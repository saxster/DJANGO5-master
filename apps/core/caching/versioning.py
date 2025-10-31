"""
Cache versioning system for schema-aware cache invalidation.

Implements cache versioning to prevent stale data after schema changes.
Complies with .claude/rules.md - file size < 200 lines, specific exceptions.
"""

import logging
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import DatabaseError

logger = logging.getLogger(__name__)

__all__ = [
    'CacheVersionManager',
    'get_versioned_cache_key',
    'bump_cache_version',
    'clear_old_version_caches',
]


class CacheVersionManager:
    """
    Manages cache versioning to handle schema changes gracefully.

    Features:
    - Automatic version integration into cache keys
    - Migration path for version bumps
    - Old version cleanup
    """

    VERSION_KEY = 'cache:global:version'
    VERSION_HISTORY_KEY = 'cache:version:history'

    def __init__(self):
        self.current_version = self._load_current_version()

    def _load_current_version(self) -> str:
        """Load current cache version from settings or cache"""
        try:
            # Check if cache backend is available before attempting operations
            if not hasattr(cache, '_cache') and not hasattr(cache, 'get'):
                logger.debug("Cache backend not fully initialized, using default version")
                return '1.0'

            try:
                cached_version = cache.get(self.VERSION_KEY)
                if cached_version and isinstance(cached_version, str):
                    return cached_version
            except (AttributeError, TypeError, ConnectionError) as inner_e:
                # Cache.get() failed - likely Redis unavailable or MaterializedView backend
                logger.debug(f"Cache retrieval failed: {inner_e}, using default version")
                return '1.0'

            # No cached version found, use settings default
            settings_version = getattr(settings, 'CACHE_VERSION', '1.0')

            try:
                cache.set(self.VERSION_KEY, settings_version, timeout=None)
                logger.info(f"Initialized cache version: {settings_version}")
            except (AttributeError, TypeError, ConnectionError):
                # Cache.set() failed - not critical, just continue with default
                logger.debug("Could not cache version in backend, using in-memory default")

            return settings_version
        except (AttributeError, ValueError, TypeError, ConnectionError) as e:
            logger.debug(f"Error loading cache version: {e}, using default")
            return '1.0'

    def get_version(self) -> str:
        """Get current cache version"""
        return self.current_version

    def bump_version(self, new_version: Optional[str] = None) -> Dict[str, Any]:
        """Bump cache version and invalidate old caches"""
        try:
            old_version = self.current_version
            self.current_version = new_version if new_version else self._increment_version(old_version)
            cache.set(self.VERSION_KEY, self.current_version, timeout=None)
            self._record_version_change(old_version, self.current_version)
            logger.warning(f"Cache version bumped: {old_version} -> {self.current_version}", extra={'old_version': old_version, 'new_version': self.current_version})
            return {'success': True, 'old_version': old_version, 'new_version': self.current_version, 'message': f'Version bumped: {old_version} -> {self.current_version}'}
        except (ValueError, TypeError) as e:
            logger.error(f"Error bumping cache version: {e}")
            return {'success': False, 'error': str(e)}

    def _increment_version(self, version: str) -> str:
        """Auto-increment version number"""
        try:
            parts = version.split('.')
            major, minor = int(parts[0]), int(parts[1])
            return f"{major}.{minor + 1}"
        except (ValueError, IndexError):
            return '2.0'

    def _record_version_change(self, old_version: str, new_version: str):
        """Record version change in history"""
        try:
            history = cache.get(self.VERSION_HISTORY_KEY, [])
            history.append({'old': old_version, 'new': new_version, 'ts': str(timezone.now())})
            cache.set(self.VERSION_HISTORY_KEY, history[-100:], timeout=None)
        except (AttributeError, TypeError) as e:
            logger.warning(f"Could not record version history: {e}")

    def get_version_history(self) -> list:
        """Get version change history"""
        return cache.get(self.VERSION_HISTORY_KEY, [])


cache_version_manager = CacheVersionManager()


def get_versioned_cache_key(base_key: str, include_version: bool = True) -> str:
    """Generate cache key with version suffix"""
    if not include_version:
        return base_key
    version = cache_version_manager.get_version()
    return f"{base_key}:v{version}"


def bump_cache_version(new_version: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to bump global cache version"""
    return cache_version_manager.bump_version(new_version)


def clear_old_version_caches(keep_versions: int = 1) -> Dict[str, Any]:
    """Clear cache entries from old versions"""
    try:
        from apps.core.caching.utils import clear_cache_pattern
        current_version = cache_version_manager.get_version()
        history = cache_version_manager.get_version_history()
        versions_to_clear = [h['old'] for h in history[:-keep_versions]] if len(history) > keep_versions else []
        cleared_count = 0
        for old_version in versions_to_clear:
            result = clear_cache_pattern(f"*:v{old_version}")
            if result['success']:
                cleared_count += result['keys_cleared']
        logger.info(f"Cleared {cleared_count} cache keys from {len(versions_to_clear)} old versions")
        return {'success': True, 'versions_cleared': len(versions_to_clear), 'keys_cleared': cleared_count, 'current_version': current_version}
    except (ImportError, AttributeError) as e:
        logger.error(f"Error clearing old version caches: {e}")
        return {'success': False, 'error': str(e)}