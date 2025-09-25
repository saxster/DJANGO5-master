# Wrapper file to maintain backward compatibility
# Imports from the fallback version
from .asset_queries_with_fallback import AssetQueriesWithFallback

# Alias for backward compatibility
AssetQueries = AssetQueriesWithFallback

# Export both names
__all__ = ['AssetQueries', 'AssetQueriesWithFallback']