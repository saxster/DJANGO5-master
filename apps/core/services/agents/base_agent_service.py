"""
Base Agent Service

Foundation for all dashboard AI agents.
Provides common functionality: LLM integration, recommendation creation, error handling.

Following CLAUDE.md:
- Rule #7: <150 lines
- Rule #11: Specific exception handling
- Integration with Gemini/Claude LLM router

Dashboard Agent Intelligence - Phase 2.1
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from django.utils import timezone

from apps.core.models.agent_recommendation import AgentRecommendation
from apps.core.validation_pydantic.agent_schemas import AgentRecommendationSchema
from apps.onboarding_api.services.llm.provider_router import get_llm_router
from apps.onboarding_api.services.llm.exceptions import AllProvidersFailedError
from apps.client_onboarding.models import Bt

logger = logging.getLogger(__name__)


class BaseAgentService:
    """
    Base class for all dashboard AI agents.

    Provides:
    - LLM integration (Gemini primary, Claude fallback)
    - Recommendation creation and validation
    - Common utility methods
    - Error handling patterns
    """

    def __init__(self, agent_id: str, agent_name: str, tenant_id: int):
        """
        Initialize base agent service.

        Args:
            agent_id: Unique agent identifier (e.g., 'taskbot-001')
            agent_name: Human-readable name (e.g., 'TaskBot')
            tenant_id: Tenant/client ID for multi-tenant isolation
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.tenant_id = tenant_id

        # Lazy-loaded LLM (Gemini with Claude fallback)
        self._llm_router = None
        self._maker_llm = None
        self._llm_provider_used = None

    def get_llm(self):
        """
        Lazy load LLM with automatic fallback.

        Returns Gemini by default, falls back to Claude if Gemini fails.

        Returns:
            MakerLLM instance

        Raises:
            AllProvidersFailedError: If all LLM providers fail
        """
        if not self._maker_llm:
            try:
                if not self._llm_router:
                    self._llm_router = get_llm_router(self.tenant_id)

                self._maker_llm = self._llm_router.get_maker_llm()
                self._llm_provider_used = getattr(self._maker_llm, 'provider_name', 'gemini')

                logger.info(
                    f"{self.agent_name}: Using LLM provider '{self._llm_provider_used}' "
                    f"for tenant {self.tenant_id}"
                )
            except AllProvidersFailedError as e:
                logger.error(f"{self.agent_name}: All LLM providers failed: {e}", exc_info=True)
                raise

        return self._maker_llm

    def analyze(self, site_id: int, time_range: Tuple[datetime, datetime]) -> List[AgentRecommendation]:
        """
        Analyze dashboard metrics and generate recommendations.

        Must be overridden by subclasses.

        Args:
            site_id: Business unit/site ID
            time_range: (start, end) datetime tuple

        Returns:
            List of AgentRecommendation instances

        Raises:
            NotImplementedError: If not overridden by subclass
        """
        raise NotImplementedError(f"{self.agent_name} must implement analyze() method")

    def create_recommendation(
        self,
        module: str,
        site_id: int,
        client_id: int,
        summary: str,
        details: List[Dict[str, Any]],
        confidence: float,
        severity: str,
        actions: List[Dict[str, Any]],
        time_range: Tuple[datetime, datetime],
        context_metrics: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AgentRecommendation:
        """
        Create and validate agent recommendation.

        Args:
            module: Dashboard module ('tasks', 'tours', etc.)
            site_id: Business unit/site ID
            client_id: Tenant/client ID
            summary: Human-readable summary
            details: List of entity-specific details
            confidence: Confidence score (0.0-1.0)
            severity: 'low', 'medium', 'high', or 'critical'
            actions: List of actionable buttons
            time_range: Analysis time range
            context_metrics: Optional metrics dictionary
            **kwargs: Additional fields

        Returns:
            Created AgentRecommendation instance

        Raises:
            ValidationError: If Pydantic validation fails
            DatabaseError: If database save fails
        """
        # Validate with Pydantic first
        schema = AgentRecommendationSchema(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            timestamp=timezone.now(),
            context={
                'module': module,
                'site': str(site_id),
                'time_range': f"{time_range[0].isoformat()} ~ {time_range[1].isoformat()}",
                'metrics': context_metrics or {}
            },
            recommendation={'summary': summary, 'details': details},
            confidence=confidence,
            severity=severity,
            actions=actions,
            llm_provider=self._llm_provider_used or 'gemini',
            **kwargs
        )

        # Create database record
        site = Bt.objects.get(id=site_id)
        client = Bt.objects.get(id=client_id)

        rec = AgentRecommendation.objects.create(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            module=module,
            site=site,
            client=client,
            time_range_start=time_range[0],
            time_range_end=time_range[1],
            context_metrics=context_metrics or {},
            summary=summary,
            details=details,
            confidence=confidence,
            severity=severity,
            actions=actions,
            llm_provider=self._llm_provider_used or 'gemini',
            **kwargs
        )

        logger.info(
            f"{self.agent_name}: Created recommendation {rec.id} "
            f"(module={module}, severity={severity}, confidence={confidence:.2f})"
        )

        return rec

    def execute_action(self, recommendation_id: int, action_type: str):
        """
        Execute recommended action.

        Must be overridden by subclasses that support action execution.

        Args:
            recommendation_id: AgentRecommendation ID
            action_type: Action type to execute

        Raises:
            NotImplementedError: If not overridden by subclass
        """
        raise NotImplementedError(f"{self.agent_name} does not support action execution")
