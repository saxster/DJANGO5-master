"""RouteBot - Route & Shift Optimization Agent."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from django.utils import timezone

from apps.activity.models.job_model import Jobneed
from apps.core_onboarding.services.llm.exceptions import LLMProviderError

from .base_agent_service import BaseAgentService

logger = logging.getLogger(__name__)


class RouteAgentService(BaseAgentService):
    """AI agent that optimizes patrol routes and shift coverage."""

    TOUR_IDENTIFIERS = (
        Jobneed.Identifier.INTERNALTOUR,
        Jobneed.Identifier.EXTERNALTOUR,
    )

    def __init__(self, tenant_id: int):
        super().__init__(
            agent_id="routebot-001",
            agent_name="RouteBot",
            tenant_id=tenant_id,
        )

    def analyze(
        self,
        site_id: int,
        time_range: Tuple[datetime, datetime],
    ) -> List["AgentRecommendation"]:
        recommendations = []
        try:
            metrics = self._get_route_metrics(site_id, time_range)

            if (
                metrics["eta_breaches"] > 0
                or metrics["route_deviation_count"] > 0
                or metrics["staff_gap"] > 0
            ):
                rec = self._generate_route_recommendation(site_id, time_range, metrics)
                if rec:
                    recommendations.append(rec)

        except (ValueError, KeyError, AttributeError) as exc:
            logger.error("RouteBot analysis error: %s", exc, exc_info=True)

        return recommendations

    def _get_route_metrics(
        self, site_id: int, time_range: Tuple[datetime, datetime]
    ) -> Dict[str, int]:
        queryset = (
            Jobneed.objects.filter(
                bu_id=site_id,
                client_id=self.tenant_id,
                identifier__in=self.TOUR_IDENTIFIERS,
                plandatetime__range=time_range,
            )
            .select_related("bu")
            .only("id", "jobstatus", "expirydatetime")
        )

        planned = queryset.count()
        completed = queryset.filter(jobstatus=Jobneed.JobStatus.COMPLETED).count()
        autoclosed = queryset.filter(jobstatus=Jobneed.JobStatus.AUTOCLOSED).count()
        partial = queryset.filter(jobstatus=Jobneed.JobStatus.PARTIALLYCOMPLETED).count()
        inprogress = queryset.filter(jobstatus=Jobneed.JobStatus.INPROGRESS).count()
        eta_breaches = queryset.filter(
            jobstatus__in=[Jobneed.JobStatus.ASSIGNED, Jobneed.JobStatus.INPROGRESS],
            expirydatetime__lt=timezone.now(),
        ).count()

        route_deviation_count = autoclosed + partial
        staff_gap = max(0, planned - (completed + inprogress))

        return {
            "planned": planned,
            "completed": completed,
            "autoclosed": autoclosed,
            "partial": partial,
            "inprogress": inprogress,
            "eta_breaches": eta_breaches,
            "route_deviation_count": route_deviation_count,
            "staff_gap": staff_gap,
        }

    def _generate_route_recommendation(
        self,
        site_id: int,
        time_range: Tuple[datetime, datetime],
        metrics: Dict[str, int],
    ) -> Optional["AgentRecommendation"]:
        try:
            focus = (
                "Analyze patrol coverage and highlight where travel times or"
                " staffing gaps will violate SLAs. Recommend concrete route"
                " changes or shift swaps so supervisors can act immediately."
            )

            prompt_bundle = self._build_prompt_bundle(
                module="routes",
                site_id=site_id,
                client_id=self.tenant_id,
                metrics=metrics,
                time_range=time_range,
                focus=focus,
                additional_notes={
                    "staff_gap": metrics["staff_gap"],
                    "eta_breaches": metrics["eta_breaches"],
                },
            )

            schema = {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "route_deviations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entity_id": {"type": "string"},
                                "reason": {"type": "string"},
                                "impact_minutes": {"type": "number"},
                                "suggested_action": {"type": "string"},
                            },
                            "required": ["reason"],
                        },
                        "maxItems": 5,
                    },
                    "staffing_moves": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "shift": {"type": "string"},
                                "impact": {"type": "string"},
                                "action": {"type": "string"},
                            },
                            "required": ["action"],
                        },
                        "maxItems": 5,
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "type": {"type": "string"},
                                "endpoint": {"type": "string"},
                                "payload": {"type": "object"},
                                "url": {"type": "string"},
                            },
                            "required": ["label", "type"],
                        },
                    },
                    "narrative_chunks": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "summary",
                    "severity",
                    "confidence",
                    "route_deviations",
                ],
            }

            analysis = self._invoke_structured_llm(
                prompt_bundle,
                schema,
                generation_kwargs={"temperature": 0.5, "max_tokens": 1600},
            )

            summary = analysis.get("summary") or (
                "Route deviations detected – rebalance patrol coverage"
            )
            severity = analysis.get("severity", "medium")
            confidence = float(analysis.get("confidence", 0.85))
            route_deviations = analysis.get("route_deviations", [])
            staffing_moves = analysis.get("staffing_moves", [])

            actions = analysis.get("actions") or [
                {
                    "label": "Reassign Patrols",
                    "type": "workflow_trigger",
                    "endpoint": "/api/routes/rebalance",
                    "payload": {
                        "site_id": site_id,
                        "eta_breaches": metrics["eta_breaches"],
                    },
                },
                {
                    "label": "View Route Board",
                    "type": "link",
                    "url": "/operations/routes/",
                },
            ]

            context_metrics = {
                **metrics,
                "prompt_context": prompt_bundle["metadata"],
                "schema": "routebot.optimization.v2",
            }
            if analysis.get("narrative_chunks"):
                context_metrics["narrative_chunks"] = analysis["narrative_chunks"]
            if staffing_moves:
                context_metrics["staffing_moves"] = staffing_moves

            return self.create_recommendation(
                module="routes",
                site_id=site_id,
                client_id=self.tenant_id,
                summary=summary,
                details=route_deviations,
                confidence=confidence,
                severity=severity,
                actions=actions,
                time_range=time_range,
                context_metrics=context_metrics,
            )

        except (LLMProviderError, json.JSONDecodeError, ValueError) as exc:
            logger.error("RouteBot recommendation failed: %s", exc, exc_info=True)
            return None
