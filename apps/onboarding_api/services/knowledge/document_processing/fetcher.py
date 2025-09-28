import base64
import hashlib
import logging
import requests
from datetime import datetime
from typing import Dict
from django.conf import settings

from apps.onboarding.models import KnowledgeSource
from ..exceptions import SecurityError, DocumentFetchError
from ..security.url_validator import URLValidator
from ..security.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class DocumentFetcher:
    """
    Secure document fetcher with allowlist validation and content verification
    """

    def __init__(self):
        self.allowed_domains = getattr(settings, 'KB_ALLOWED_SOURCES', [
            'iso.org',
            'nist.gov',
            'asis.org',
            'wikipedia.org',
            'example.com'
        ])

        self.max_file_size = getattr(settings, 'KB_MAX_FILE_SIZE', 50 * 1024 * 1024)
        self.request_timeout = getattr(settings, 'KB_FETCH_TIMEOUT', 30)
        self.user_agent = f"IntelliWiz-KB-Fetcher/1.0 (+https://{getattr(settings, 'ALLOWED_HOSTS', ['localhost'])[0]}/kb/about)"

        self.rate_limit_delay = getattr(settings, 'KB_RATE_LIMIT_DELAY', 1.0)

        self.allowed_content_types = {
            'application/pdf',
            'text/html',
            'text/plain',
            'application/json',
            'application/xml',
            'text/xml'
        }

        self.url_validator = URLValidator(self.allowed_domains)
        self.rate_limiter = RateLimiter(self.rate_limit_delay)

    def fetch_document(self, source_url: str, knowledge_source: KnowledgeSource) -> Dict[str, any]:
        """Fetch document with security validation and content verification"""
        logger.info(f"Starting document fetch from {source_url}")

        try:
            self.url_validator.validate_url_security(source_url)
            self.rate_limiter.enforce_rate_limit(source_url)

            if not self.url_validator.check_robots_txt(source_url, self.user_agent):
                raise SecurityError(f"Robots.txt disallows fetching from {source_url}")

            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/pdf,text/plain,application/json,application/xml',
                'Accept-Language': 'en-US,en;q=0.9',
            }

            if knowledge_source.auth_config:
                headers.update(self._prepare_auth_headers(knowledge_source.auth_config))

            response = requests.get(
                source_url,
                headers=headers,
                timeout=self.request_timeout,
                stream=True,
                verify=True
            )
            response.raise_for_status()

            self._validate_response(response, source_url)

            content = self._read_content_safely(response)

            content_hash = hashlib.sha256(content).hexdigest()

            metadata = self._extract_metadata(response, source_url)

            logger.info(f"Successfully fetched document from {source_url} ({len(content)} bytes)")

            return {
                'content': content,
                'content_hash': content_hash,
                'content_type': response.headers.get('content-type', 'unknown'),
                'metadata': metadata,
                'fetch_timestamp': datetime.now(),
                'source_url': source_url,
                'status_code': response.status_code
            }

        except requests.RequestException as e:
            logger.error(f"Network error fetching document from {source_url}: {str(e)}")
            raise DocumentFetchError(f"Failed to fetch document: {str(e)}")
        except (ValueError, TypeError) as e:
            logger.error(f"Data error fetching document from {source_url}: {str(e)}")
            raise DocumentFetchError(f"Invalid data: {str(e)}")

    def _prepare_auth_headers(self, auth_config: Dict) -> Dict[str, str]:
        """Prepare authentication headers from configuration"""
        headers = {}

        if auth_config.get('type') == 'bearer_token':
            headers['Authorization'] = f"Bearer {auth_config.get('token')}"
        elif auth_config.get('type') == 'api_key':
            key_header = auth_config.get('header', 'X-API-Key')
            headers[key_header] = auth_config.get('key')
        elif auth_config.get('type') == 'basic_auth':
            credentials = f"{auth_config.get('username')}:{auth_config.get('password')}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded}"

        return headers

    def _validate_response(self, response: requests.Response, url: str):
        """Validate HTTP response for security and content"""
        content_type = response.headers.get('content-type', '').split(';')[0].lower()
        if content_type not in self.allowed_content_types:
            raise SecurityError(f"Disallowed content type: {content_type}")

        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > self.max_file_size:
            raise SecurityError(f"Content too large: {content_length} bytes (max: {self.max_file_size})")

    def _read_content_safely(self, response: requests.Response) -> bytes:
        """Read response content with size limits"""
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > self.max_file_size:
                raise SecurityError(f"Content exceeds size limit: {len(content)} bytes")
        return content

    def _extract_metadata(self, response: requests.Response, url: str) -> Dict[str, any]:
        """Extract metadata from HTTP response"""
        return {
            'last_modified': response.headers.get('last-modified'),
            'etag': response.headers.get('etag'),
            'content_encoding': response.headers.get('content-encoding'),
            'server': response.headers.get('server'),
            'cache_control': response.headers.get('cache-control'),
            'content_language': response.headers.get('content-language'),
            'final_url': response.url,
            'response_headers': dict(response.headers)
        }