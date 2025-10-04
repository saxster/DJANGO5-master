"""
Runbook Matcher Service.

Intelligently matches findings to appropriate runbooks.
Selects best runbook based on finding type, category, severity, and context.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from typing import Optional, List
from django.db.models import Q

from apps.noc.security_intelligence.models import FindingRunbook

logger = logging.getLogger('noc.runbook_matcher')


class RunbookMatcher:
    """
    Matches findings to appropriate runbooks.

    Matching strategy:
    1. Exact finding_type match (highest priority)
    2. Category + severity match
    3. Category match (fallback)
    4. Generic runbook (last resort)
    """

    @classmethod
    def match_runbook(cls, finding_type: str, category: str, severity: str, tenant) -> Optional[FindingRunbook]:
        """
        Find best matching runbook for a finding.

        Args:
            finding_type: String finding type
            category: String category
            severity: String severity
            tenant: Tenant instance

        Returns:
            FindingRunbook instance or None
        """
        try:
            # Strategy 1: Exact finding_type match
            runbook = cls._exact_match(finding_type, tenant)
            if runbook:
                logger.debug(f"Exact match for {finding_type}: {runbook.title}")
                return runbook

            # Strategy 2: Category + severity match
            runbook = cls._category_severity_match(category, severity, tenant)
            if runbook:
                logger.debug(f"Category/severity match for {category}/{severity}: {runbook.title}")
                return runbook

            # Strategy 3: Category match (any severity)
            runbook = cls._category_match(category, tenant)
            if runbook:
                logger.debug(f"Category match for {category}: {runbook.title}")
                return runbook

            # Strategy 4: Generic fallback
            runbook = cls._generic_fallback(tenant)
            if runbook:
                logger.debug(f"Generic fallback: {runbook.title}")
                return runbook

            logger.warning(f"No runbook match for {finding_type}/{category}/{severity}")
            return None

        except (ValueError, AttributeError) as e:
            logger.error(f"Runbook matching error: {e}", exc_info=True)
            return None

    @classmethod
    def _exact_match(cls, finding_type: str, tenant) -> Optional[FindingRunbook]:
        """Find runbook with exact finding_type match."""
        return FindingRunbook.objects.filter(
            tenant=tenant,
            finding_type=finding_type
        ).first()

    @classmethod
    def _category_severity_match(cls, category: str, severity: str, tenant) -> Optional[FindingRunbook]:
        """Find runbook matching category and severity."""
        return FindingRunbook.objects.filter(
            tenant=tenant,
            category=category,
            severity=severity
        ).order_by('-usage_count').first()  # Prefer most-used runbook

    @classmethod
    def _category_match(cls, category: str, tenant) -> Optional[FindingRunbook]:
        """Find runbook matching category (any severity)."""
        return FindingRunbook.objects.filter(
            tenant=tenant,
            category=category
        ).order_by('-usage_count').first()

    @classmethod
    def _generic_fallback(cls, tenant) -> Optional[FindingRunbook]:
        """Get generic fallback runbook."""
        return FindingRunbook.objects.filter(
            tenant=tenant,
            finding_type='GENERIC'
        ).first()

    @classmethod
    def get_related_runbooks(cls, finding_type: str, category: str, tenant, limit: int = 3) -> List[FindingRunbook]:
        """
        Get list of related runbooks for reference.

        Args:
            finding_type: String finding type
            category: String category
            tenant: Tenant instance
            limit: Maximum number of runbooks to return

        Returns:
            list: FindingRunbook instances
        """
        try:
            runbooks = FindingRunbook.objects.filter(
                tenant=tenant
            ).filter(
                Q(finding_type__icontains=finding_type.split('_')[0]) |  # Partial match on first keyword
                Q(category=category)
            ).exclude(
                finding_type=finding_type  # Exclude exact match (already shown)
            ).order_by('-usage_count', '-success_rate')[:limit]

            return list(runbooks)

        except (ValueError, AttributeError) as e:
            logger.error(f"Related runbooks error: {e}", exc_info=True)
            return []

    @classmethod
    def recommend_runbook_improvements(cls, runbook: FindingRunbook) -> List[str]:
        """
        Recommend improvements to a runbook based on usage stats.

        Args:
            runbook: FindingRunbook instance

        Returns:
            list: Recommendations for improvement
        """
        recommendations = []

        try:
            # Low success rate
            if runbook.usage_count >= 10 and runbook.success_rate < 70:
                recommendations.append(
                    f"Success rate is low ({runbook.success_rate:.1f}%). "
                    "Review and update remediation steps."
                )

            # High resolution time
            if runbook.usage_count >= 10 and runbook.avg_resolution_time_minutes > 60:
                recommendations.append(
                    f"Average resolution time is {runbook.avg_resolution_time_minutes:.0f} minutes. "
                    "Consider adding automation or more specific guidance."
                )

            # Rarely used
            if runbook.usage_count == 0:
                recommendations.append(
                    "Runbook has never been used. Consider reviewing relevance or promoting awareness."
                )

            # Missing auto-actions
            if runbook.usage_count >= 5 and not runbook.auto_action_enabled and runbook.success_rate >= 80:
                recommendations.append(
                    f"High success rate ({runbook.success_rate:.1f}%) and stable usage. "
                    "Consider enabling auto-actions for faster response."
                )

            # Needs more steps
            if len(runbook.steps) < 3:
                recommendations.append(
                    "Runbook has very few steps. Consider adding more detailed guidance."
                )

            return recommendations

        except (ValueError, AttributeError) as e:
            logger.error(f"Runbook improvement recommendations error: {e}", exc_info=True)
            return []
