"""
Production-grade embedding generation service with multiple providers,
cost controls, caching, and fallback mechanisms.
"""
import hashlib
import logging
import time
from abc import ABC, abstractmethod

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Result from embedding generation"""
    embedding: List[float]
    model: str
    provider: str
    token_count: int
    cost_cents: float
    latency_ms: int
    cached: bool = False


@dataclass
class ProviderConfig:
    """Configuration for an embedding provider"""
    name: str
    api_key: str
    model: str
    max_tokens: int
    cost_per_token: float
    daily_budget_cents: int
    timeout_seconds: int = 30
    retry_attempts: int = 3


class EmbeddingProviderError(Exception):
    """Exception raised when embedding provider fails"""
    pass


class BudgetExceededError(Exception):
    """Exception raised when daily budget is exceeded"""
    pass


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers"""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name

    @abstractmethod
    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding for given text"""
        pass

    @abstractmethod
    def generate_batch_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts efficiently"""
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Test if provider is accessible"""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider"""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        try:
            import openai
            self.client = openai.OpenAI(api_key=config.api_key)
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate single embedding using OpenAI"""
        start_time = time.time()

        try:
            response = self.client.embeddings.create(
                model=self.config.model,
                input=text,
                encoding_format="float"
            )

            latency_ms = int((time.time() - start_time) * 1000)
            embedding = response.data[0].embedding
            token_count = response.usage.total_tokens
            cost_cents = token_count * self.config.cost_per_token * 100

            return EmbeddingResult(
                embedding=embedding,
                model=self.config.model,
                provider=self.name,
                token_count=token_count,
                cost_cents=cost_cents,
                latency_ms=latency_ms
            )

        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"OpenAI embedding failed: {str(e)}")
            raise EmbeddingProviderError(f"OpenAI error: {str(e)}")

    def generate_batch_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate multiple embeddings efficiently"""
        start_time = time.time()

        try:
            response = self.client.embeddings.create(
                model=self.config.model,
                input=texts,
                encoding_format="float"
            )

            latency_ms = int((time.time() - start_time) * 1000)
            results = []

            for i, embedding_data in enumerate(response.data):
                token_count = response.usage.total_tokens // len(texts)  # Approximate
                cost_cents = token_count * self.config.cost_per_token * 100

                results.append(EmbeddingResult(
                    embedding=embedding_data.embedding,
                    model=self.config.model,
                    provider=self.name,
                    token_count=token_count,
                    cost_cents=cost_cents,
                    latency_ms=latency_ms // len(texts)  # Approximate
                ))

            return results

        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"OpenAI batch embedding failed: {str(e)}")
            raise EmbeddingProviderError(f"OpenAI batch error: {str(e)}")

    def validate_connection(self) -> bool:
        """Test OpenAI connection"""
        try:
            # Generate a small test embedding
            self.generate_embedding("test connection")
            return True
        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError):
            return False


class AnthropicEmbeddingProvider(EmbeddingProvider):
    """Anthropic embedding provider (placeholder - they don't have embeddings API yet)"""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        logger.warning("Anthropic doesn't provide embeddings API yet. This is a placeholder.")

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Placeholder - Anthropic doesn't have embeddings yet"""
        raise EmbeddingProviderError("Anthropic embeddings not available")

    def generate_batch_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Placeholder - Anthropic doesn't have embeddings yet"""
        raise EmbeddingProviderError("Anthropic embeddings not available")

    def validate_connection(self) -> bool:
        """Placeholder validation"""
        return False


