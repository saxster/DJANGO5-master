"""Prompt composition utilities for dashboard AI agents."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Tuple
from django.conf import settings


@dataclass(frozen=True)
class AgentCommunicationProfile:
    """Voice/structure expectations for an agent output."""

    key: str
    description: str
    tone: str
    bullet_style: str
    escalation_language: str
    signoff: str

    def to_metadata(self) -> Dict[str, str]:
        return asdict(self)


DEFAULT_PROFILE = AgentCommunicationProfile(
    key="default",
    description="Balanced operations analyst voice",
    tone="Confident, empathetic, focuses on measurable impact",
    bullet_style="Numbered list with short imperative sentences",
    escalation_language="Escalate only when SLA or safety is at risk; cite the trigger metric",
    signoff="Close with a single sentence summarizing impact and next step",
)

FORMAL_ENTERPRISE_PROFILE = AgentCommunicationProfile(
    key="formal_enterprise",
    description="Formal stakeholder brief for enterprise clients",
    tone="Concise, executive-friendly, emphasizes risk management",
    bullet_style="Bullets with bolded labels followed by explanations",
    escalation_language="Reference governance owners and request acknowledgement",
    signoff="End with a call to action tied to accountability",
)

PROFILE_LIBRARY: Dict[str, AgentCommunicationProfile] = {
    DEFAULT_PROFILE.key: DEFAULT_PROFILE,
    FORMAL_ENTERPRISE_PROFILE.key: FORMAL_ENTERPRISE_PROFILE,
}


class AgentPromptComposer:
    """Constructs structured prompt sections for an agent call."""

    def __init__(
        self,
        agent_name: str,
        module: str,
        time_range: Tuple[str, str],
        metrics: Dict[str, Any],
        tenant_context: Dict[str, Any],
        focus: str,
        profile: AgentCommunicationProfile,
        recent_recommendations: List[Dict[str, Any]],
        additional_notes: Dict[str, Any] | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.module = module
        self.time_range = time_range
        self.metrics = metrics
        self.tenant_context = tenant_context
        self.focus = focus
        self.profile = profile
        self.recent_recommendations = recent_recommendations
        self.additional_notes = additional_notes or {}
        self._sections: List[str] = []

    def render(self) -> str:
        self._sections = [
            self._persona_section(),
            self._tenant_section(),
            self._metrics_section(),
            self._history_section(),
            self._focus_section(),
        ]
        return "\n\n".join(section for section in self._sections if section)

    def context_summary(self) -> Dict[str, Any]:
        return {
            "profile": self.profile.to_metadata(),
            "focus": self.focus,
            "tenant": self.tenant_context,
            "recent_recommendations": self.recent_recommendations,
            "additional_notes": self.additional_notes,
        }

    def _persona_section(self) -> str:
        return (
            f"## Agent Persona\n"
            f"Agent: {self.agent_name}\n"
            f"Module: {self.module}\n"
            f"Tone: {self.profile.tone}\n"
            f"Bullet Style: {self.profile.bullet_style}\n"
            f"Escalation Guidance: {self.profile.escalation_language}\n"
            f"Signoff: {self.profile.signoff}"
        )

    def _tenant_section(self) -> str:
        tenant_lines = ["## Tenant Context"]
        for key, value in self.tenant_context.items():
            tenant_lines.append(f"- {key}: {value}")
        if self.additional_notes:
            tenant_lines.append("- Additional Signals:")
            for key, value in self.additional_notes.items():
                tenant_lines.append(f"  • {key}: {value}")
        return "\n".join(tenant_lines)

    def _metrics_section(self) -> str:
        metrics_lines = [
            "## Current Metrics",
            f"Time Range: {self.time_range[0]} → {self.time_range[1]}",
        ]
        for key, value in self.metrics.items():
            metrics_lines.append(f"- {key}: {value}")
        return "\n".join(metrics_lines)

    def _history_section(self) -> str:
        if not self.recent_recommendations:
            return "## Recent Recommendations\n- None in the last window"
        history_lines = ["## Recent Recommendations"]
        for rec in self.recent_recommendations:
            history_lines.append(
                f"- #{rec['id']} ({rec['severity']}): {rec['summary']}\n  Outcome: {rec['status']}"
            )
        return "\n".join(history_lines)

    def _focus_section(self) -> str:
        return (
            "## Task"
            f"\n{self.focus}\n"
            "Respond ONLY with JSON that matches the requested schema."
        )


def get_profile_for_tenant(subdomain: str | None) -> AgentCommunicationProfile:
    overrides = getattr(settings, "AGENT_TONE_PROFILE_OVERRIDES", {})
    profile_key = overrides.get(subdomain or "", DEFAULT_PROFILE.key)
    return PROFILE_LIBRARY.get(profile_key, DEFAULT_PROFILE)

