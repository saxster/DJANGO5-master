"""
Advanced File Validation and Malware Scanning Service

Enhanced security service that provides:
- Deep file content analysis
- Malware signature detection
- Behavioral pattern analysis
- Suspicious file quarantine
- Integration with external scanning services

Extends the SecureFileUploadService for comprehensive file security.
Addresses advanced threats beyond basic path traversal (CVSS 8.1) vulnerability.
"""

import os
import hashlib
import mimetypes
import logging
import subprocess
import tempfile
from typing import Dict, List, Optional, Any, Tuple
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from apps.core.services.secure_file_upload_service import SecureFileUploadService
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger(__name__)


class AdvancedFileValidationService(SecureFileUploadService):
    """
    Advanced file validation service with malware scanning and behavioral analysis.

    Extends SecureFileUploadService with:
    - Malware signature detection
    - Behavioral analysis
    - Content deep inspection
    - External scanner integration
    - Quarantine management
    """

    # Known malware signatures (simplified for demonstration)
    MALWARE_SIGNATURES = {
        # PE executable signatures
        b'\x4d\x5a\x90\x00': 'PE_EXECUTABLE',
        b'\x4d\x5a\x80\x00': 'PE_EXECUTABLE',

        # Script signatures
        b'<script': 'JAVASCRIPT_INJECTION',
        b'<?php': 'PHP_SCRIPT',
        b'<%': 'ASP_SCRIPT',

        # Archive bombs
        b'PK\x03\x04': 'ZIP_ARCHIVE',  # Need further analysis

        # Suspicious patterns
        b'eval(': 'EVAL_FUNCTION',
        b'exec(': 'EXEC_FUNCTION',
        b'system(': 'SYSTEM_CALL',
        b'shell_exec': 'SHELL_EXECUTION',
    }

    # Suspicious file patterns
    SUSPICIOUS_PATTERNS = [
        # Base64 encoded payloads
        r'[A-Za-z0-9+/]{100,}={0,2}',
        # Hex encoded data
        r'[0-9a-fA-F]{100,}',
        # Multiple extensions
        r'\.[a-zA-Z]{2,4}\.[a-zA-Z]{2,4}$',
        # Encoded URLs
        r'%[0-9a-fA-F]{2}',
        # JavaScript/VBScript
        r'(javascript|vbscript):[^;]*',
    ]

    # File type specific validations
    FILE_TYPE_VALIDATORS = {
        'image': '_validate_image_content',
        'pdf': '_validate_pdf_content',
        'document': '_validate_document_content',
        'archive': '_validate_archive_content'
    }

    @classmethod
    def validate_and_scan_file(
        cls,
        uploaded_file: UploadedFile,
        file_type: str,
        upload_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enhanced validation with malware scanning and behavioral analysis.

        Args:
            uploaded_file: Django UploadedFile object
            file_type: Type of file ('image', 'pdf', 'document')
            upload_context: Dict with context info (user_id, folder_type, etc.)

        Returns:
            dict: Enhanced file information with security analysis

        Raises:
            ValidationError: If any security validation fails
        """
        try:
            correlation_id = cls._generate_correlation_id()

            logger.info(
                "Starting advanced file validation and scanning",
                extra={
                    'correlation_id': correlation_id,
                    'file_type': file_type,
                    'original_filename': uploaded_file.name if uploaded_file else 'None',
                    'upload_context': upload_context
                }
            )

            # Phase 1: Basic security validation (from parent class)
            file_metadata = super().validate_and_process_upload(
                uploaded_file, file_type, upload_context
            )

            # Phase 2: Advanced content analysis
            security_analysis = cls._perform_security_analysis(uploaded_file, file_type, correlation_id)

            # Phase 3: Malware signature detection
            malware_scan_result = cls._scan_for_malware(uploaded_file, correlation_id)

            # Phase 4: Behavioral analysis
            behavioral_analysis = cls._perform_behavioral_analysis(uploaded_file, file_type, correlation_id)

            # Phase 5: External scanner integration (if enabled)
            external_scan_result = cls._external_malware_scan(uploaded_file, correlation_id)

            # Phase 6: Risk assessment
            risk_assessment = cls._calculate_risk_score(
                security_analysis, malware_scan_result, behavioral_analysis, external_scan_result
            )

            # Phase 7: Quarantine decision
            quarantine_decision = cls._determine_quarantine_action(risk_assessment)

            # Enhanced metadata with security analysis
            enhanced_metadata = {
                **file_metadata,
                'security_analysis': security_analysis,
                'malware_scan': malware_scan_result,
                'behavioral_analysis': behavioral_analysis,
                'external_scan': external_scan_result,
                'risk_assessment': risk_assessment,
                'quarantine_decision': quarantine_decision,
                'scan_timestamp': timezone.now().isoformat()
            }

            # Log security analysis results
            logger.info(
                "Advanced file validation completed",
                extra={
                    'correlation_id': correlation_id,
                    'risk_score': risk_assessment['risk_score'],
                    'threat_level': risk_assessment['threat_level'],
                    'quarantine_action': quarantine_decision['action']
                }
            )

            # Raise validation error if high risk
            if risk_assessment['threat_level'] in ['HIGH', 'CRITICAL']:
                raise ValidationError(
                    f"File rejected due to security concerns: {risk_assessment['threat_summary']}"
                )

            return enhanced_metadata

        except ValidationError:
            raise
        except (TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'AdvancedFileValidationService',
                    'method': 'validate_and_scan_file',
                    'file_type': file_type,
                    'upload_context': upload_context
                }
            )
            raise ValidationError(
                f"Advanced file validation failed (ID: {correlation_id})"
            ) from e

    @classmethod
    def _perform_security_analysis(cls, uploaded_file, file_type, correlation_id):
        """Perform deep security analysis of file content."""
        analysis = {
            'file_structure_valid': True,
            'suspicious_patterns_found': [],
            'embedded_content_detected': [],
            'metadata_analysis': {},
            'entropy_analysis': {},
            'content_summary': {}
        }

        try:
            # Read file content for analysis
            uploaded_file.seek(0)
            file_content = uploaded_file.read(10 * 1024 * 1024)  # Read up to 10MB
            uploaded_file.seek(0)

            # Check for suspicious patterns
            analysis['suspicious_patterns_found'] = cls._detect_suspicious_patterns(file_content)

            # Analyze file entropy (measure of randomness - high entropy may indicate encryption/compression)
            analysis['entropy_analysis'] = cls._calculate_entropy(file_content)

            # File type specific analysis
            if file_type in cls.FILE_TYPE_VALIDATORS:
                validator_method = getattr(cls, cls.FILE_TYPE_VALIDATORS[file_type])
                specific_analysis = validator_method(file_content, uploaded_file.name)
                analysis.update(specific_analysis)

            # Metadata extraction
            analysis['metadata_analysis'] = cls._extract_file_metadata(file_content, file_type)

            # Check for embedded content
            analysis['embedded_content_detected'] = cls._detect_embedded_content(file_content)

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            logger.warning(
                "Error during security analysis",
                extra={
                    'correlation_id': correlation_id,
                    'error': str(e)
                }
            )
            analysis['analysis_error'] = str(e)

        return analysis

    @classmethod
    def _scan_for_malware(cls, uploaded_file, correlation_id):
        """Scan file for known malware signatures."""
        scan_result = {
            'signatures_detected': [],
            'threat_classification': 'CLEAN',
            'confidence_level': 'HIGH',
            'scan_details': {}
        }

        try:
            # Read file content
            uploaded_file.seek(0)
            file_content = uploaded_file.read()
            uploaded_file.seek(0)

            # Scan for known signatures
            for signature, threat_type in cls.MALWARE_SIGNATURES.items():
                if signature in file_content:
                    scan_result['signatures_detected'].append({
                        'signature': signature.hex(),
                        'threat_type': threat_type,
                        'location': file_content.find(signature)
                    })

            # Classify threat level
            if scan_result['signatures_detected']:
                threat_types = [sig['threat_type'] for sig in scan_result['signatures_detected']]

                if any(t in ['PE_EXECUTABLE', 'SHELL_EXECUTION'] for t in threat_types):
                    scan_result['threat_classification'] = 'MALWARE'
                elif any(t in ['JAVASCRIPT_INJECTION', 'PHP_SCRIPT'] for t in threat_types):
                    scan_result['threat_classification'] = 'SUSPICIOUS'
                else:
                    scan_result['threat_classification'] = 'LOW_RISK'

            # Add scan statistics
            scan_result['scan_details'] = {
                'bytes_scanned': len(file_content),
                'signatures_checked': len(cls.MALWARE_SIGNATURES),
                'scan_duration_ms': 0  # Would be actual timing in real implementation
            }

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.warning(
                "Error during malware scan",
                extra={
                    'correlation_id': correlation_id,
                    'error': str(e)
                }
            )
            scan_result['scan_error'] = str(e)
            scan_result['threat_classification'] = 'UNKNOWN'

        return scan_result

    @classmethod
    def _perform_behavioral_analysis(cls, uploaded_file, file_type, correlation_id):
        """Analyze file behavior patterns and characteristics."""
        analysis = {
            'file_characteristics': {},
            'behavioral_indicators': [],
            'anomaly_score': 0,
            'suspicious_behaviors': []
        }

        try:
            # File size analysis
            file_size = uploaded_file.size
            analysis['file_characteristics']['size'] = file_size

            # Check for unusual file sizes
            if cls._is_unusual_file_size(file_size, file_type):
                analysis['behavioral_indicators'].append('UNUSUAL_FILE_SIZE')

            # Check filename characteristics
            filename = uploaded_file.name
            filename_analysis = cls._analyze_filename_behavior(filename)
            analysis['file_characteristics']['filename_analysis'] = filename_analysis

            if filename_analysis['suspicious_patterns']:
                analysis['behavioral_indicators'].extend(filename_analysis['suspicious_patterns'])

            # Content-based behavioral analysis
            uploaded_file.seek(0)
            content_sample = uploaded_file.read(1024)  # First 1KB
            uploaded_file.seek(0)

            # Check for packed/encrypted content
            if cls._appears_packed_or_encrypted(content_sample):
                analysis['behavioral_indicators'].append('PACKED_OR_ENCRYPTED_CONTENT')

            # Calculate anomaly score
            analysis['anomaly_score'] = len(analysis['behavioral_indicators']) * 10

            # Determine suspicious behaviors
            if analysis['anomaly_score'] > 30:
                analysis['suspicious_behaviors'].append('HIGH_ANOMALY_SCORE')

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.warning(
                "Error during behavioral analysis",
                extra={
                    'correlation_id': correlation_id,
                    'error': str(e)
                }
            )
            analysis['analysis_error'] = str(e)

        return analysis

    @classmethod
    def _external_malware_scan(cls, uploaded_file, correlation_id):
        """Integrate with external malware scanning services."""
        scan_result = {
            'service_used': None,
            'scan_result': 'NOT_SCANNED',
            'threat_detected': False,
            'scan_details': {}
        }

        # Check if external scanning is enabled
        enable_external_scan = getattr(settings, 'ENABLE_EXTERNAL_MALWARE_SCAN', False)

        if not enable_external_scan:
            scan_result['scan_result'] = 'DISABLED'
            return scan_result

        try:
            # Integration with ClamAV (if available)
            if cls._is_clamav_available():
                scan_result = cls._scan_with_clamav(uploaded_file, correlation_id)
            # Could add other scanners here (VirusTotal API, etc.)
            else:
                scan_result['scan_result'] = 'NO_SCANNER_AVAILABLE'

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.warning(
                "Error during external malware scan",
                extra={
                    'correlation_id': correlation_id,
                    'error': str(e)
                }
            )
            scan_result['scan_error'] = str(e)
            scan_result['scan_result'] = 'ERROR'

        return scan_result

    @classmethod
    def _calculate_risk_score(
        cls,
        security_analysis: Dict[str, Any],
        malware_scan: Dict[str, Any],
        behavioral_analysis: Dict[str, Any],
        external_scan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate overall risk score and threat level."""
        risk_score = 0
        threat_factors = []

        # Security analysis factors
        if security_analysis.get('suspicious_patterns_found'):
            risk_score += len(security_analysis['suspicious_patterns_found']) * 10
            threat_factors.append('SUSPICIOUS_PATTERNS')

        if security_analysis.get('embedded_content_detected'):
            risk_score += len(security_analysis['embedded_content_detected']) * 15
            threat_factors.append('EMBEDDED_CONTENT')

        # Malware scan factors
        if malware_scan.get('signatures_detected'):
            if malware_scan['threat_classification'] == 'MALWARE':
                risk_score += 100
                threat_factors.append('MALWARE_DETECTED')
            elif malware_scan['threat_classification'] == 'SUSPICIOUS':
                risk_score += 50
                threat_factors.append('SUSPICIOUS_CODE')

        # Behavioral analysis factors
        risk_score += behavioral_analysis.get('anomaly_score', 0)
        if behavioral_analysis.get('behavioral_indicators'):
            threat_factors.extend(behavioral_analysis['behavioral_indicators'])

        # External scan factors
        if external_scan.get('threat_detected'):
            risk_score += 75
            threat_factors.append('EXTERNAL_SCAN_THREAT')

        # Determine threat level
        if risk_score >= 100:
            threat_level = 'CRITICAL'
        elif risk_score >= 75:
            threat_level = 'HIGH'
        elif risk_score >= 50:
            threat_level = 'MEDIUM'
        elif risk_score >= 25:
            threat_level = 'LOW'
        else:
            threat_level = 'MINIMAL'

        return {
            'risk_score': risk_score,
            'threat_level': threat_level,
            'threat_factors': threat_factors,
            'threat_summary': cls._generate_threat_summary(threat_factors, threat_level)
        }

    @classmethod
    def _determine_quarantine_action(cls, risk_assessment):
        """Determine if file should be quarantined and what action to take."""
        threat_level = risk_assessment['threat_level']
        risk_score = risk_assessment['risk_score']

        if threat_level in ['CRITICAL', 'HIGH']:
            action = 'QUARANTINE'
            reason = f"High threat level ({threat_level}) detected"
        elif threat_level == 'MEDIUM' and risk_score > 60:
            action = 'REVIEW'
            reason = "Medium threat requires manual review"
        else:
            action = 'ALLOW'
            reason = "Risk level acceptable"

        return {
            'action': action,
            'reason': reason,
            'quarantine_duration_hours': 72 if action == 'QUARANTINE' else 0,
            'review_required': action in ['QUARANTINE', 'REVIEW']
        }

    # Helper methods for analysis

    @classmethod
    def _detect_suspicious_patterns(cls, content: bytes) -> List[str]:
        """Detect suspicious patterns in file content."""
        import re
        suspicious_found = []

        for pattern in cls.SUSPICIOUS_PATTERNS:
            matches = re.finditer(pattern.encode() if isinstance(pattern, str) else pattern, content)
            for match in matches:
                suspicious_found.append({
                    'pattern': pattern,
                    'location': match.start(),
                    'length': len(match.group())
                })
                if len(suspicious_found) > 10:  # Limit to prevent performance issues
                    break

        return suspicious_found

    @classmethod
    def _calculate_entropy(cls, data):
        """Calculate Shannon entropy of data."""
        if not data:
            return {'entropy': 0, 'analysis': 'EMPTY_FILE'}

        # Count byte frequency
        byte_counts = {}
        for byte in data:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1

        # Calculate entropy
        entropy = 0
        length = len(data)
        for count in byte_counts.values():
            p = count / length
            if p > 0:
                entropy -= p * (p.bit_length() - 1)

        # Analyze entropy level
        if entropy > 7.5:
            analysis = 'HIGH_ENTROPY_SUSPICIOUS'
        elif entropy > 6.0:
            analysis = 'MEDIUM_ENTROPY'
        else:
            analysis = 'LOW_ENTROPY_NORMAL'

        return {
            'entropy': round(entropy, 3),
            'analysis': analysis,
            'unique_bytes': len(byte_counts)
        }

    @classmethod
    def _validate_image_content(cls, content, filename):
        """Validate image file content for security issues."""
        analysis = {
            'image_format_valid': True,
            'embedded_data_detected': False,
            'metadata_concerns': []
        }

        # Check for embedded scripts in image
        if b'<script' in content or b'javascript:' in content:
            analysis['embedded_data_detected'] = True
            analysis['metadata_concerns'].append('EMBEDDED_JAVASCRIPT')

        # Check for unusual metadata
        if b'<?php' in content or b'<%' in content:
            analysis['embedded_data_detected'] = True
            analysis['metadata_concerns'].append('EMBEDDED_SERVER_SCRIPT')

        return analysis

    @classmethod
    def _validate_pdf_content(cls, content, filename):
        """Validate PDF file content for security issues."""
        analysis = {
            'pdf_structure_valid': True,
            'javascript_detected': False,
            'embedded_files_detected': False,
            'security_concerns': []
        }

        # Check for embedded JavaScript
        if b'/JavaScript' in content or b'/JS' in content:
            analysis['javascript_detected'] = True
            analysis['security_concerns'].append('EMBEDDED_JAVASCRIPT')

        # Check for embedded files
        if b'/EmbeddedFile' in content:
            analysis['embedded_files_detected'] = True
            analysis['security_concerns'].append('EMBEDDED_FILES')

        return analysis

    @classmethod
    def _validate_document_content(cls, content, filename):
        """Validate document file content for security issues."""
        analysis = {
            'document_format_valid': True,
            'macros_detected': False,
            'external_links_detected': False,
            'security_concerns': []
        }

        # Check for macros
        if b'vba' in content.lower() or b'macro' in content.lower():
            analysis['macros_detected'] = True
            analysis['security_concerns'].append('MACROS_DETECTED')

        # Check for external links
        if b'http://' in content or b'https://' in content:
            analysis['external_links_detected'] = True
            analysis['security_concerns'].append('EXTERNAL_LINKS')

        return analysis

    @classmethod
    def _extract_file_metadata(cls, content, file_type):
        """Extract and analyze file metadata."""
        metadata = {
            'creation_tool': 'UNKNOWN',
            'creation_date': None,
            'suspicious_metadata': False
        }

        # Look for common metadata indicators
        if b'Creator' in content or b'Producer' in content:
            # PDF metadata
            if b'Script' in content or b'JavaScript' in content:
                metadata['suspicious_metadata'] = True

        return metadata

    @classmethod
    def _detect_embedded_content(cls, content):
        """Detect embedded content that might be suspicious."""
        embedded_content = []

        # Check for embedded archives
        if b'PK\x03\x04' in content:
            embedded_content.append('ZIP_ARCHIVE')

        # Check for embedded executables
        if b'MZ' in content:
            embedded_content.append('PE_EXECUTABLE')

        # Check for scripts
        if b'<script' in content:
            embedded_content.append('JAVASCRIPT')

        return embedded_content

    @classmethod
    def _is_unusual_file_size(cls, file_size, file_type):
        """Check if file size is unusual for the file type."""
        # Define normal size ranges for different file types
        size_ranges = {
            'image': (1024, 50 * 1024 * 1024),    # 1KB to 50MB
            'pdf': (1024, 100 * 1024 * 1024),     # 1KB to 100MB
            'document': (1024, 50 * 1024 * 1024), # 1KB to 50MB
        }

        if file_type in size_ranges:
            min_size, max_size = size_ranges[file_type]
            return file_size < min_size or file_size > max_size

        return False

    @classmethod
    def _analyze_filename_behavior(cls, filename):
        """Analyze filename for suspicious patterns."""
        analysis = {
            'length': len(filename),
            'suspicious_patterns': [],
            'character_analysis': {}
        }

        # Check for suspicious patterns
        if '..' in filename:
            analysis['suspicious_patterns'].append('PATH_TRAVERSAL')

        if filename.count('.') > 2:
            analysis['suspicious_patterns'].append('MULTIPLE_EXTENSIONS')

        # Check for unusual characters
        unusual_chars = set(filename) - set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-')
        if unusual_chars:
            analysis['suspicious_patterns'].append('UNUSUAL_CHARACTERS')
            analysis['character_analysis']['unusual_chars'] = list(unusual_chars)

        return analysis

    @classmethod
    def _appears_packed_or_encrypted(cls, content_sample):
        """Check if content appears to be packed or encrypted."""
        if len(content_sample) < 100:
            return False

        # Calculate entropy of sample
        entropy_analysis = cls._calculate_entropy(content_sample)
        return entropy_analysis['entropy'] > 7.0

    @classmethod
    def _is_clamav_available(cls):
        """Check if ClamAV antivirus is available."""
        try:
            result = subprocess.run(['clamscan', '--version'],
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    @classmethod
    def _scan_with_clamav(cls, uploaded_file, correlation_id):
        """Scan file with ClamAV antivirus."""
        scan_result = {
            'service_used': 'ClamAV',
            'scan_result': 'CLEAN',
            'threat_detected': False,
            'scan_details': {}
        }

        try:
            # Write file to temporary location for scanning
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                uploaded_file.seek(0)
                temp_file.write(uploaded_file.read())
                temp_file_path = temp_file.name
                uploaded_file.seek(0)

            # Run ClamAV scan
            result = subprocess.run(['clamscan', '--no-summary', temp_file_path],
                                  capture_output=True, text=True, timeout=30)

            # Parse results
            if result.returncode == 0:
                scan_result['scan_result'] = 'CLEAN'
            elif result.returncode == 1:
                scan_result['scan_result'] = 'INFECTED'
                scan_result['threat_detected'] = True
                scan_result['scan_details']['threat_info'] = result.stdout.strip()
            else:
                scan_result['scan_result'] = 'ERROR'
                scan_result['scan_details']['error'] = result.stderr.strip()

            # Clean up temporary file
            os.unlink(temp_file_path)

        except subprocess.TimeoutExpired:
            scan_result['scan_result'] = 'TIMEOUT'
        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            scan_result['scan_result'] = 'ERROR'
            scan_result['scan_details']['error'] = str(e)

        return scan_result

    @classmethod
    def _generate_threat_summary(cls, threat_factors, threat_level):
        """Generate human-readable threat summary."""
        if not threat_factors:
            return "No security threats detected"

        factor_descriptions = {
            'SUSPICIOUS_PATTERNS': 'suspicious code patterns',
            'EMBEDDED_CONTENT': 'embedded content',
            'MALWARE_DETECTED': 'malware signatures',
            'SUSPICIOUS_CODE': 'suspicious code',
            'EXTERNAL_SCAN_THREAT': 'external scanner detection',
            'UNUSUAL_FILE_SIZE': 'unusual file size',
            'PATH_TRAVERSAL': 'path traversal attempt',
            'MULTIPLE_EXTENSIONS': 'multiple file extensions'
        }

        descriptions = [factor_descriptions.get(factor, factor.lower()) for factor in threat_factors[:3]]
        summary = f"Threat level {threat_level}: {', '.join(descriptions)}"

        if len(threat_factors) > 3:
            summary += f" and {len(threat_factors) - 3} other concerns"

        return summary