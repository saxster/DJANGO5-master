"""
Production-grade LLM service with real provider integrations,
strict budget controls, and idempotent request handling.

Replaces dummy LLM implementations with actual provider adapters
while maintaining cost control and quality assurance.
"""
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class LLMRequest:
    """Represents an LLM request with idempotency"""
    request_id: str
    user_id: int
    client_id: int
    prompt: str
    model: str
    max_tokens: int
    temperature: float
    metadata: Dict[str, Any]
    created_at: datetime


@dataclass
class LLMResponse:
    """Represents an LLM response with cost tracking"""
    request_id: str
    response_text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_cents: float
    latency_ms: int
    quality_score: Optional[float] = None
    cached: bool = False


@dataclass
class BudgetStatus:
    """Current budget status"""
    daily_budget_cents: int
    current_spend_cents: float
    remaining_budget_cents: float
    utilization_percentage: float
    projected_daily_spend: float
    budget_exhausted: bool


class LLMProviderError(Exception):
    """Exception raised when LLM provider fails"""
    pass


class BudgetExceededError(Exception):
    """Exception raised when budget limits are exceeded"""
    pass


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.api_key = config.get('api_key', '')
        self.model = config.get('model', '')
        self.max_tokens = config.get('max_tokens', 2048)
        self.cost_per_input_token = config.get('cost_per_input_token', 0.0001)
        self.cost_per_output_token = config.get('cost_per_output_token', 0.0002)
        self.daily_budget_cents = config.get('daily_budget_cents', 1000)

    @abstractmethod
    def generate_completion(self, request: LLMRequest) -> LLMResponse:
        """Generate completion for the given request"""
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Test if provider is accessible"""
        pass

    def estimate_cost(self, prompt: str, max_tokens: int) -> float:
        """Estimate cost in cents for a request"""
        # Rough token estimation (1 token ≈ 4 characters)
        estimated_input_tokens = len(prompt) // 4
        estimated_output_tokens = min(max_tokens, 500)  # Conservative estimate

        cost_cents = (
            estimated_input_tokens * self.cost_per_input_token +
            estimated_output_tokens * self.cost_per_output_token
        ) * 100

        return cost_cents


class OpenAILLMProvider(LLMProvider):
    """OpenAI GPT provider with budget controls"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")

    def generate_completion(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using OpenAI GPT"""
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert facility management consultant helping with system configuration."},
                    {"role": "user", "content": request.prompt}
                ],
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                user=f"user_{request.user_id}_client_{request.client_id}"  # For tracking
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract response data
            choice = response.choices[0]
            response_text = choice.message.content
            usage = response.usage

            # Calculate actual cost
            cost_cents = (
                usage.prompt_tokens * self.cost_per_input_token +
                usage.completion_tokens * self.cost_per_output_token
            ) * 100

            return LLMResponse(
                request_id=request.request_id,
                response_text=response_text,
                provider=self.name,
                model=self.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cost_cents=cost_cents,
                latency_ms=latency_ms
            )

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"OpenAI completion failed: {str(e)}")
            raise LLMProviderError(f"OpenAI error: {str(e)}")

    def validate_connection(self) -> bool:
        """Test OpenAI connection"""
        try:
            # Make a minimal test request
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test connection"}],
                max_tokens=5
            )
            return bool(response.choices)
        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError):
            return False


class AnthropicLLMProvider(LLMProvider):
    """Anthropic Claude provider with budget controls"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("Anthropic package not installed. Install with: pip install anthropic")

    def generate_completion(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using Anthropic Claude"""
        start_time = time.time()

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                messages=[
                    {"role": "user", "content": request.prompt}
                ]
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract response data
            response_text = response.content[0].text
            usage = response.usage

            # Calculate actual cost
            cost_cents = (
                usage.input_tokens * self.cost_per_input_token +
                usage.output_tokens * self.cost_per_output_token
            ) * 100

            return LLMResponse(
                request_id=request.request_id,
                response_text=response_text,
                provider=self.name,
                model=self.model,
                prompt_tokens=usage.input_tokens,
                completion_tokens=usage.output_tokens,
                total_tokens=usage.input_tokens + usage.output_tokens,
                cost_cents=cost_cents,
                latency_ms=latency_ms
            )

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Anthropic completion failed: {str(e)}")
            raise LLMProviderError(f"Anthropic error: {str(e)}")

    def validate_connection(self) -> bool:
        """Test Anthropic connection"""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=5,
                messages=[{"role": "user", "content": "Test"}]
            )
            return bool(response.content)
        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError):
            return False


class AzureOpenAILLMProvider(LLMProvider):
    """Azure OpenAI provider with budget controls"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        try:
            import openai
            self.client = openai.AzureOpenAI(
                api_key=self.api_key,
                api_version=config.get('api_version', '2024-02-01'),
                azure_endpoint=config.get('azure_endpoint', '')
            )
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")

    def generate_completion(self, request: LLMRequest) -> LLMResponse:
        """Generate completion using Azure OpenAI"""
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert facility management consultant."},
                    {"role": "user", "content": request.prompt}
                ],
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract response data
            choice = response.choices[0]
            response_text = choice.message.content
            usage = response.usage

            # Calculate actual cost
            cost_cents = (
                usage.prompt_tokens * self.cost_per_input_token +
                usage.completion_tokens * self.cost_per_output_token
            ) * 100

            return LLMResponse(
                request_id=request.request_id,
                response_text=response_text,
                provider=self.name,
                model=self.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cost_cents=cost_cents,
                latency_ms=latency_ms
            )

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Azure OpenAI completion failed: {str(e)}")
            raise LLMProviderError(f"Azure OpenAI error: {str(e)}")

    def validate_connection(self) -> bool:
        """Test Azure OpenAI connection"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            return bool(response.choices)
        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError):
            return False


class BudgetManager:
    """Manages LLM spending budgets and enforcement"""

    def __init__(self):
        self.cache_timeout = 86400  # 24 hours
        self.alert_thresholds = [0.5, 0.8, 0.95]  # 50%, 80%, 95%

    def get_budget_status(self, provider: str) -> BudgetStatus:
        """Get current budget status for a provider"""
        today = timezone.now().date().isoformat()
        spend_key = f"llm_spend:{provider}:{today}"
        budget_key = f"llm_budget:{provider}"

        current_spend = cache.get(spend_key, 0.0)
        daily_budget = cache.get(budget_key, 1000.0)  # Default $10

        remaining = max(0, daily_budget - current_spend)
        utilization = (current_spend / daily_budget) if daily_budget > 0 else 0.0
        exhausted = remaining <= 0

        # Project daily spend based on current rate
        now = timezone.now()
        minutes_since_midnight = (now.hour * 60) + now.minute
        projected_daily = (current_spend * 1440) / max(1, minutes_since_midnight) if minutes_since_midnight > 0 else current_spend

        return BudgetStatus(
            daily_budget_cents=int(daily_budget),
            current_spend_cents=current_spend,
            remaining_budget_cents=remaining,
            utilization_percentage=utilization * 100,
            projected_daily_spend=projected_daily,
            budget_exhausted=exhausted
        )

    def record_spend(self, provider: str, cost_cents: float, request_metadata: Dict[str, Any] = None):
        """Record spending for budget tracking"""
        today = timezone.now().date().isoformat()
        spend_key = f"llm_spend:{provider}:{today}"

        current_spend = cache.get(spend_key, 0.0)
        new_spend = current_spend + cost_cents
        cache.set(spend_key, new_spend, self.cache_timeout)

        # Check for budget alerts
        self._check_budget_alerts(provider, new_spend)

        logger.info(f"Recorded ${cost_cents/100:.4f} LLM spend for {provider}. Daily total: ${new_spend/100:.2f}")

    def check_budget_availability(self, provider: str, estimated_cost_cents: float) -> Tuple[bool, str]:
        """Check if spending is within budget"""
        status = self.get_budget_status(provider)

        if status.budget_exhausted:
            return False, f"Daily budget exhausted for {provider}"

        if status.remaining_budget_cents < estimated_cost_cents:
            return False, f"Insufficient budget: need ${estimated_cost_cents/100:.2f}, have ${status.remaining_budget_cents/100:.2f}"

        return True, "Budget available"

    def _check_budget_alerts(self, provider: str, current_spend: float):
        """Check if budget alerts should be triggered"""
        status = self.get_budget_status(provider)

        for threshold in self.alert_thresholds:
            if status.utilization_percentage >= threshold * 100:
                alert_key = f"budget_alert:{provider}:{threshold}:{timezone.now().date().isoformat()}"

                # Only send alert once per day per threshold
                if not cache.get(alert_key):
                    self._send_budget_alert(provider, threshold, status)
                    cache.set(alert_key, True, self.cache_timeout)

    def _send_budget_alert(self, provider: str, threshold: float, status: BudgetStatus):
        """Send budget alert notification"""
        try:
            from .notifications import get_notification_service, NotificationEvent

            notification_service = get_notification_service()

            event = NotificationEvent(
                event_type='budget_alert',
                event_id=f"budget_{provider}_{threshold}_{timezone.now().date().isoformat()}",
                title=f"LLM Budget Alert - {provider}",
                message=f"LLM spending for {provider} has reached {threshold:.0%} of daily budget. "
                       f"Current: ${status.current_spend_cents/100:.2f}, Budget: ${status.daily_budget_cents/100:.2f}",
                priority='high' if threshold >= 0.8 else 'medium',
                metadata={
                    'provider': provider,
                    'threshold': threshold,
                    'current_spend': status.current_spend_cents,
                    'daily_budget': status.daily_budget_cents,
                    'utilization': status.utilization_percentage
                },
                timestamp=timezone.now()
            )

            notification_service.send_notification(event)

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Failed to send budget alert: {str(e)}")


class IdempotencyManager:
    """Manages idempotent LLM requests"""

    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
        self.key_prefix = "llm_idempotency"

    def generate_request_id(self, user_id: int, prompt: str, model: str) -> str:
        """Generate deterministic request ID"""
        # Include date to allow daily resets
        date_str = timezone.now().date().isoformat()
        key_components = [str(user_id), prompt, model, date_str]
        key_string = ":".join(key_components)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
        return f"{self.key_prefix}:{key_hash}"

    def check_cached_response(self, request_id: str) -> Optional[LLMResponse]:
        """Check for cached response"""
        cached_data = cache.get(request_id)
        if cached_data:
            # Reconstruct LLMResponse from cached data
            cached_data['cached'] = True
            return LLMResponse(**cached_data)
        return None

    def cache_response(self, response: LLMResponse):
        """Cache response for future idempotent requests"""
        cache_data = {
            'request_id': response.request_id,
            'response_text': response.response_text,
            'provider': response.provider,
            'model': response.model,
            'prompt_tokens': response.prompt_tokens,
            'completion_tokens': response.completion_tokens,
            'total_tokens': response.total_tokens,
            'cost_cents': response.cost_cents,
            'latency_ms': response.latency_ms,
            'quality_score': response.quality_score,
            'cached': False
        }
        cache.set(response.request_id, cache_data, self.cache_timeout)


class QualityAssessmentEngine:
    """Assesses LLM response quality and safety"""

    def __init__(self):
        self.safety_keywords = self._load_safety_keywords()
        self.quality_metrics = self._define_quality_metrics()

    def _load_safety_keywords(self) -> List[str]:
        """Load safety keywords for content filtering"""
        return [
            'disable_security', 'bypass_auth', 'remove_protection',
            'skip_verification', 'ignore_policy', 'override_safety'
        ]

    def _define_quality_metrics(self) -> Dict[str, Any]:
        """Define quality assessment metrics"""
        return {
            'completeness': {
                'weight': 0.3,
                'min_length': 50,
                'required_elements': ['reasoning', 'configuration']
            },
            'safety': {
                'weight': 0.4,
                'safety_keywords': self.safety_keywords,
                'max_violations': 0
            },
            'coherence': {
                'weight': 0.2,
                'min_sentences': 2,
                'max_repetition_ratio': 0.3
            },
            'relevance': {
                'weight': 0.1,
                'context_keywords_required': True
            }
        }

    def assess_response_quality(self, response: LLMResponse, original_prompt: str) -> float:
        """
        Assess response quality on a 0-1 scale

        Args:
            response: LLM response to assess
            original_prompt: Original prompt for context

        Returns:
            Quality score between 0.0 and 1.0
        """
        total_score = 0.0
        response_text = response.response_text.lower()

        # Completeness assessment
        completeness_score = self._assess_completeness(response.response_text)
        total_score += completeness_score * self.quality_metrics['completeness']['weight']

        # Safety assessment
        safety_score = self._assess_safety(response_text)
        total_score += safety_score * self.quality_metrics['safety']['weight']

        # Coherence assessment
        coherence_score = self._assess_coherence(response.response_text)
        total_score += coherence_score * self.quality_metrics['coherence']['weight']

        # Relevance assessment
        relevance_score = self._assess_relevance(response_text, original_prompt.lower())
        total_score += relevance_score * self.quality_metrics['relevance']['weight']

        return min(1.0, max(0.0, total_score))

    def _assess_completeness(self, response_text: str) -> float:
        """Assess response completeness"""
        if len(response_text) < self.quality_metrics['completeness']['min_length']:
            return 0.3

        required_elements = self.quality_metrics['completeness']['required_elements']
        found_elements = sum(1 for element in required_elements if element in response_text.lower())

        return found_elements / len(required_elements)

    def _assess_safety(self, response_text: str) -> float:
        """Assess response safety"""
        violations = sum(1 for keyword in self.safety_keywords if keyword in response_text)

        if violations > self.quality_metrics['safety']['max_violations']:
            return 0.0  # Fail safety check

        return 1.0

    def _assess_coherence(self, response_text: str) -> float:
        """Assess response coherence"""
        sentences = response_text.split('.')
        if len(sentences) < self.quality_metrics['coherence']['min_sentences']:
            return 0.5

        # Simple repetition check
        words = response_text.lower().split()
        unique_words = set(words)
        repetition_ratio = 1 - (len(unique_words) / max(1, len(words)))

        if repetition_ratio > self.quality_metrics['coherence']['max_repetition_ratio']:
            return 0.3

        return 1.0

    def _assess_relevance(self, response_text: str, original_prompt: str) -> float:
        """Assess response relevance to prompt"""
        prompt_words = set(original_prompt.split())
        response_words = set(response_text.split())

        # Calculate word overlap
        overlap = prompt_words.intersection(response_words)
        relevance_score = len(overlap) / max(1, len(prompt_words))

        return min(1.0, relevance_score * 2)  # Scale up for better scoring


class ProductionLLMService:
    """
    Production-grade LLM service with multiple providers,
    budget controls, idempotency, and quality assessment
    """

    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        self.budget_manager = BudgetManager()
        self.idempotency_manager = IdempotencyManager()
        self.quality_engine = QualityAssessmentEngine()
        self.fallback_order = getattr(settings, 'LLM_FALLBACK_ORDER', ['openai', 'anthropic', 'azure'])

        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize LLM providers from Django settings"""
        provider_configs = getattr(settings, 'LLM_PROVIDERS', {})

        for provider_name, config in provider_configs.items():
            try:
                if provider_name == 'openai':
                    provider = OpenAILLMProvider(provider_name, config)
                elif provider_name == 'anthropic':
                    provider = AnthropicLLMProvider(provider_name, config)
                elif provider_name == 'azure':
                    provider = AzureOpenAILLMProvider(provider_name, config)
                else:
                    logger.warning(f"Unknown LLM provider type: {provider_name}")
                    continue

                # Test connection
                if provider.validate_connection():
                    self.providers[provider_name] = provider
                    logger.info(f"Initialized LLM provider: {provider_name}")
                else:
                    logger.warning(f"Failed to validate LLM provider: {provider_name}")

            except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Failed to initialize LLM provider {provider_name}: {str(e)}")

        # Ensure we have at least a fallback
        if not self.providers:
            logger.warning("No LLM providers available, creating dummy fallback")
            self._create_dummy_fallback()

    def _create_dummy_fallback(self):
        """Create dummy provider as absolute fallback"""
        from ..services.llm import DummyLLMService

        class DummyProvider(LLMProvider):
            def __init__(self):
                super().__init__('dummy', {})
                self.dummy_service = DummyLLMService()

            def generate_completion(self, request: LLMRequest) -> LLMResponse:
                # Use existing dummy service logic
                dummy_response = self.dummy_service.enhance_context(
                    request.prompt, {}, None
                )

                return LLMResponse(
                    request_id=request.request_id,
                    response_text=json.dumps(dummy_response),
                    provider='dummy',
                    model='dummy',
                    prompt_tokens=len(request.prompt.split()),
                    completion_tokens=50,
                    total_tokens=len(request.prompt.split()) + 50,
                    cost_cents=0.0,
                    latency_ms=100
                )

            def validate_connection(self) -> bool:
                return True

        self.providers['dummy'] = DummyProvider()

    def generate_completion(
        self,
        prompt: str,
        user_id: int,
        client_id: int,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        preferred_provider: str = None,
        metadata: Dict[str, Any] = None
    ) -> LLMResponse:
        """
        Generate LLM completion with budget controls and idempotency

        Args:
            prompt: Input prompt
            user_id: User ID for tracking
            client_id: Client ID for tracking
            max_tokens: Maximum response tokens
            temperature: Response creativity (0-1)
            preferred_provider: Preferred provider name
            metadata: Additional request metadata

        Returns:
            LLM response with cost and quality information
        """
        # Create request object
        request = LLMRequest(
            request_id=self.idempotency_manager.generate_request_id(user_id, prompt, preferred_provider or 'auto'),
            user_id=user_id,
            client_id=client_id,
            prompt=prompt,
            model=preferred_provider or 'auto',
            max_tokens=max_tokens,
            temperature=temperature,
            metadata=metadata or {},
            created_at=timezone.now()
        )

        # Check for cached response (idempotency)
        cached_response = self.idempotency_manager.check_cached_response(request.request_id)
        if cached_response:
            logger.info(f"Returning cached LLM response for request {request.request_id}")
            return cached_response

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
                # Check budget before making request
                estimated_cost = provider.estimate_cost(prompt, max_tokens)
                budget_ok, budget_message = self.budget_manager.check_budget_availability(
                    provider_name, estimated_cost
                )

                if not budget_ok:
                    logger.warning(f"Budget check failed for {provider_name}: {budget_message}")
                    continue

                # Generate completion
                response = provider.generate_completion(request)

                # Assess quality
                quality_score = self.quality_engine.assess_response_quality(response, prompt)
                response.quality_score = quality_score

                # Record spending
                self.budget_manager.record_spend(
                    provider_name, response.cost_cents, request.metadata
                )

                # Cache response for idempotency
                self.idempotency_manager.cache_response(response)

                logger.info(f"Generated LLM completion using {provider_name} (quality: {quality_score:.2f})")
                return response

            except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
                last_error = e
                logger.warning(f"LLM provider {provider_name} failed: {str(e)}")
                continue

        # All providers failed
        if last_error:
            raise LLMProviderError(f"All LLM providers failed. Last error: {str(last_error)}")
        else:
            raise LLMProviderError("No available LLM providers")

    def enhance_context(self, user_input: str, context: Dict[str, Any], user) -> Dict[str, Any]:
        """Enhanced context generation for conversational onboarding"""
        prompt = f"""
        As a facility management expert, analyze the following user input and context to enhance understanding:

        User Input: {user_input}
        Context: {json.dumps(context, indent=2)}

        Provide enhanced context including:
        1. Inferred requirements and preferences
        2. Industry and facility type detection
        3. Suggested next questions
        4. Risk assessment

        Respond in JSON format with enhanced_context, inferred_requirements, suggested_questions, and risk_factors.
        """

        try:
            response = self.generate_completion(
                prompt=prompt,
                user_id=user.id if user else 0,
                client_id=getattr(user, 'client_id', 0) if user else 0,
                max_tokens=1024,
                temperature=0.3,  # Lower temperature for structured output
                metadata={'operation': 'enhance_context', 'user_input_length': len(user_input)}
            )

            # Parse JSON response
            try:
                enhanced_data = json.loads(response.response_text)
                return enhanced_data.get('enhanced_context', context)
            except json.JSONDecodeError:
                logger.warning("LLM response was not valid JSON, returning original context")
                return context

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error enhancing context with LLM: {str(e)}")
            return context

    def generate_questions(self, context: Dict[str, Any], conversation_type: str) -> List[str]:
        """Generate contextual questions for the conversation"""
        prompt = f"""
        Based on the following context and conversation type, generate 3-5 relevant questions to gather the necessary information for facility management system setup:

        Context: {json.dumps(context, indent=2)}
        Conversation Type: {conversation_type}

        Generate questions that are:
        1. Specific and actionable
        2. Appropriate for the conversation stage
        3. Focused on essential configuration details
        4. Easy to understand for non-technical users

        Return as a JSON array of question strings.
        """

        try:
            response = self.generate_completion(
                prompt=prompt,
                user_id=context.get('user_id', 0),
                client_id=context.get('client_id', 0),
                max_tokens=512,
                temperature=0.5,
                metadata={'operation': 'generate_questions', 'conversation_type': conversation_type}
            )

            # Parse JSON response
            try:
                questions = json.loads(response.response_text)
                return questions if isinstance(questions, list) else []
            except json.JSONDecodeError:
                logger.warning("LLM response was not valid JSON for questions")
                return self._get_fallback_questions(conversation_type)

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error generating questions with LLM: {str(e)}")
            return self._get_fallback_questions(conversation_type)

    def process_conversation_step(
        self,
        session,
        user_input: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a conversation step and generate recommendations"""
        prompt = f"""
        As a facility management consultant, analyze this conversation step and generate specific recommendations:

        Previous Context: {json.dumps(session.context_data, indent=2)}
        User Input: {user_input}
        Additional Context: {json.dumps(context, indent=2)}
        Session Type: {session.conversation_type}

        Generate specific, actionable recommendations for system configuration including:
        1. Business unit configurations
        2. Shift schedules
        3. User roles and permissions
        4. Security settings
        5. Device configurations

        Include confidence scores and clear reasoning for each recommendation.
        Return as JSON with recommendations array, confidence_score, and next_steps.
        """

        try:
            response = self.generate_completion(
                prompt=prompt,
                user_id=session.user.id,
                client_id=session.client.id,
                max_tokens=2048,
                temperature=0.4,
                metadata={
                    'operation': 'process_conversation',
                    'session_id': str(session.session_id),
                    'conversation_type': session.conversation_type
                }
            )

            # Parse JSON response
            try:
                result = json.loads(response.response_text)
                result['llm_metadata'] = {
                    'provider': response.provider,
                    'model': response.model,
                    'cost_cents': response.cost_cents,
                    'quality_score': response.quality_score,
                    'latency_ms': response.latency_ms
                }
                return result
            except json.JSONDecodeError:
                logger.warning("LLM response was not valid JSON for conversation processing")
                return self._get_fallback_conversation_result()

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error processing conversation step with LLM: {str(e)}")
            return self._get_fallback_conversation_result()

    def _get_fallback_questions(self, conversation_type: str) -> List[str]:
        """Get fallback questions when LLM fails"""
        fallback_questions = {
            'initial_setup': [
                "What type of facility are you setting up? (office, retail, warehouse, etc.)",
                "How many staff members will be using the system?",
                "What are your typical operating hours?",
                "Do you need GPS tracking for mobile workers?"
            ],
            'config_update': [
                "What specific configuration would you like to update?",
                "Are there any new requirements or changes in your operation?",
                "Do you need to add or modify user roles?"
            ]
        }

        return fallback_questions.get(conversation_type, [
            "Could you tell me more about your facility?",
            "What are your main requirements?",
            "Are there any specific features you need?"
        ])

    def _get_fallback_conversation_result(self) -> Dict[str, Any]:
        """Get fallback result when LLM processing fails"""
        return {
            'recommendations': [],
            'confidence_score': 0.1,
            'next_steps': [
                "Please provide more specific information about your requirements",
                "Consider using industry templates for faster setup"
            ],
            'fallback_used': True,
            'llm_metadata': {
                'provider': 'fallback',
                'error': 'LLM service unavailable'
            }
        }

    def get_provider_status(self) -> Dict[str, Any]:
        """Get status and budget information for all providers"""
        status = {}

        for name, provider in self.providers.items():
            budget_status = self.budget_manager.get_budget_status(name)

            status[name] = {
                'available': provider.validate_connection(),
                'model': provider.model,
                'budget_status': {
                    'daily_budget_cents': budget_status.daily_budget_cents,
                    'current_spend_cents': budget_status.current_spend_cents,
                    'remaining_budget_cents': budget_status.remaining_budget_cents,
                    'utilization_percentage': budget_status.utilization_percentage,
                    'budget_exhausted': budget_status.budget_exhausted
                }
            }

        return status

    def reset_daily_budgets(self, provider: str = None):
        """Reset daily budgets (admin function)"""
        if provider:
            providers_to_reset = [provider] if provider in self.providers else []
        else:
            providers_to_reset = list(self.providers.keys())

        today = timezone.now().date().isoformat()

        for provider_name in providers_to_reset:
            spend_key = f"llm_spend:{provider_name}:{today}"
            cache.delete(spend_key)
            logger.info(f"Reset daily budget for {provider_name}")

        return {'reset_providers': providers_to_reset, 'reset_at': timezone.now().isoformat()}


# Singleton instance
_production_llm_service = None


def get_production_llm_service() -> ProductionLLMService:
    """Get singleton instance of production LLM service"""
    global _production_llm_service
    if _production_llm_service is None:
        _production_llm_service = ProductionLLMService()
    return _production_llm_service


def get_llm_service():
    """Factory function to get appropriate LLM service"""
    if getattr(settings, 'ENABLE_PRODUCTION_LLM', False):
        return get_production_llm_service()
    else:
        # Fall back to existing dummy service
        from .llm import get_llm_service as get_dummy_llm
        return get_dummy_llm()