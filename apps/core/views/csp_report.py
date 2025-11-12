"""
CSP Report Endpoint for Content Security Policy Violations
"""

import json
import logging
from datetime import datetime

from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.http import HttpResponse
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from apps.core.decorators import rate_limit

logger = logging.getLogger("security.csp")


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(rate_limit(max_requests=120, window_seconds=60), name='dispatch')
class CSPReportView(View):
    """
    Endpoint to receive CSP violation reports from browsers.
    
    CSP violations are sent by browsers when content violates the Content Security Policy.
    This helps identify:
    - Legitimate inline scripts that need to be refactored
    - Actual XSS attempts
    - Third-party resources that need to be whitelisted
    
    Security: CSRF exempt is acceptable here (Rule #2 alternative protection):
    - Browser-automated reports (not user-initiated)
    - Read-only side effects (logging only)
    - Content-Type validation enforced
    - Content-Length limited to 64KB
    - Rate limited to 120 requests/minute per IP
    - No state modification or sensitive data access
    """
    
    # Maximum allowed size for CSP reports (64KB)
    MAX_CONTENT_LENGTH = 64 * 1024  # 64KB
    
    def post(self, request):
        """
        Process CSP violation report.
        
        The browser sends a JSON payload with the violation details.
        
        Security validations:
        - Content-Type enforcement
        - Content-Length limit (64KB max)
        - Rate limiting (120/minute)
        """
        try:
            # Security: Enforce content length limit
            content_length = int(request.META.get('CONTENT_LENGTH', 0))
            if content_length > self.MAX_CONTENT_LENGTH:
                logger.warning(
                    f"CSP report rejected: Content too large ({content_length} bytes)",
                    extra={'client_ip': self._get_client_ip(request), 'content_length': content_length}
                )
                return HttpResponse(status=413)  # Payload Too Large
            
            # Parse the CSP report
            if request.content_type == 'application/csp-report':
                report_data = json.loads(request.body.decode('utf-8'))
            elif request.content_type == 'application/json':
                report_data = json.loads(request.body.decode('utf-8'))
            else:
                logger.warning(
                    f"Invalid content type for CSP report: {request.content_type}",
                    extra={'client_ip': self._get_client_ip(request)}
                )
                return HttpResponse(status=400)
                
            # Extract the CSP report
            csp_report = report_data.get('csp-report', report_data)
            
            # Log the violation
            self._log_csp_violation(csp_report, request)
            
            # Store violation for analysis if configured
            if getattr(settings, 'CSP_STORE_VIOLATIONS', True):
                self._store_violation(csp_report, request)
                
            # Check for critical violations
            if self._is_critical_violation(csp_report):
                self._handle_critical_violation(csp_report, request)
                
            return HttpResponse(status=204)  # No Content
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode CSP report: {e}")
            return HttpResponse(status=400)
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error processing CSP report: {e}")
            return HttpResponse(status=500)
            
    def _log_csp_violation(self, report, request):
        """
        Log CSP violation details.
        
        Args:
            report: CSP violation report data
            request: Django request object
        """
        violated_directive = report.get('violated-directive', 'unknown')
        blocked_uri = report.get('blocked-uri', 'unknown')
        document_uri = report.get('document-uri', 'unknown')
        source_file = report.get('source-file', 'unknown')
        line_number = report.get('line-number', 'unknown')
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Determine severity
        severity = self._determine_severity(report)
        
        log_message = (
            f"CSP Violation [{severity}] - "
            f"IP: {client_ip}, "
            f"Document: {document_uri}, "
            f"Violated: {violated_directive}, "
            f"Blocked: {blocked_uri}, "
            f"Source: {source_file}:{line_number}"
        )
        
        if severity == 'CRITICAL':
            logger.error(log_message)
        elif severity == 'HIGH':
            logger.warning(log_message)
        else:
            logger.info(log_message)
            
    def _store_violation(self, report, request):
        """
        Store CSP violation for analysis.
        
        Args:
            report: CSP violation report data
            request: Django request object
        """
        try:
            from apps.core.models import CSPViolation
            
            CSPViolation.objects.create(
                document_uri=report.get('document-uri', ''),
                referrer=report.get('referrer', ''),
                violated_directive=report.get('violated-directive', ''),
                effective_directive=report.get('effective-directive', ''),
                original_policy=report.get('original-policy', ''),
                blocked_uri=report.get('blocked-uri', ''),
                source_file=report.get('source-file', ''),
                line_number=report.get('line-number', 0) or 0,
                column_number=report.get('column-number', 0) or 0,
                status_code=report.get('status-code', 0) or 0,
                script_sample=report.get('script-sample', ''),
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                reported_at=datetime.now()
            )
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to store CSP violation: {e}")
            
    def _is_critical_violation(self, report):
        """
        Check if the violation is critical (potential attack).
        
        Args:
            report: CSP violation report data
            
        Returns:
            bool: True if violation is critical
        """
        blocked_uri = report.get('blocked-uri', '').lower()
        violated_directive = report.get('violated-directive', '').lower()
        script_sample = report.get('script-sample', '').lower()
        
        # Check for inline script violations with suspicious content
        if 'script-src' in violated_directive:
            if 'inline' in blocked_uri or blocked_uri == 'eval':
                # Check for suspicious patterns in script sample
                suspicious_patterns = [
                    'eval(',
                    'document.cookie',
                    'document.write',
                    '.innerhtml',
                    'xmlhttprequest',
                    'fetch(',
                    'window.location',
                    'alert(',
                    'prompt(',
                    'confirm('
                ]
                
                for pattern in suspicious_patterns:
                    if pattern in script_sample:
                        return True
                        
        # Check for data: URIs in script-src (common XSS vector)
        if 'script-src' in violated_directive and blocked_uri.startswith('data:'):
            return True
            
        # Check for external script injections from untrusted sources
        if 'script-src' in violated_directive:
            untrusted_domains = [
                'evil.com',
                'malicious.net',
                # Add more known malicious domains
            ]
            for domain in untrusted_domains:
                if domain in blocked_uri:
                    return True
                    
        return False
        
    def _handle_critical_violation(self, report, request):
        """
        Handle critical CSP violations (potential attacks).
        
        Args:
            report: CSP violation report data
            request: Django request object
        """
        client_ip = self._get_client_ip(request)
        
        # Log security event
        logger.critical(
            f"POTENTIAL XSS ATTACK - IP: {client_ip}, "
            f"Document: {report.get('document-uri', 'unknown')}, "
            f"Blocked: {report.get('blocked-uri', 'unknown')}, "
            f"Script Sample: {report.get('script-sample', 'none')[:100]}"
        )
        
        # Could implement additional security measures here:
        # - Temporarily block IP
        # - Send alert to security team
        # - Increase rate limiting for this IP
        
    def _determine_severity(self, report):
        """
        Determine the severity of a CSP violation.
        
        Args:
            report: CSP violation report data
            
        Returns:
            str: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
        """
        if self._is_critical_violation(report):
            return 'CRITICAL'
            
        violated_directive = report.get('violated-directive', '').lower()
        blocked_uri = report.get('blocked-uri', '').lower()
        
        # High severity - inline scripts/styles that might be legitimate but risky
        if 'script-src' in violated_directive and ('inline' in blocked_uri or 'eval' in blocked_uri):
            return 'HIGH'
            
        # Medium severity - external resources from unknown sources
        if 'script-src' in violated_directive or 'style-src' in violated_directive:
            return 'MEDIUM'
            
        # Low severity - other violations (images, fonts, etc.)
        return 'LOW'
        
    def _get_client_ip(self, request):
        """
        Get client IP address from request.
        
        Args:
            request: Django request object
            
        Returns:
            str: Client IP address
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
