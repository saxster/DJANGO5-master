import pytest
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.core.security.virus_scanner import VirusScannerService


@pytest.mark.security
class TestVirusScanning:

    def test_virus_scanner_service_exists(self):
        """Test VirusScannerService can be imported."""
        assert VirusScannerService is not None

    @patch('apps.core.security.virus_scanner.HAS_CLAMAV', True)
    @patch('apps.core.security.virus_scanner.pyclamd')
    def test_clean_file_passes_scan(self, mock_clamd):
        """Test clean file passes virus scan."""
        # Mock ClamAV daemon
        mock_cd = mock_clamd.ClamdUnixSocket.return_value
        mock_cd.ping.return_value = True
        mock_cd.scan_stream.return_value = None  # No virus detected

        clean_file = SimpleUploadedFile('clean.txt', b'clean content')

        result = VirusScannerService.scan_file(clean_file)

        assert result['safe'] is True
        assert result['threat_name'] is None
        assert result['engine'] == 'clamav'

    @patch('apps.core.security.virus_scanner.HAS_CLAMAV', True)
    @patch('apps.core.security.virus_scanner.pyclamd')
    def test_malware_detected_fails_scan(self, mock_clamd):
        """Test file with malware fails virus scan."""
        # Mock ClamAV daemon
        mock_cd = mock_clamd.ClamdUnixSocket.return_value
        mock_cd.ping.return_value = True
        mock_cd.scan_stream.return_value = {
            'stream': ('FOUND', 'Eicar-Test-Signature')
        }

        malware_file = SimpleUploadedFile('malware.exe', b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR')

        result = VirusScannerService.scan_file(malware_file)

        assert result['safe'] is False
        assert 'Eicar' in result['threat_name']
        assert result['engine'] == 'clamav'

    @patch('apps.core.security.virus_scanner.HAS_CLAMAV', True)
    @patch('apps.core.security.virus_scanner.pyclamd')
    def test_scan_timeout_handling(self, mock_clamd):
        """Test virus scan timeout is handled gracefully."""
        import socket
        # Mock ClamAV daemon
        mock_cd = mock_clamd.ClamdUnixSocket.return_value
        mock_cd.ping.return_value = True
        mock_cd.scan_stream.side_effect = socket.timeout("Scan timeout")

        file = SimpleUploadedFile('large.zip', b'x' * 1000000)

        # Timeout should be caught and fail open (allow upload)
        result = VirusScannerService.scan_file(file, timeout=5)

        # Should fail open with error
        assert result['safe'] is True
        assert result['engine'] == 'error'
        assert 'error' in result
