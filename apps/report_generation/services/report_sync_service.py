"""
Report Sync Service for Mobile Offline-First Operations

Handles mobile sync for report generation following established patterns:
- Inherits from BaseSyncService
- Bulk upsert with conflict detection
- Delta sync for efficient mobile bandwidth
- Idempotency support
- Attachment handling

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling
- Multi-tenant isolation
"""

import logging
from typing import Dict, Any, List
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.core.services.sync.base_sync_service import BaseSyncService
from apps.report_generation.models import GeneratedReport, ReportAttachment
from apps.ontology import ontology

logger = logging.getLogger(__name__)


@ontology(
    domain="report_generation",
    concept="Mobile Report Synchronization with AI Processing",
    purpose=(
        "Receives reports created offline by Kotlin Android app, processes them "
        "with AI analysis, quality gates, and mentor guidance. Handles bulk sync, "
        "conflict resolution, and attachment processing."
    ),
    criticality="high",
    inputs=[
        {
            "name": "sync_data",
            "type": "dict",
            "description": "Mobile sync payload with report entries",
            "structure": {
                "entries": "List[dict] - Reports from mobile",
                "last_sync_timestamp": "str - Last successful sync",
                "client_id": "str - Device identifier",
                "attachments": "List[dict] - Photos/videos from reports"
            }
        }
    ],
    outputs=[
        {
            "name": "sync_response",
            "type": "dict",
            "structure": {
                "synced_reports": "List[dict] - Server IDs mapped to mobile IDs",
                "conflicts": "List[dict] - Version conflicts",
                "errors": "List[dict] - Validation errors",
                "ai_analysis_queued": "int - Reports queued for AI processing"
            }
        }
    ],
    side_effects=[
        "Creates GeneratedReport records from mobile data",
        "Triggers async AI analysis (quality gates, mentor detection)",
        "Processes attachments (EXIF, OCR, damage detection)",
        "Sends supervisor notifications for pending reviews",
        "Updates incident trends and learning statistics"
    ]
)
class ReportSyncService(BaseSyncService):
    """
    Sync service for report generation.
    Leverages existing BaseSyncService infrastructure.
    """
    
    def sync_reports(
        self,
        user,
        sync_data: Dict[str, Any],
        serializer_class
    ) -> Dict[str, Any]:
        """
        Process bulk report sync from Kotlin app.
        
        Args:
            user: Authenticated user
            sync_data: Mobile sync payload
            serializer_class: Report sync serializer
        
        Returns:
            Sync results with server IDs
        """
        result = self.process_sync_batch(
            user=user,
            sync_data=sync_data,
            model_class=GeneratedReport,
            serializer_class=serializer_class,
            extra_filters={'tenant': user.tenant}
        )
        
        # Queue AI analysis for new reports
        ai_queued = 0
        for item in result['synced_items']:
            if item.get('created', False):
                from apps.report_generation.tasks import process_incoming_report
                process_incoming_report.delay(item['server_id'])
                ai_queued += 1
        
        result['ai_analysis_queued'] = ai_queued
        
        logger.info(
            f"Synced {len(result['synced_items'])} reports, "
            f"queued {ai_queued} for AI analysis"
        )
        
        return result
    
    def sync_attachments(
        self,
        user,
        attachment_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process attachment uploads from mobile.
        
        Args:
            user: Authenticated user
            attachment_data: List of attachment data with base64 or S3 URLs
        
        Returns:
            Processing results
        """
        results = {'processed': 0, 'failed': []}
        
        for data in attachment_data:
            try:
                report_id = data.get('report_id') or data.get('report_server_id')
                
                if not report_id:
                    results['failed'].append({
                        'mobile_id': data.get('mobile_id'),
                        'error': 'Missing report_id'
                    })
                    continue
                
                # Verify access
                report = GeneratedReport.objects.get(
                    id=report_id,
                    tenant=user.tenant
                )
                
                # Create attachment
                attachment = self._create_attachment(report, data, user)
                
                # Queue AI analysis
                from apps.report_generation.tasks import analyze_attachment_async
                analyze_attachment_async.delay(attachment.id)
                
                results['processed'] += 1
                
            except GeneratedReport.DoesNotExist:
                results['failed'].append({
                    'mobile_id': data.get('mobile_id'),
                    'error': 'Report not found or access denied'
                })
            except (ValidationError, ValueError, IOError, OSError) as e:
                # Catch specific exceptions from file handling and validation
                # ValidationError: File validation failures
                # ValueError: Invalid data formats
                # IOError/OSError: File system errors during save
                logger.error(f"Attachment sync error: {e}", exc_info=True)
                results['failed'].append({
                    'mobile_id': data.get('mobile_id'),
                    'error': str(e)
                })
        
        return results
    
    def _create_attachment(self, report, data, user):
        """Create attachment from mobile data."""
        from apps.core.services.secure_file_upload_service import SecureFileUploadService
        
        # Handle base64 or S3 URL
        if 'file_base64' in data:
            file_data = self._decode_base64_file(data['file_base64'])
        elif 's3_url' in data:
            file_data = self._download_from_s3(data['s3_url'])
        else:
            raise ValidationError("No file data provided")
        
        # Validate and save
        attachment = ReportAttachment.objects.create(
            report=report,
            filename=data['filename'],
            attachment_type=data.get('attachment_type', 'photo'),
            evidence_category=data.get('evidence_category', 'scene'),
            file_size=data.get('file_size', len(file_data)),
            mime_type=data.get('mime_type', 'image/jpeg'),
            metadata=data.get('metadata', {}),
            caption=data.get('caption', ''),
            user_description=data.get('description', ''),
            uploaded_by=user,
            captured_by=user
        )
        
        # Save file securely
        attachment.file.save(data['filename'], file_data)
        
        return attachment
    
    def _decode_base64_file(self, base64_data):
        """Decode base64 file data."""
        import base64
        from io import BytesIO
        
        file_data = base64.b64decode(base64_data)
        return BytesIO(file_data)
    
    def _download_from_s3(self, s3_url):
        """
        Download file from S3 presigned URL.

        Security: Validates URL against S3 domain whitelist to prevent SSRF attacks.
        Only allows requests to legitimate AWS S3 endpoints.

        Raises:
            ValidationError: If URL is not a valid S3 presigned URL
        """
        import requests
        from io import BytesIO
        from urllib.parse import urlparse

        # SECURITY: SSRF Prevention - Validate S3 URL whitelist
        # Only allow legitimate AWS S3 domains to prevent:
        # - AWS metadata service access (169.254.169.254)
        # - Internal network probing (localhost, 10.0.0.0/8, etc.)
        # - File URI attacks (file://)
        parsed = urlparse(s3_url)

        # Allowed S3 domain patterns
        allowed_domains = [
            's3.amazonaws.com',
            's3-accelerate.amazonaws.com',
        ]

        # Check for standard S3 URL or bucket-specific subdomain
        is_valid_s3 = (
            parsed.scheme == 'https' and (
                parsed.hostname in allowed_domains or
                (parsed.hostname and parsed.hostname.endswith('.s3.amazonaws.com')) or
                (parsed.hostname and parsed.hostname.endswith('.s3-accelerate.amazonaws.com'))
            )
        )

        if not is_valid_s3:
            logger.warning(
                f"SSRF attempt blocked: Invalid S3 URL '{s3_url}' "
                f"(hostname: {parsed.hostname}, scheme: {parsed.scheme})"
            )
            raise ValidationError(
                f"Invalid S3 URL. Only HTTPS URLs from AWS S3 domains are allowed. "
                f"Received: {parsed.scheme}://{parsed.hostname}"
            )

        response = requests.get(s3_url, timeout=(5, 30))
        response.raise_for_status()

        return BytesIO(response.content)
