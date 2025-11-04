import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from typing import List

from ..exceptions import SecurityError

logger = logging.getLogger(__name__)


class URLValidator:
    """
    Validates URLs against security constraints for document fetching
    """

    def __init__(self, allowed_domains: List[str]):
        self.allowed_domains = allowed_domains
        self.sensitive_domains = ['nist.gov', 'iso.org']

    def validate_url_security(self, url: str):
        """Validate URL against security constraints"""
        parsed = urlparse(url)

        if parsed.scheme not in ['https', 'http']:
            raise SecurityError(f"Unsupported protocol: {parsed.scheme}")

        if parsed.scheme == 'http' and any(domain in parsed.netloc for domain in self.sensitive_domains):
            logger.warning(f"Using HTTP for sensitive source: {url}")

        domain = parsed.netloc.lower()
        if not any(allowed_domain in domain for allowed_domain in self.allowed_domains):
            raise SecurityError(f"Domain {domain} not in allowlist: {self.allowed_domains}")

        if any(pattern in url.lower() for pattern in ['.exe', '.bat', '.sh', 'javascript:', 'data:']):
            raise SecurityError(f"Suspicious URL pattern detected: {url}")

    def check_robots_txt(self, url: str, user_agent: str) -> bool:
        """Check robots.txt compliance"""
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()

            return rp.can_fetch(user_agent, url)
        except (ValueError, TypeError, IOError) as e:
            logger.warning(f"Could not check robots.txt for {url}: {str(e)}")
            return True