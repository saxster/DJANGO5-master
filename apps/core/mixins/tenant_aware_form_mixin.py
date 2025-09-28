"""
Tenant-Aware Form Mixin

Eliminates duplicated form queryset filtering patterns found in 200+ lines
across 6 form files.

Following .claude/rules.md:
- Form size < 100 lines (Rule 8)
- Specific exception handling (Rule 11)
- Secure tenant isolation
- Single responsibility principle
"""

import logging
from typing import Dict, Any, Optional
from django.db.models import Q
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

__all__ = [
    'TenantAwareFormMixin',
]


class TenantAwareFormMixin:
    """
    Mixin for automatic tenant-aware queryset filtering in forms.

    Automatically filters querysets for ForeignKey/ManyToMany fields
    based on session tenant scope (client_id, bu_id).

    Usage:
        class AssetForm(TenantAwareFormMixin, forms.ModelForm):
            tenant_filtered_fields = {
                'parent': {
                    'model': Asset,
                    'filter_by': 'bu_id',
                    'extra_filters': Q(runningstatus__ne='SCRAPPED'),
                },
                'location': {
                    'model': Location,
                    'filter_by': 'bu_id',
                    'extra_filters': Q(locstatus__ne='SCRAPPED'),
                },
                'type': {
                    'model': TypeAssist,
                    'filter_by': 'client_id',
                    'extra_filters': Q(tatype__tacode='ASSETTYPE'),
                },
            }

            def __init__(self, *args, **kwargs):
                self.request = kwargs.pop('request')
                super().__init__(*args, **kwargs)
                self.apply_tenant_filters()
    """

    tenant_filtered_fields: Dict[str, Dict[str, Any]] = {}

    def apply_tenant_filters(self):
        """
        Apply tenant filtering to configured form fields.

        Automatically filters querysets based on session tenant scope.
        """
        if not hasattr(self, 'request'):
            logger.warning(
                f"{self.__class__.__name__}: Cannot apply tenant filters without request"
            )
            return

        session = self.request.session
        filters_applied = 0

        for field_name, config in self.get_tenant_filtered_fields().items():
            if field_name not in self.fields:
                continue

            try:
                queryset = self._build_filtered_queryset(config, session)
                self.fields[field_name].queryset = queryset
                filters_applied += 1

            except (KeyError, ValueError, AttributeError) as e:
                logger.error(
                    f"Failed to apply tenant filter to {field_name}: {e}",
                    extra={'form': self.__class__.__name__, 'field': field_name}
                )

        logger.debug(
            f"Applied {filters_applied} tenant filters to {self.__class__.__name__}"
        )

    def get_tenant_filtered_fields(self) -> Dict[str, Dict[str, Any]]:
        """Get tenant filtered field configuration. Override to customize."""
        return self.tenant_filtered_fields

    def _build_filtered_queryset(self, config: Dict[str, Any], session: Dict[str, Any]):
        """
        Build filtered queryset for a field.

        Args:
            config: Field filter configuration
            session: Request session data

        Returns:
            Filtered queryset
        """
        model = config.get('model')
        if not model:
            raise ValueError("Field config must include 'model'")

        filter_by = config.get('filter_by', 'bu_id')
        extra_filters = config.get('extra_filters', Q())
        select_related = config.get('select_related', [])

        filter_value = self._get_session_filter_value(filter_by, session)

        queryset = model.objects.all()

        if select_related:
            queryset = queryset.select_related(*select_related)

        if filter_value:
            queryset = queryset.filter(**{filter_by: filter_value})

        if extra_filters:
            queryset = queryset.filter(extra_filters)

        return queryset

    def _get_session_filter_value(self, filter_by: str, session: Dict[str, Any]):
        """
        Get filter value from session.

        Args:
            filter_by: Field to filter by (e.g., 'bu_id', 'client_id')
            session: Request session

        Returns:
            Filter value or None
        """
        session_key_map = {
            'bu_id': 'bu_id',
            'client_id': 'client_id',
            'sites': 'assignedsites',
        }

        session_key = session_key_map.get(filter_by, filter_by)
        return session.get(session_key)


class TypeAssistFilterMixin:
    """
    Specialized mixin for TypeAssist field filtering.

    Common pattern for filtering TypeAssist fields by tatype__tacode.
    """

    def apply_typeassist_filters(self, field_mapping: Dict[str, str]):
        """
        Apply TypeAssist filters to form fields.

        Args:
            field_mapping: Dict of {field_name: tacode_value}
                          e.g., {'type': 'ASSETTYPE', 'category': 'ASSETCATEGORY'}
        """
        if not hasattr(self, 'request'):
            return

        session = self.request.session
        client_id = session.get('client_id')

        from apps.onboarding.models import TypeAssist

        for field_name, tacode in field_mapping.items():
            if field_name not in self.fields:
                continue

            self.fields[field_name].queryset = TypeAssist.objects.select_related(
                'tatype'
            ).filter(
                Q(tatype__tacode=tacode) | Q(tatype__tacode=tacode.replace('_', '')),
                client_id=client_id
            )