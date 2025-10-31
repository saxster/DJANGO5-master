"""
Custom exceptions for LLM services.

Following CLAUDE.md Rule #11: Use specific exception types from patterns.
"""


class LLMServiceException(Exception):
    """Base exception for LLM service errors."""
    pass


class LLMValidationError(LLMServiceException):
    """Raised when LLM output validation fails."""
    pass


class LLMKnowledgeError(LLMServiceException):
    """Raised when knowledge base operations fail."""
    pass


class LLMConsensusError(LLMServiceException):
    """Raised when consensus creation fails."""
    pass


class QuotaExceededError(LLMServiceException):
    """Raised when LLM quota/rate limit is exceeded."""
    pass


class LLMProviderError(LLMServiceException):
    """Raised when LLM provider encounters an error."""
    def __init__(self, message: str, provider: str = None, operation: str = None):
        self.provider = provider
        self.operation = operation
        super().__init__(message)


class PromptTooLongError(LLMServiceException):
    """Raised when prompt exceeds provider's token limit."""
    pass


class RateLimitError(LLMServiceException):
    """Raised when rate limit is exceeded."""
    def __init__(self, provider: str, retry_after_seconds: int = None):
        self.provider = provider
        self.retry_after_seconds = retry_after_seconds
        message = f"Rate limit exceeded for provider: {provider}"
        if retry_after_seconds:
            message += f" (retry after {retry_after_seconds}s)"
        super().__init__(message)


class InvalidProviderConfigError(LLMServiceException):
    """Raised when provider configuration is invalid."""
    pass


class CircuitBreakerOpenError(LLMServiceException):
    """Raised when circuit breaker is open and requests are being blocked."""
    pass


class AllProvidersFailedError(LLMServiceException):
    """Raised when all LLM providers in fallback chain have failed."""
    def __init__(self, attempted_providers):
        self.attempted_providers = attempted_providers
        message = f"All LLM providers failed. Attempted: {', '.join(attempted_providers)}"
        super().__init__(message)
