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

import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from django.utils import timezone

from apps.core.models.agent_recommendation import AgentRecommendation
from apps.core.validation_pydantic.agent_schemas import AgentRecommendationSchema
from apps.core_onboarding.services.llm.provider_router import get_llm_router
from apps.core_onboarding.services.llm.exceptions import AllProvidersFailedError
from apps.client_onboarding.models import Bt
from apps.core.services.agents.prompt_builder import (
    AgentPromptComposer,
    get_profile_for_tenant,
)

LOG_JSON_EXTRACTION_ERROR = "Gemini response did not contain valid JSON output"

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
        self._last_prompt_metadata: Dict[str, Any] = {}

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

    # ------------------------------------------------------------------
    # Prompt & context helpers
    # ------------------------------------------------------------------

    def _get_recent_recommendations(
        self, module: str, site_id: int, limit: int = 3
    ) -> List[Dict[str, Any]]:
        queryset = AgentRecommendation.objects.filter(
            module=module,
            site_id=site_id,
        ).order_by('-created_at')[:limit]
        return [
            {
                'id': rec.id,
                'summary': rec.summary,
                'severity': rec.severity,
                'status': rec.status,
            }
            for rec in queryset
        ]

    def _get_tenant_context(self, client_id: int, site_id: int) -> Dict[str, Any]:
        site = Bt.objects.select_related('tenant', 'parent').filter(id=site_id).first()
        client = Bt.objects.select_related('tenant').filter(id=client_id).first()
        tenant = (client or site).tenant if (client or site) else None
        return {
            'client_name': client.buname if client else 'Unknown Client',
            'client_code': client.bucode if client else 'UNKNOWN',
            'site_name': site.buname if site else 'Unknown Site',
            'site_code': site.bucode if site else 'UNKNOWN',
            'tenant_name': getattr(tenant, 'tenantname', 'Unknown Tenant'),
            'tenant_slug': getattr(tenant, 'subdomain_prefix', None),
        }

    def _build_prompt_bundle(
        self,
        *,
        module: str,
        site_id: int,
        client_id: int,
        metrics: Dict[str, Any],
        time_range: Tuple[datetime, datetime],
        focus: str,
        additional_notes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        tenant_context = self._get_tenant_context(client_id, site_id)
        profile = get_profile_for_tenant(tenant_context.get('tenant_slug'))
        history = self._get_recent_recommendations(module, site_id)
        composer = AgentPromptComposer(
            agent_name=self.agent_name,
            module=module,
            time_range=(time_range[0].isoformat(), time_range[1].isoformat()),
            metrics=metrics,
            tenant_context=tenant_context,
            focus=focus,
            profile=profile,
            recent_recommendations=history,
            additional_notes=additional_notes,
        )
        prompt = composer.render()
        metadata = composer.context_summary()
        metadata.update(
            {
                'profile_key': profile.key,
                'recent_recommendation_ids': [rec['id'] for rec in history],
                'prompt_char_count': len(prompt),
            }
        )
        self._last_prompt_metadata = metadata
        return {'prompt': prompt, 'metadata': metadata}

    def _invoke_structured_llm(
        self,
        prompt_bundle: Dict[str, Any],
        schema: Dict[str, Any],
        generation_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        llm = self.get_llm()
        schema_text = json.dumps(schema, indent=2)
        instructions = (
            "You must respond with VALID JSON that matches the schema above. "
            "Do not include prose outside the JSON body."
        )
        final_prompt = (
            f"{prompt_bundle['prompt']}\n\n"
            f"## Output Schema\n{schema_text}\n\n{instructions}"
        )
        kwargs = {'temperature': 0.65, 'max_tokens': 2048}
        if generation_kwargs:
            kwargs.update(generation_kwargs)
        response = llm.generate(final_prompt, **kwargs)
        data = self._extract_json_payload(response)
        return data

    def _extract_json_payload(self, response_text: str) -> Dict[str, Any]:
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start == -1 or end == -1:
            logger.error(LOG_JSON_EXTRACTION_ERROR, extra={'provider': self._llm_provider_used})
            raise ValueError(LOG_JSON_EXTRACTION_ERROR)
        raw_json = response_text[start:end + 1]
        return json.loads(raw_json)

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