class AzureOpenAIEmbeddingProvider(EmbeddingProvider):
    """Azure OpenAI embedding provider"""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        try:
            import openai
            self.client = openai.AzureOpenAI(
                api_key=config.api_key,
                api_version=getattr(settings, 'AZURE_OPENAI_API_VERSION', '2024-02-01'),
                azure_endpoint=getattr(settings, 'AZURE_OPENAI_ENDPOINT', '')
            )
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding using Azure OpenAI"""
        start_time = time.time()

        try:
            response = self.client.embeddings.create(
                model=self.config.model,
                input=text,
                encoding_format="float"
            )

            latency_ms = int((time.time() - start_time) * 1000)
            embedding = response.data[0].embedding
            token_count = response.usage.total_tokens
            cost_cents = token_count * self.config.cost_per_token * 100

            return EmbeddingResult(
                embedding=embedding,
                model=self.config.model,
                provider=self.name,
                token_count=token_count,
                cost_cents=cost_cents,
                latency_ms=latency_ms
            )

        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Azure OpenAI embedding failed: {str(e)}")
            raise EmbeddingProviderError(f"Azure OpenAI error: {str(e)}")

    def generate_batch_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate multiple embeddings using Azure OpenAI"""
        start_time = time.time()

        try:
            response = self.client.embeddings.create(
                model=self.config.model,
                input=texts,
                encoding_format="float"
            )

            latency_ms = int((time.time() - start_time) * 1000)
            results = []

            for i, embedding_data in enumerate(response.data):
                token_count = response.usage.total_tokens // len(texts)
                cost_cents = token_count * self.config.cost_per_token * 100

                results.append(EmbeddingResult(
                    embedding=embedding_data.embedding,
                    model=self.config.model,
                    provider=self.name,
                    token_count=token_count,
                    cost_cents=cost_cents,
                    latency_ms=latency_ms // len(texts)
                ))

            return results

        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Azure OpenAI batch embedding failed: {str(e)}")
            raise EmbeddingProviderError(f"Azure OpenAI batch error: {str(e)}")

    def validate_connection(self) -> bool:
        """Test Azure OpenAI connection"""
        try:
            self.generate_embedding("test connection")
            return True
        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError):
            return False


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local/self-hosted embedding provider using sentence-transformers"""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(config.model)
            logger.info(f"Loaded local embedding model: {config.model}")
        except ImportError:
            raise ImportError("sentence-transformers not installed. Install with: pip install sentence-transformers")

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding using local model"""
        start_time = time.time()

        try:
            embedding = self.model.encode([text])[0].tolist()
            latency_ms = int((time.time() - start_time) * 1000)

            # Local models have no token costs
            return EmbeddingResult(
                embedding=embedding,
                model=self.config.model,
                provider=self.name,
                token_count=len(text.split()),  # Rough approximation
                cost_cents=0.0,  # Local models are free
                latency_ms=latency_ms
            )

        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Local embedding failed: {str(e)}")
            raise EmbeddingProviderError(f"Local model error: {str(e)}")

    def generate_batch_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate multiple embeddings using local model"""
        start_time = time.time()

        try:
            embeddings = self.model.encode(texts)
            latency_ms = int((time.time() - start_time) * 1000)

            results = []
            for i, embedding in enumerate(embeddings):
                results.append(EmbeddingResult(
                    embedding=embedding.tolist(),
                    model=self.config.model,
                    provider=self.name,
                    token_count=len(texts[i].split()),
                    cost_cents=0.0,
                    latency_ms=latency_ms // len(texts)
                ))

            return results

        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Local batch embedding failed: {str(e)}")
            raise EmbeddingProviderError(f"Local batch error: {str(e)}")

    def validate_connection(self) -> bool:
        """Test local model"""
        try:
            self.generate_embedding("test connection")
            return True
        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError):
            return False


class CostTracker:
    """Track embedding costs and enforce budgets"""

    def __init__(self):
        self.cache_timeout = 86400  # 24 hours

    def get_daily_spend(self, provider: str) -> float:
        """Get today's spending for a provider in cents"""
        today = timezone.now().date().isoformat()
        cache_key = f"embedding_spend:{provider}:{today}"
        return cache.get(cache_key, 0.0)

    def record_spend(self, provider: str, cost_cents: float):
        """Record spending for a provider"""
        today = timezone.now().date().isoformat()
        cache_key = f"embedding_spend:{provider}:{today}"

        current_spend = cache.get(cache_key, 0.0)
        new_spend = current_spend + cost_cents
        cache.set(cache_key, new_spend, self.cache_timeout)

        logger.info(f"Recorded ${cost_cents/100:.4f} spend for {provider}. Daily total: ${new_spend/100:.2f}")

    def check_budget(self, provider: str, budget_cents: int, cost_cents: float) -> bool:
        """Check if spending this amount would exceed budget"""
        daily_spend = self.get_daily_spend(provider)
        return (daily_spend + cost_cents) <= budget_cents

    def get_remaining_budget(self, provider: str, budget_cents: int) -> float:
        """Get remaining budget for provider in cents"""
        daily_spend = self.get_daily_spend(provider)
        return max(0, budget_cents - daily_spend)


