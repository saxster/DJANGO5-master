"""IncidentBot - Helpdesk triage and escalation agent."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.db.models import Avg, DurationField, ExpressionWrapper, F
from django.utils import timezone

from apps.core_onboarding.services.llm.exceptions import LLMProviderError
from apps.y_helpdesk.models import Ticket

from .base_agent_service import BaseAgentService

logger = logging.getLogger(__name__)


class IncidentAgentService(BaseAgentService):
    """Transforms ticket backlogs into structured remediation steps."""

    SLA_HOURS = 4

    def __init__(self, tenant_id: int):
        super().__init__(
            agent_id="incidentbot-001",
            agent_name="IncidentBot",
            tenant_id=tenant_id,
        )

    def analyze(
        self,
        site_id: int,
        time_range: Tuple[datetime, datetime],
    ) -> List["AgentRecommendation"]:
        recommendations = []
        try:
            metrics = self._get_incident_metrics(site_id, time_range)

            if metrics["backlog"] > 0 or metrics["sla_breaches"] > 0:
                rec = self._generate_incident_recommendation(site_id, time_range, metrics)
                if rec:
                    recommendations.append(rec)

        except (ValueError, KeyError, AttributeError) as exc:
            logger.error("IncidentBot analysis error: %s", exc, exc_info=True)

        return recommendations

    def _get_incident_metrics(
        self,
        site_id: int,
        time_range: Tuple[datetime, datetime],
    ) -> Dict[str, float]:
        queryset = Ticket.objects.filter(
            bu_id=site_id,
            client_id=self.tenant_id,
            cdtz__range=time_range,
        ).only("status", "priority", "cdtz", "mdtz", "ticketno")

        total = queryset.count()
        open_count = queryset.filter(status=Ticket.Status.OPEN).count()
        resolved = queryset.filter(status=Ticket.Status.RESOLVED).count()
        onhold = queryset.filter(status=Ticket.Status.ONHOLD).count()
        new = queryset.filter(status=Ticket.Status.NEW).count()
        cancelled = queryset.filter(status=Ticket.Status.CANCEL).count()
        closed = queryset.filter(status=Ticket.Status.CLOSED).count()

        backlog = open_count + onhold

        sla_cutoff = timezone.now() - timedelta(hours=self.SLA_HOURS)
        sla_breaches = queryset.filter(
            status__in=[Ticket.Status.OPEN, Ticket.Status.ONHOLD],
            mdtz__lte=sla_cutoff,
        ).count()

        duration_expr = ExpressionWrapper(
            F("mdtz") - F("cdtz"), output_field=DurationField()
        )
        avg_resolution = queryset.filter(status=Ticket.Status.RESOLVED).aggregate(
            avg_hours=Avg(duration_expr)
        )["avg_hours"]
        avg_resolution_hours = (
            avg_resolution.total_seconds() / 3600 if avg_resolution else 0.0
        )

        high_priority = queryset.filter(priority=Ticket.Priority.HIGH).count()

        return {
            "total": total,
            "open": open_count,
            "resolved": resolved,
            "onhold": onhold,
            "new": new,
            "cancelled": cancelled,
            "closed": closed,
            "backlog": backlog,
            "sla_breaches": sla_breaches,
            "avg_resolution_hours": round(avg_resolution_hours, 2),
            "high_priority": high_priority,
        }

    def _generate_incident_recommendation(
        self,
        site_id: int,
        time_range: Tuple[datetime, datetime],
        metrics: Dict[str, float],
    ) -> Optional["AgentRecommendation"]:
        try:
            focus = (
                "Summarize incident backlog risk, flag high-priority tickets"
                " that need immediate action, and recommend remediation"
                " playbooks or escalations."
            )

            prompt_bundle = self._build_prompt_bundle(
                module="incidents",
                site_id=site_id,
                client_id=self.tenant_id,
                metrics=metrics,
                time_range=time_range,
                focus=focus,
                additional_notes={
                    "avg_resolution_hours": metrics["avg_resolution_hours"],
                    "high_priority": metrics["high_priority"],
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
                    "incident_hotlist": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entity_id": {"type": "string"},
                                "reason": {"type": "string"},
                                "priority": {"type": "string"},
                                "suggested_action": {"type": "string"},
                            },
                            "required": ["reason"],
                        },
                        "maxItems": 5,
                    },
                    "playbooks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "steps": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["name"],
                        },
                        "maxItems": 3,
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
                    "incident_hotlist",
                ],
            }

            analysis = self._invoke_structured_llm(
                prompt_bundle,
                schema,
                generation_kwargs={"temperature": 0.45, "max_tokens": 1500},
            )

            summary = analysis.get("summary") or (
                "Incident backlog requires immediate triage"
            )
            severity = analysis.get("severity", "medium")
            confidence = float(analysis.get("confidence", 0.82))
            hotlist = analysis.get("incident_hotlist", [])
            playbooks = analysis.get("playbooks", [])

            actions = analysis.get("actions") or [
                {
                    "label": "Escalate Urgent Tickets",
                    "type": "workflow_trigger",
                    "endpoint": "/api/helpdesk/tickets/escalate",
                    "payload": {"site_id": site_id},
                },
                {
                    "label": "Open Helpdesk",
                    "type": "link",
                    "url": "/helpdesk/",
                },
            ]

            context_metrics = {
                **metrics,
                "prompt_context": prompt_bundle["metadata"],
                "schema": "incidentbot.triage.v2",
            }
            if analysis.get("narrative_chunks"):
                context_metrics["narrative_chunks"] = analysis["narrative_chunks"]
            if playbooks:
                context_metrics["playbooks"] = playbooks

            return self.create_recommendation(
                module="incidents",
                site_id=site_id,
                client_id=self.tenant_id,
                summary=summary,
                details=hotlist,
                confidence=confidence,
                severity=severity,
                actions=actions,
                time_range=time_range,
                context_metrics=context_metrics,
            )

        except (LLMProviderError, json.JSONDecodeError, ValueError) as exc:
            logger.error("IncidentBot recommendation failed: %s", exc, exc_info=True)
            return None
