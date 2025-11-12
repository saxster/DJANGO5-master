"""
Virus scanning service using ClamAV.

Provides malware detection for file uploads to prevent distribution
of malicious content through the platform.
"""
import logging
from typing import Dict, Any, Optional
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

logger = logging.getLogger(__name__)

# Try to import ClamAV client
try:
    import pyclamd
    HAS_CLAMAV = True
except ImportError:
    pyclamd = None
    HAS_CLAMAV = False
    logger.warning("pyclamd not installed - virus scanning disabled")


class VirusScannerService:
    """Service for scanning uploaded files for malware."""

    @classmethod
    def scan_file(
        cls,
        uploaded_file,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scan uploaded file for malware using ClamAV.

        Args:
            uploaded_file: Django UploadedFile instance
            timeout: Optional scan timeout in seconds

        Returns:
            dict: Scan result with keys:
                - safe (bool): True if no malware detected
                - threat_name (str|None): Name of detected threat
                - engine (str): Scanning engine used
                - scan_time_ms (int): Scan duration

        Raises:
            TimeoutError: If scan exceeds timeout
            ImproperlyConfigured: If ClamAV not available and scanning required
        """
        import time

        start_time = time.time()

        # Check if virus scanning is enabled
        scanning_enabled = getattr(settings, 'FILE_UPLOAD_VIRUS_SCANNING', True)

        if not scanning_enabled:
            logger.debug("Virus scanning disabled in settings")
            return {
                'safe': True,
                'threat_name': None,
                'engine': 'disabled',
                'scan_time_ms': 0
            }

        # Check if ClamAV is available
        if not HAS_CLAMAV:
            logger.warning(
                "Virus scanning enabled but pyclamd not installed - failing open",
                extra={'uploaded_filename': uploaded_file.name}
            )
            return {
                'safe': True,  # Fail open (allow upload)
                'threat_name': None,
                'engine': 'unavailable',
                'scan_time_ms': 0
            }

        try:
            # Connect to ClamAV daemon
            cd = pyclamd.ClamdUnixSocket()

            # Verify ClamAV is running
            if not cd.ping():
                raise ImproperlyConfigured("ClamAV daemon not responding")

            # Read file content
            uploaded_file.seek(0)  # Reset file pointer
            file_content = uploaded_file.read()
            uploaded_file.seek(0)  # Reset for subsequent operations

            # Scan with timeout
            scan_result = cd.scan_stream(file_content)

            scan_time_ms = int((time.time() - start_time) * 1000)

            # Process result
            if scan_result is None:
                # No virus detected
                logger.info(
                    f"File scan clean: {uploaded_file.name}",
                    extra={
                        'uploaded_filename': uploaded_file.name,
                        'size_bytes': len(file_content),
                        'scan_time_ms': scan_time_ms
                    }
                )
                return {
                    'safe': True,
                    'threat_name': None,
                    'engine': 'clamav',
                    'scan_time_ms': scan_time_ms
                }
            else:
                # Virus detected
                threat = scan_result['stream']
                threat_status, threat_name = threat

                logger.error(
                    f"Malware detected in upload: {threat_name}",
                    extra={
                        'uploaded_filename': uploaded_file.name,
                        'threat': threat_name,
                        'scan_time_ms': scan_time_ms
                    }
                )

                return {
                    'safe': False,
                    'threat_name': threat_name,
                    'engine': 'clamav',
                    'scan_time_ms': scan_time_ms
                }

        except (OSError, IOError) as e:
            logger.error(
                f"ClamAV connection error: {e}",
                extra={'uploaded_filename': uploaded_file.name}
            )
            # Fail open - allow upload but log error
            return {
                'safe': True,
                'threat_name': None,
                'engine': 'error',
                'scan_time_ms': int((time.time() - start_time) * 1000),
                'error': str(e)
            }
