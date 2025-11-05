# Wrapper file to maintain backward compatibility
# Imports from the optimized version
from .url_router_optimized import OptimizedURLRouter, URLRouter

__all__ = [
    'OptimizedURLRouter',
    'URLRouter',
]