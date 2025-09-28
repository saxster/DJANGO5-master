import time
import logging
from urllib.parse import urlparse
from typing import Dict

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Enforces rate limiting for document fetching by domain
    """

    def __init__(self, delay_seconds: float = 1.0):
        self.rate_limit_delay = delay_seconds
        self._last_fetch_time: Dict[str, float] = {}

    def enforce_rate_limit(self, url: str):
        """Enforce rate limiting per domain"""
        domain = urlparse(url).netloc
        now = time.time()

        if domain in self._last_fetch_time:
            time_since_last = now - self._last_fetch_time[domain]
            if time_since_last < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last
                logger.info(f"Rate limiting: sleeping {sleep_time:.1f}s for {domain}")
                time.sleep(sleep_time)

        self._last_fetch_time[domain] = now