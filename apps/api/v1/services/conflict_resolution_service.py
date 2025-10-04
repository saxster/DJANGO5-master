"""
Conflict Auto-Resolution Engine for Mobile Offline Sync

Implements smart resolution strategies based on domain-specific policies.
Supports per-tenant configuration for flexibility.

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
from django.db import transaction, DatabaseError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils import timezone
from typing import Dict, Any, Optional, Literal

from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)

PolicyType = Literal['client_wins', 'server_wins', 'most_recent_wins', 'preserve_escalation', 'manual']


class ConflictResolutionService:
    """
    Smart conflict resolution for mobile sync operations.

    Resolution Policies:
    - client_wins: User's device is authoritative (e.g., journal entries)
    - server_wins: Organization is authoritative (e.g., attendance records)
    - most_recent_wins: Latest timestamp wins (e.g., tasks, work orders)
    - preserve_escalation: Complex merge for escalated items (e.g., tickets)
    - manual: Requires human intervention
    """

    DEFAULT_POLICIES: Dict[str, PolicyType] = {
        'journal': 'client_wins',
        'attendance': 'server_wins',
        'task': 'most_recent_wins',
        'ticket': 'preserve_escalation',
        'work_order': 'most_recent_wins',
    }

    def resolve_conflict(
        self,
        domain: str,
        server_entry: Dict[str, Any],
        client_entry: Dict[str, Any],
        tenant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Resolve sync conflict using domain-specific policy.

        Args:
            domain: Data domain (journal, attendance, task, etc.)
            server_entry: Current server version with metadata
            client_entry: Client's version with metadata
            tenant_id: Tenant ID for custom policy lookup

        Returns:
            {
                resolution: 'resolved' | 'manual_required',
                winning_entry: {...},
                strategy_used: str,
                merge_details: {...}
            }
        """
        try:
            policy = self._get_policy(domain, tenant_id)

            if policy == 'client_wins':
                return self._apply_client_version(server_entry, client_entry)
            elif policy == 'server_wins':
                return self._apply_server_version(server_entry, client_entry)
            elif policy == 'most_recent_wins':
                return self._apply_most_recent(server_entry, client_entry)
            elif policy == 'preserve_escalation':
                return self._smart_merge(server_entry, client_entry)
            else:
                return self._require_manual_resolution(server_entry, client_entry)

        except (ValidationError, KeyError) as e:
            logger.error(f"Conflict resolution failed for domain {domain}: {e}")
            raise ValidationError(f"Resolution failed: {e}")

    def _get_policy(self, domain: str, tenant_id: Optional[int]) -> PolicyType:
        """Get resolution policy for domain, checking tenant overrides."""
        if tenant_id:
            try:
                from apps.core.models.sync_conflict_policy import TenantConflictPolicy
                custom_policy = TenantConflictPolicy.objects.filter(
                    tenant_id=tenant_id,
                    domain=domain,
                    auto_resolve=True
                ).first()

                if custom_policy:
                    return custom_policy.resolution_policy
            except (DatabaseError, ObjectDoesNotExist) as e:
                logger.warning(f"Failed to fetch tenant policy: {e}")

        return self.DEFAULT_POLICIES.get(domain, 'manual')

    def _apply_client_version(
        self, server_entry: Dict[str, Any], client_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Client wins - user's device is authoritative."""
        return {
            'resolution': 'resolved',
            'winning_entry': client_entry,
            'strategy_used': 'client_wins',
            'merge_details': {
                'server_version_discarded': server_entry.get('version'),
                'reason': 'User data takes precedence'
            }
        }

    def _apply_server_version(
        self, server_entry: Dict[str, Any], client_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Server wins - organization is authoritative."""
        return {
            'resolution': 'resolved',
            'winning_entry': server_entry,
            'strategy_used': 'server_wins',
            'merge_details': {
                'client_version_rejected': client_entry.get('version'),
                'reason': 'Organization data takes precedence'
            }
        }

    def _apply_most_recent(
        self, server_entry: Dict[str, Any], client_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Most recent timestamp wins."""
        server_ts = server_entry.get('updated_at', '')
        client_ts = client_entry.get('updated_at', '')

        if client_ts > server_ts:
            winning_entry = client_entry
            strategy = 'most_recent_wins (client)'
        else:
            winning_entry = server_entry
            strategy = 'most_recent_wins (server)'

        return {
            'resolution': 'resolved',
            'winning_entry': winning_entry,
            'strategy_used': strategy,
            'merge_details': {
                'server_timestamp': server_ts,
                'client_timestamp': client_ts
            }
        }

    def _smart_merge(
        self, server_entry: Dict[str, Any], client_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Smart merge preserving critical fields like escalation status."""
        merged = client_entry.copy()

        critical_fields = ['escalation_level', 'escalated_at', 'escalated_by', 'status']
        for field in critical_fields:
            if field in server_entry:
                merged[field] = server_entry[field]

        return {
            'resolution': 'resolved',
            'winning_entry': merged,
            'strategy_used': 'preserve_escalation',
            'merge_details': {
                'fields_preserved_from_server': critical_fields,
                'reason': 'Critical escalation data retained'
            }
        }

    def _require_manual_resolution(
        self, server_entry: Dict[str, Any], client_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Flag conflict for manual resolution."""
        return {
            'resolution': 'manual_required',
            'winning_entry': None,
            'strategy_used': 'manual',
            'merge_details': {
                'server_entry': server_entry,
                'client_entry': client_entry,
                'reason': 'Requires human review'
            }
        }