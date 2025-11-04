"""
Management command to warm ticket system caches.

Pre-populates frequently accessed data in Redis cache to improve
initial response times and reduce database load.

Usage: python manage.py warm_ticket_cache [options]
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
import logging

from apps.y_helpdesk.models import Ticket, EscalationMatrix
from apps.y_helpdesk.services.ticket_cache_service import TicketCacheService
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Warm ticket system caches with frequently accessed data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cache-types',
            type=str,
            default='all',
            help='Comma-separated cache types to warm (ticket_list,dashboard_stats,escalation_matrix,all)'
        )
        parser.add_argument(
            '--business-units',
            type=str,
            help='Comma-separated business unit IDs to warm cache for'
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=30,
            help='Number of days back to warm cache for (default: 30)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force refresh cached data'
        )

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        cache_types = self._parse_cache_types(options['cache_types'])
        business_units = self._parse_business_units(options['business_units'])
        days_back = options['days_back']
        force_refresh = options['force']

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🔥 WARMING TICKET SYSTEM CACHES\n"
                f"{'='*40}\n"
            )
        )

        start_time = timezone.now()
        total_warmed = 0

        try:
            # Warm different cache types
            if 'escalation_matrix' in cache_types:
                count = self._warm_escalation_matrix_cache(business_units, force_refresh)
                total_warmed += count
                if self.verbosity >= 1:
                    self.stdout.write(f"✅ Escalation matrix cache warmed: {count} entries")

            if 'dashboard_stats' in cache_types:
                count = self._warm_dashboard_stats_cache(business_units, days_back, force_refresh)
                total_warmed += count
                if self.verbosity >= 1:
                    self.stdout.write(f"✅ Dashboard stats cache warmed: {count} entries")

            if 'ticket_list' in cache_types:
                count = self._warm_ticket_list_cache(business_units, days_back, force_refresh)
                total_warmed += count
                if self.verbosity >= 1:
                    self.stdout.write(f"✅ Ticket list cache warmed: {count} entries")

            if 'user_permissions' in cache_types:
                count = self._warm_user_permissions_cache(business_units, force_refresh)
                total_warmed += count
                if self.verbosity >= 1:
                    self.stdout.write(f"✅ User permissions cache warmed: {count} entries")

            # Display summary
            duration = timezone.now() - start_time
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n🎯 Cache warming completed!\n"
                    f"   Total entries warmed: {total_warmed}\n"
                    f"   Duration: {duration.total_seconds():.2f} seconds\n"
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Cache warming failed: {e}")
            )
            raise

    def _parse_cache_types(self, cache_types_str: str) -> list:
        """Parse cache types from command line argument."""
        if cache_types_str == 'all':
            return ['ticket_list', 'dashboard_stats', 'escalation_matrix', 'user_permissions']

        return [ct.strip() for ct in cache_types_str.split(',') if ct.strip()]

    def _parse_business_units(self, business_units_str: str) -> list:
        """Parse business unit IDs from command line argument."""
        if not business_units_str:
            # Get top 10 most active business units
            from apps.client_onboarding.models import Bt
            return list(
                Bt.objects.annotate(
                    ticket_count=models.Count('ticket')
                ).order_by('-ticket_count')[:10].values_list('id', flat=True)
            )

        return [int(bu.strip()) for bu in business_units_str.split(',') if bu.strip()]

    def _warm_escalation_matrix_cache(self, business_units: list, force_refresh: bool) -> int:
        """Warm escalation matrix cache."""
        from apps.client_onboarding.models import Bt

        warmed_count = 0

        for bu_id in business_units:
            try:
                bu = Bt.objects.get(id=bu_id)

                # Create cache key parameters for this business unit
                cache_key_params = {
                    'bu_id': bu_id,
                    'client_id': bu.client_id if hasattr(bu, 'client_id') else 1,
                    'tenant': 'default'
                }

                def load_escalation_data():
                    return list(
                        EscalationMatrix.objects.filter(
                            bu_id=bu_id
                        ).select_related(
                            'escalationtemplate', 'assignedperson', 'assignedgroup'
                        ).values(
                            'id', 'level', 'frequency', 'frequencyvalue',
                            'escalationtemplate__taname', 'assignedperson__peoplename',
                            'assignedgroup__groupname'
                        )
                    )

                # Warm the cache
                data = TicketCacheService.get_cached_data(
                    'escalation_matrix',
                    cache_key_params,
                    load_escalation_data,
                    force_refresh=force_refresh
                )

                if data:
                    warmed_count += 1

                if self.verbosity >= 2:
                    self.stdout.write(f"   Warmed escalation matrix for BU {bu_id}: {len(data)} rules")

            except Exception as e:
                if self.verbosity >= 1:
                    self.stdout.write(
                        self.style.WARNING(f"   Failed to warm escalation matrix for BU {bu_id}: {e}")
                    )

        return warmed_count

    def _warm_dashboard_stats_cache(self, business_units: list, days_back: int, force_refresh: bool) -> int:
        """Warm dashboard statistics cache."""
        from apps.client_onboarding.models import Bt

        warmed_count = 0
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)

        # Common date ranges for dashboard
        date_ranges = [
            (end_date - timedelta(days=7), end_date),  # Last 7 days
            (end_date - timedelta(days=30), end_date),  # Last 30 days
            (end_date - timedelta(days=90), end_date),  # Last 90 days
        ]

        for bu_id in business_units:
            try:
                bu = Bt.objects.get(id=bu_id)

                for start_dt, end_dt in date_ranges:
                    cache_key_params = {
                        'sites': str([bu_id]),
                        'client': bu.client_id if hasattr(bu, 'client_id') else 1,
                        'from': start_dt.isoformat(),
                        'to': end_dt.isoformat(),
                        'tenant': 'default'
                    }

                    def load_dashboard_stats():
                        from django.db.models import Count, Case, When, IntegerField

                        stats_query = Ticket.objects.filter(
                            bu_id=bu_id,
                            cdtz__date__gte=start_dt,
                            cdtz__date__lte=end_dt,
                        ).aggregate(
                            new=Count(Case(When(status="NEW", then=1), output_field=IntegerField())),
                            open=Count(Case(When(status="OPEN", then=1), output_field=IntegerField())),
                            resolved=Count(Case(When(status="RESOLVED", then=1), output_field=IntegerField())),
                            closed=Count(Case(When(status="CLOSED", then=1), output_field=IntegerField())),
                            total=Count('id')
                        )

                        return ([
                            stats_query["new"], stats_query["resolved"],
                            stats_query["open"], stats_query["closed"]
                        ], stats_query["total"])

                    # Warm the cache
                    TicketCacheService.get_cached_data(
                        'dashboard_stats',
                        cache_key_params,
                        load_dashboard_stats,
                        force_refresh=force_refresh
                    )

                    warmed_count += 1

                if self.verbosity >= 2:
                    self.stdout.write(f"   Warmed dashboard stats for BU {bu_id}: {len(date_ranges)} date ranges")

            except Exception as e:
                if self.verbosity >= 1:
                    self.stdout.write(
                        self.style.WARNING(f"   Failed to warm dashboard stats for BU {bu_id}: {e}")
                    )

        return warmed_count

    def _warm_ticket_list_cache(self, business_units: list, days_back: int, force_refresh: bool) -> int:
        """Warm ticket list cache for common scenarios."""
        from apps.client_onboarding.models import Bt

        warmed_count = 0
        end_date = timezone.now().date()

        # Common date ranges and status filters
        scenarios = [
            {'days': 7, 'status': ''},
            {'days': 7, 'status': 'NEW'},
            {'days': 7, 'status': 'OPEN'},
            {'days': 30, 'status': ''},
            {'days': 30, 'status': 'RESOLVED'},
        ]

        for bu_id in business_units:
            try:
                bu = Bt.objects.get(id=bu_id)

                for scenario in scenarios:
                    start_date = end_date - timedelta(days=scenario['days'])

                    cache_key_params = {
                        'from': start_date.isoformat(),
                        'to': end_date.isoformat(),
                        'sites': str([bu_id]),
                        'client': bu.client_id if hasattr(bu, 'client_id') else 1,
                        'status': scenario['status'],
                        'tenant': 'default'
                    }

                    def load_ticket_list():
                        qset = Ticket.objects.filter(
                            bu_id=bu_id,
                            cdtz__date__gte=start_date,
                            cdtz__date__lte=end_date
                        )

                        if scenario['status']:
                            qset = qset.filter(status=scenario['status'])

                        return list(qset.values(
                            'id', 'ticketno', 'ticketdesc', 'status', 'priority',
                            'cdtz', 'cuser__peoplename'
                        )[:50])  # Limit to first 50 for cache warming

                    # Warm the cache
                    TicketCacheService.get_cached_data(
                        'ticket_list',
                        cache_key_params,
                        load_ticket_list,
                        force_refresh=force_refresh
                    )

                    warmed_count += 1

                if self.verbosity >= 2:
                    self.stdout.write(f"   Warmed ticket lists for BU {bu_id}: {len(scenarios)} scenarios")

            except Exception as e:
                if self.verbosity >= 1:
                    self.stdout.write(
                        self.style.WARNING(f"   Failed to warm ticket lists for BU {bu_id}: {e}")
                    )

        return warmed_count

    def _warm_user_permissions_cache(self, business_units: list, force_refresh: bool) -> int:
        """Warm user permissions cache."""
        warmed_count = 0

        # Get active users from specified business units
        active_users = People.objects.filter(
            peopleorganizational__bu_id__in=business_units,
            enable=True
        ).distinct()[:50]  # Limit to 50 most recent users

        for user in active_users:
            try:
                cache_key_params = {
                    'user_id': user.id,
                    'bu_id': user.peopleorganizational.bu_id if hasattr(user, 'peopleorganizational') else None,
                    'tenant': 'default'
                }

                def load_user_permissions():
                    # This would load user's permissions and access rights
                    # For now, return placeholder data
                    return {
                        'can_assign_tickets': True,
                        'can_escalate_tickets': True,
                        'can_view_all_tickets': user.is_staff,
                        'accessible_bus': business_units
                    }

                # Warm the cache
                TicketCacheService.get_cached_data(
                    'user_permissions',
                    cache_key_params,
                    load_user_permissions,
                    force_refresh=force_refresh
                )

                warmed_count += 1

            except Exception as e:
                if self.verbosity >= 2:
                    self.stdout.write(
                        self.style.WARNING(f"   Failed to warm permissions for user {user.id}: {e}")
                    )

        return warmed_count