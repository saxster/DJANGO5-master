"""
Base LLM interfaces and unified adapter for AI Mentor system.

This module provides a consistent interface for different LLM providers
and implements the Maker/Checker dual-LLM pattern for enhanced reliability.
"""

from abc import ABC, abstractmethod
from enum import Enum
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Available LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    MOCK = "mock"


class LLMRole(Enum):
    """LLM roles in the Maker/Checker pattern."""
    MAKER = "maker"
    CHECKER = "checker"


@dataclass
class LLMRequest:
    """Represents a request to an LLM."""
    prompt: str
    context: Dict[str, Any]
    max_tokens: int = 2000
    temperature: float = 0.3
    role: LLMRole = LLMRole.MAKER
    system_message: Optional[str] = None
    examples: Optional[List[Dict[str, str]]] = None


@dataclass
class LLMResponse:
    """Represents a response from an LLM."""
    content: str
    tokens_used: int
    confidence_score: Optional[float] = None
    provider: str = ""
    role: LLMRole = LLMRole.MAKER
    metadata: Dict[str, Any] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_name = self.config.get('name', 'unknown')

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and configured."""
        pass

    @abstractmethod
    def estimate_cost(self, request: LLMRequest) -> float:
        """Estimate the cost of a request in USD."""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key') or getattr(settings, 'OPENAI_API_KEY', None)
        self.model = config.get('model', 'gpt-4')
        self.base_url = config.get('base_url', 'https://api.openai.com/v1')

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using OpenAI API."""
        if not self.is_available():
            return LLMResponse(
                content="",
                tokens_used=0,
                provider=self.provider_name,
                role=request.role,
                error="OpenAI provider not available"
            )

        try:
            import openai

            messages = []

            # Add system message
            if request.system_message:
                messages.append({"role": "system", "content": request.system_message})

            # Add examples if provided
            if request.examples:
                for example in request.examples:
                    messages.append({"role": "user", "content": example.get("user", "")})
                    messages.append({"role": "assistant", "content": example.get("assistant", "")})

            # Add main prompt with context
            prompt_with_context = request.prompt
            if request.context:
                context_str = json.dumps(request.context, indent=2)
                prompt_with_context = f"Context:\n{context_str}\n\nRequest:\n{request.prompt}"

            messages.append({"role": "user", "content": prompt_with_context})

            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                tokens_used=response.usage.total_tokens,
                provider=self.provider_name,
                role=request.role,
                confidence_score=self._calculate_confidence(response),
                metadata={
                    'model': self.model,
                    'finish_reason': response.choices[0].finish_reason
                }
            )

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"OpenAI API error: {e}")
            return LLMResponse(
                content="",
                tokens_used=0,
                provider=self.provider_name,
                role=request.role,
                error=str(e)
            )

    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        try:
            import openai
            return bool(self.api_key)
        except ImportError:
            return False

    def estimate_cost(self, request: LLMRequest) -> float:
        """Estimate cost based on token usage."""
        # Rough estimation for GPT-4
        estimated_tokens = len(request.prompt.split()) * 1.3  # Rough token estimation
        cost_per_1k_tokens = 0.03  # Approximate cost for GPT-4
        return (estimated_tokens / 1000) * cost_per_1k_tokens

    def _calculate_confidence(self, response) -> float:
        """Calculate confidence score based on response metadata."""
        # Simple heuristic based on finish reason and content length
        if response.choices[0].finish_reason == 'stop':
            content_length = len(response.choices[0].message.content)
            if content_length > 100:
                return 0.9
            elif content_length > 50:
                return 0.8
            else:
                return 0.7
        return 0.6


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key') or getattr(settings, 'ANTHROPIC_API_KEY', None)
        self.model = config.get('model', 'claude-3-sonnet-20240229')

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using Anthropic API."""
        if not self.is_available():
            return LLMResponse(
                content="",
                tokens_used=0,
                provider=self.provider_name,
                role=request.role,
                error="Anthropic provider not available"
            )

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)

            # Prepare prompt with context
            prompt_with_context = request.prompt
            if request.context:
                context_str = json.dumps(request.context, indent=2)
                prompt_with_context = f"Context:\n{context_str}\n\nRequest:\n{request.prompt}"

            response = client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=request.system_message or "You are a helpful AI coding assistant.",
                messages=[{"role": "user", "content": prompt_with_context}]
            )

            return LLMResponse(
                content=response.content[0].text,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                provider=self.provider_name,
                role=request.role,
                confidence_score=0.85,  # Claude generally has high confidence
                metadata={
                    'model': self.model,
                    'stop_reason': response.stop_reason
                }
            )

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Anthropic API error: {e}")
            return LLMResponse(
                content="",
                tokens_used=0,
                provider=self.provider_name,
                role=request.role,
                error=str(e)
            )

    def is_available(self) -> bool:
        """Check if Anthropic is available."""
        try:
            import anthropic
            return bool(self.api_key)
        except ImportError:
            return False

    def estimate_cost(self, request: LLMRequest) -> float:
        """Estimate cost for Anthropic API."""
        estimated_tokens = len(request.prompt.split()) * 1.3
        cost_per_1k_tokens = 0.015  # Approximate cost for Claude
        return (estimated_tokens / 1000) * cost_per_1k_tokens


class MockProvider(BaseLLMProvider):
    """Mock LLM provider for testing and development."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.mock_responses = config.get('responses', {})

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate mock response."""
        # Simple keyword-based mock responses
        prompt_lower = request.prompt.lower()

        mock_content = "This is a mock response for testing."

        if "plan" in prompt_lower:
            mock_content = json.dumps({
                "plan_id": "mock_plan_123",
                "steps": [
                    {"description": "Mock step 1", "risk": "low"},
                    {"description": "Mock step 2", "risk": "medium"}
                ],
                "overall_risk": "medium"
            }, indent=2)
        elif "patch" in prompt_lower:
            mock_content = "```python\n# Mock patch\ndef improved_function():\n    return 'better implementation'\n```"
        elif "explain" in prompt_lower:
            mock_content = "This code does the following:\n1. Mock explanation point 1\n2. Mock explanation point 2"

        return LLMResponse(
            content=mock_content,
            tokens_used=100,
            provider=self.provider_name,
            role=request.role,
            confidence_score=0.5,
            metadata={"mock": True}
        )

    def is_available(self) -> bool:
        """Mock provider is always available."""
        return True

    def estimate_cost(self, request: LLMRequest) -> float:
        """Mock provider has no cost."""
        return 0.0


class LLMManager:
    """Manager for LLM providers with Maker/Checker pattern support."""

    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {}
        self.default_provider = None
        self.maker_provider = None
        self.checker_provider = None

        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize LLM providers based on configuration."""
        llm_config = getattr(settings, 'MENTOR_LLM_CONFIG', {})

        # Initialize providers
        providers_config = llm_config.get('providers', {})

        if 'openai' in providers_config:
            self.providers['openai'] = OpenAIProvider(providers_config['openai'])

        if 'anthropic' in providers_config:
            self.providers['anthropic'] = AnthropicProvider(providers_config['anthropic'])

        # Always include mock provider for testing
        self.providers['mock'] = MockProvider(providers_config.get('mock', {}))

        # Set default provider
        default_name = llm_config.get('default_provider', 'mock')
        self.default_provider = self.providers.get(default_name)

        # Set Maker/Checker providers
        maker_name = llm_config.get('maker_provider', default_name)
        checker_name = llm_config.get('checker_provider', default_name)

        self.maker_provider = self.providers.get(maker_name)
        self.checker_provider = self.providers.get(checker_name)

    def generate(self, request: LLMRequest, provider_name: Optional[str] = None) -> LLMResponse:
        """Generate response using specified or default provider."""
        if provider_name:
            provider = self.providers.get(provider_name)
        elif request.role == LLMRole.MAKER:
            provider = self.maker_provider
        elif request.role == LLMRole.CHECKER:
            provider = self.checker_provider
        else:
            provider = self.default_provider

        if not provider:
            return LLMResponse(
                content="",
                tokens_used=0,
                role=request.role,
                error="No suitable provider available"
            )

        return provider.generate(request)

    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return [name for name, provider in self.providers.items() if provider.is_available()]

    def estimate_cost(self, request: LLMRequest, provider_name: Optional[str] = None) -> float:
        """Estimate cost for a request."""
        provider = self.providers.get(provider_name) or self.default_provider
        if provider:
            return provider.estimate_cost(request)
        return 0.0


# Global LLM manager instance
llm_manager = LLMManager()