class ProductionEmbeddingService:
    """
    Production-grade embedding service with multiple providers,
    cost controls, caching, and intelligent fallback mechanisms.
    """

    def __init__(self):
        self.providers: Dict[str, EmbeddingProvider] = {}
        self.cost_tracker = CostTracker()
        self.cache_timeout = getattr(settings, 'EMBEDDING_CACHE_TIMEOUT', 3600 * 24)  # 24 hours
        self.fallback_order = getattr(settings, 'EMBEDDING_FALLBACK_ORDER', ['openai', 'azure', 'local'])

        # Initialize providers from settings
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize embedding providers from Django settings"""
        provider_configs = getattr(settings, 'EMBEDDING_PROVIDERS', {})

        for provider_name, config in provider_configs.items():
            try:
                provider_config = ProviderConfig(
                    name=provider_name,
                    api_key=config.get('api_key', ''),
                    model=config.get('model', ''),
                    max_tokens=config.get('max_tokens', 8192),
                    cost_per_token=config.get('cost_per_token', 0.0001),
                    daily_budget_cents=config.get('daily_budget_cents', 1000),  # $10 default
                    timeout_seconds=config.get('timeout_seconds', 30),
                    retry_attempts=config.get('retry_attempts', 3)
                )

                if provider_name == 'openai':
                    provider = OpenAIEmbeddingProvider(provider_config)
                elif provider_name == 'azure':
                    provider = AzureOpenAIEmbeddingProvider(provider_config)
                elif provider_name == 'anthropic':
                    provider = AnthropicEmbeddingProvider(provider_config)
                elif provider_name == 'local':
                    provider = LocalEmbeddingProvider(provider_config)
                else:
                    logger.warning(f"Unknown provider type: {provider_name}")
                    continue

                # Test connection
                if provider.validate_connection():
                    self.providers[provider_name] = provider
                    logger.info(f"Initialized embedding provider: {provider_name}")
                else:
                    logger.warning(f"Failed to validate provider: {provider_name}")

            except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Failed to initialize provider {provider_name}: {str(e)}")

        # Ensure we have at least one working provider
        if not self.providers:
            logger.warning("No embedding providers available, falling back to dummy provider")
            # Create a fallback dummy provider
            self._create_dummy_fallback()

    def _create_dummy_fallback(self):
        """Create a dummy provider as absolute fallback"""
        from ..services.knowledge import DummyEmbeddingGenerator

        class DummyProvider(EmbeddingProvider):
            def __init__(self):
                self.name = 'dummy'
                self.dummy_gen = DummyEmbeddingGenerator()

            def generate_embedding(self, text: str) -> EmbeddingResult:
                embedding = self.dummy_gen.generate_embedding(text)
                return EmbeddingResult(
                    embedding=embedding,
                    model='dummy',
                    provider='dummy',
                    token_count=len(text.split()),
                    cost_cents=0.0,
                    latency_ms=10
                )

            def generate_batch_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
                return [self.generate_embedding(text) for text in texts]

            def validate_connection(self) -> bool:
                return True

        self.providers['dummy'] = DummyProvider()
        logger.info("Created dummy fallback provider")

    def _get_cache_key(self, text: str, model: str = None) -> str:
        """Generate cache key for embedding"""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        model_suffix = f":{model}" if model else ""
        return f"embedding:{text_hash}{model_suffix}"

    def _get_from_cache(self, cache_key: str) -> Optional[EmbeddingResult]:
        """Get embedding from cache"""
        cached_data = cache.get(cache_key)
        if cached_data:
            # Reconstruct EmbeddingResult
            cached_data['cached'] = True
            return EmbeddingResult(**cached_data)
        return None

    def _store_in_cache(self, cache_key: str, result: EmbeddingResult):
        """Store embedding result in cache"""
        cache_data = {
            'embedding': result.embedding,
            'model': result.model,
            'provider': result.provider,
            'token_count': result.token_count,
            'cost_cents': result.cost_cents,
            'latency_ms': result.latency_ms,
            'cached': False
        }
        cache.set(cache_key, cache_data, self.cache_timeout)

    def generate_embedding(self, text: str, preferred_provider: str = None) -> EmbeddingResult:
        """
        Generate embedding with caching, cost controls, and fallbacks

        Args:
            text: Text to embed
            preferred_provider: Preferred provider name (optional)

        Returns:
            EmbeddingResult with embedding and metadata
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Check cache first
        cache_key = self._get_cache_key(text)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for embedding: {text[:50]}...")
            return cached_result

        # Determine provider order
        if preferred_provider and preferred_provider in self.providers:
            provider_order = [preferred_provider] + [p for p in self.fallback_order if p != preferred_provider]
        else:
            provider_order = self.fallback_order

        last_error = None

        # Try providers in order
        for provider_name in provider_order:
            if provider_name not in self.providers:
                continue

            provider = self.providers[provider_name]

            try:
                # Check budget before making API call
                estimated_cost = self._estimate_cost(text, provider)
                if not self.cost_tracker.check_budget(provider_name, provider.config.daily_budget_cents, estimated_cost):
                    logger.warning(f"Budget exceeded for provider {provider_name}, trying next provider")
                    continue

                # Generate embedding
                result = provider.generate_embedding(text)

                # Record cost
                self.cost_tracker.record_spend(provider_name, result.cost_cents)

                # Cache result
                self._store_in_cache(cache_key, result)

                logger.debug(f"Generated embedding using {provider_name}: {text[:50]}...")
                return result

            except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
                last_error = e
                logger.warning(f"Provider {provider_name} failed: {str(e)}")
                continue

        # All providers failed
        if last_error:
            raise EmbeddingProviderError(f"All providers failed. Last error: {str(last_error)}")
        else:
            raise EmbeddingProviderError("No available providers")

    def generate_batch_embeddings(self, texts: List[str], preferred_provider: str = None) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts efficiently"""
        if not texts:
            return []

        results = []
        uncached_texts = []
        uncached_indices = []

        # Check cache for each text
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                results.append((i, cached_result))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Generate embeddings for uncached texts
        if uncached_texts:
            provider_order = ([preferred_provider] + [p for p in self.fallback_order if p != preferred_provider]) \
                            if preferred_provider and preferred_provider in self.providers \
                            else self.fallback_order

            for provider_name in provider_order:
                if provider_name not in self.providers:
                    continue

                provider = self.providers[provider_name]

                try:
                    # Check budget
                    total_estimated_cost = sum(self._estimate_cost(text, provider) for text in uncached_texts)
                    if not self.cost_tracker.check_budget(provider_name, provider.config.daily_budget_cents, total_estimated_cost):
                        logger.warning(f"Budget exceeded for batch on provider {provider_name}")
                        continue

                    # Generate batch embeddings
                    batch_results = provider.generate_batch_embeddings(uncached_texts)

                    # Record costs and cache results
                    total_cost = sum(result.cost_cents for result in batch_results)
                    self.cost_tracker.record_spend(provider_name, total_cost)

                    for j, result in enumerate(batch_results):
                        cache_key = self._get_cache_key(uncached_texts[j])
                        self._store_in_cache(cache_key, result)
                        results.append((uncached_indices[j], result))

                    break  # Success, no need to try other providers

                except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
                    logger.warning(f"Batch provider {provider_name} failed: {str(e)}")
                    continue
            else:
                # All providers failed for batch, fall back to individual
                logger.warning("Batch embedding failed, falling back to individual embeddings")
                for i, text in zip(uncached_indices, uncached_texts):
                    try:
                        result = self.generate_embedding(text, preferred_provider)
                        results.append((i, result))
                    except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
                        logger.error(f"Failed to generate embedding for text {i}: {str(e)}")
                        # Create a dummy result to maintain order
                        dummy_result = EmbeddingResult(
                            embedding=[0.0] * 384,  # Standard dimension
                            model='error',
                            provider='error',
                            token_count=0,
                            cost_cents=0.0,
                            latency_ms=0
                        )
                        results.append((i, dummy_result))

        # Sort results by original index and return just the EmbeddingResult objects
        results.sort(key=lambda x: x[0])
        return [result for _, result in results]

    def _estimate_cost(self, text: str, provider: EmbeddingProvider) -> float:
        """Estimate cost for embedding this text"""
        estimated_tokens = len(text.split()) * 1.3  # Rough approximation
        return estimated_tokens * provider.config.cost_per_token * 100

    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status and budget information for all providers"""
        status = {}

        for name, provider in self.providers.items():
            daily_spend = self.cost_tracker.get_daily_spend(name)
            remaining_budget = self.cost_tracker.get_remaining_budget(name, provider.config.daily_budget_cents)

            status[name] = {
                'available': provider.validate_connection(),
                'model': getattr(provider.config, 'model', 'unknown'),
                'daily_spend_cents': daily_spend,
                'daily_budget_cents': getattr(provider.config, 'daily_budget_cents', 0),
                'remaining_budget_cents': remaining_budget,
                'budget_utilization_pct': (daily_spend / max(1, provider.config.daily_budget_cents)) * 100
            }

        return status

    def get_recommended_provider(self) -> Optional[str]:
        """Get the recommended provider based on availability and budget"""
        for provider_name in self.fallback_order:
            if provider_name not in self.providers:
                continue

            provider = self.providers[provider_name]

            # Check if provider is available
            if not provider.validate_connection():
                continue

            # Check budget utilization
            daily_spend = self.cost_tracker.get_daily_spend(provider_name)
            budget_utilization = (daily_spend / max(1, provider.config.daily_budget_cents)) * 100

            # Prefer providers with <80% budget utilization
            if budget_utilization < 80:
                return provider_name

        # If no provider has good budget, return first available
        for provider_name in self.fallback_order:
            if provider_name in self.providers and self.providers[provider_name].validate_connection():
                return provider_name

        return None


# Singleton instance
_production_embedding_service = None


def get_production_embedding_service() -> ProductionEmbeddingService:
    """Get singleton instance of production embedding service"""
    global _production_embedding_service
    if _production_embedding_service is None:
        _production_embedding_service = ProductionEmbeddingService()
    return _production_embedding_service


def get_embedding_service():
    """Factory function to get the appropriate embedding service"""
    # Check if production embeddings are enabled
    if getattr(settings, 'ENABLE_PRODUCTION_EMBEDDINGS', False):
        return get_production_embedding_service()
    else:
        # Fall back to existing enhanced embedding generator
        from .knowledge import EnhancedEmbeddingGenerator
        return EnhancedEmbeddingGenerator()