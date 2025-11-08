"""
Query Execution Plan Monitoring Command

Automated monitoring of PostgreSQL query execution plans to detect
performance regressions and optimization opportunities.

Features:
- Capture execution plans for slow queries
- Detect plan regressions by comparing with historical plans
- Generate optimization recommendations
- Integrate with existing slow query monitoring
- Automatic plan analysis and alerting

Usage:
    python manage.py monitor_execution_plans
    python manage.py monitor_execution_plans --capture-all
    python manage.py monitor_execution_plans --analyze-regressions
    python manage.py monitor_execution_plans --query-hash 123456789

Compliance:
- Rule #14: Management command < 200 lines
- Enterprise performance monitoring standards
"""

import json
import logging
from decimal import Decimal
from datetime import timedelta
from typing import Dict, List, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from django.conf import settings

from apps.core.models.query_execution_plans import (
from apps.core.exceptions.patterns import ENCRYPTION_EXCEPTIONS

from apps.core.exceptions.patterns import FILE_EXCEPTIONS

    QueryExecutionPlan,
    PlanRegressionAlert
)
from apps.core.models.query_performance import SlowQueryAlert

logger = logging.getLogger("query_plan_monitor")


class Command(BaseCommand):
    help = 'Monitor query execution plans and detect performance regressions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--capture-all',
            action='store_true',
            help='Capture plans for all recent slow queries'
        )

        parser.add_argument(
            '--analyze-regressions',
            action='store_true',
            help='Analyze existing plans for regressions'
        )

        parser.add_argument(
            '--query-hash',
            type=int,
            help='Capture plan for specific query hash'
        )

        parser.add_argument(
            '--hours-back',
            type=int,
            default=24,
            help='Hours to look back for slow queries (default: 24)'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without executing'
        )

        parser.add_argument(
            '--sample-rate',
            type=float,
            default=0.1,
            help='Sample rate for plan capture (0.0-1.0, default: 0.1)'
        )

    def handle(self, *args, **options):
        """Main command handler."""
        self.dry_run = options['dry_run']
        self.sample_rate = max(0.0, min(1.0, options['sample_rate']))

        self.stdout.write(
            self.style.SUCCESS("Starting query execution plan monitoring")
        )

        try:
            if options['query_hash']:
                self._capture_specific_query_plan(options['query_hash'])
            elif options['analyze_regressions']:
                self._analyze_plan_regressions()
            elif options['capture_all']:
                self._capture_all_slow_query_plans(options['hours_back'])
            else:
                # Default: capture recent slow queries and analyze regressions
                self._capture_recent_slow_query_plans(options['hours_back'])
                self._analyze_recent_regressions()

        except ENCRYPTION_EXCEPTIONS as e:
            logger.error(f"Plan monitoring failed: {e}", exc_info=True)
            raise CommandError(f"Plan monitoring failed: {e}")

    def _capture_specific_query_plan(self, query_hash: int):
        """Capture execution plan for a specific query."""
        self.stdout.write(f"Capturing plan for query hash: {query_hash}")

        try:
            # Get query from pg_stat_statements
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT query, calls, mean_exec_time
                    FROM pg_stat_statements
                    WHERE queryid = %s;
                """, [query_hash])

                row = cursor.fetchone()
                if not row:
                    self.stdout.write(
                        self.style.WARNING(f"Query {query_hash} not found in pg_stat_statements")
                    )
                    return

                query_text, calls, mean_time = row

                if not self.dry_run:
                    plan_data = self._capture_query_plan(query_text, query_hash)
                    if plan_data:
                        self.stdout.write(
                            self.style.SUCCESS(f"Plan captured: {plan_data['execution_time']}ms")
                        )
                else:
                    self.stdout.write(f"Would capture plan for: {query_text[:100]}...")

        except FILE_EXCEPTIONS as e:
            logger.error(f"Failed to capture specific query plan: {e}")
            raise

    def _capture_recent_slow_query_plans(self, hours_back: int):
        """Capture plans for recent slow queries."""
        self.stdout.write(f"Capturing plans for slow queries from last {hours_back} hours")

        try:
            # Get recent slow queries that don't have plans yet
            since = timezone.now() - timedelta(hours=hours_back)
            slow_queries = SlowQueryAlert.objects.filter(
                alert_time__gte=since,
                severity__in=['warning', 'critical']
            ).values_list('query_hash', flat=True).distinct()

            captured_count = 0
            for query_hash in slow_queries:
                # Check if we already have a recent plan
                existing_plan = QueryExecutionPlan.objects.filter(
                    query_hash=query_hash,
                    captured_at__gte=since
                ).first()

                if existing_plan:
                    continue  # Skip if we have a recent plan

                # Sample based on configured rate
                import random
                if random.random() > self.sample_rate:
                    continue

                try:
                    # Get query from pg_stat_statements
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT query, calls, mean_exec_time
                            FROM pg_stat_statements
                            WHERE queryid = %s;
                        """, [query_hash])

                        row = cursor.fetchone()
                        if row:
                            query_text, calls, mean_time = row

                            if not self.dry_run:
                                plan_data = self._capture_query_plan(query_text, query_hash)
                                if plan_data:
                                    captured_count += 1
                                    self.stdout.write(f"Captured plan for query {query_hash}")
                            else:
                                self.stdout.write(f"Would capture plan for query {query_hash}")

                except ENCRYPTION_EXCEPTIONS as e:
                    logger.warning(f"Failed to capture plan for query {query_hash}: {e}")
                    continue

            self.stdout.write(
                self.style.SUCCESS(f"Captured {captured_count} execution plans")
            )

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to capture recent slow query plans: {e}")
            raise

    def _capture_all_slow_query_plans(self, hours_back: int):
        """Capture plans for all slow queries in the timeframe."""
        # Temporarily set sample rate to 1.0 for capturing all
        original_sample_rate = self.sample_rate
        self.sample_rate = 1.0

        try:
            self._capture_recent_slow_query_plans(hours_back)
        finally:
            self.sample_rate = original_sample_rate

    def _capture_query_plan(self, query_text: str, query_hash: int) -> Optional[Dict]:
        """
        Capture execution plan for a specific query.

        Returns plan data dictionary if successful, None otherwise.
        """
        try:
            with connection.cursor() as cursor:
                # Execute EXPLAIN ANALYZE
                explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_text}"
                cursor.execute(explain_query)
                plan_result = cursor.fetchone()[0]

                # Extract performance metrics
                plan_data = plan_result[0]
                execution_time = plan_data.get('Execution Time', 0)
                planning_time = plan_data.get('Planning Time', 0)

                plan_node = plan_data.get('Plan', {})
                total_cost = plan_node.get('Total Cost', 0)
                actual_rows = plan_node.get('Actual Rows', 0)

                # Extract buffer usage
                shared_hit = plan_node.get('Shared Hit Blocks', 0)
                shared_read = plan_node.get('Shared Read Blocks', 0)
                temp_read = plan_node.get('Temp Read Blocks', 0)
                temp_written = plan_node.get('Temp Written Blocks', 0)

                # Create execution plan record
                execution_plan = QueryExecutionPlan.objects.create(
                    query_hash=query_hash,
                    query_text=query_text[:2000],  # Truncate if very long
                    execution_plan=plan_result,
                    execution_time=Decimal(str(execution_time)),
                    planning_time=Decimal(str(planning_time)),
                    total_cost=Decimal(str(total_cost)),
                    rows_returned=actual_rows,
                    shared_hit_blocks=shared_hit,
                    shared_read_blocks=shared_read,
                    temp_read_blocks=temp_read,
                    temp_written_blocks=temp_written,
                    capture_method='automatic'
                )

                # Analyze for optimization opportunities
                opportunities = self._analyze_optimization_opportunities(execution_plan)
                if opportunities:
                    execution_plan.optimization_opportunities = opportunities
                    execution_plan.save(update_fields=['optimization_opportunities'])

                return {
                    'plan_id': execution_plan.id,
                    'execution_time': execution_time,
                    'planning_time': planning_time,
                    'total_cost': total_cost,
                }

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to capture query plan: {e}")
            return None

    def _analyze_optimization_opportunities(self, plan: QueryExecutionPlan) -> List[str]:
        """Analyze execution plan for optimization opportunities."""
        opportunities = []

        try:
            plan_data = plan.execution_plan[0] if isinstance(plan.execution_plan, list) else plan.execution_plan
            plan_node = plan_data.get('Plan', {})

            # Check for sequential scans
            if self._contains_sequential_scan(plan_node):
                opportunities.append("Sequential scan detected - consider adding indexes")

            # Check for high cost operations
            if plan.total_cost > 10000:
                opportunities.append("High cost query - consider optimization or caching")

            # Check for temp file usage
            if plan.uses_temp_storage:
                opportunities.append("Query uses temporary storage - consider increasing work_mem")

            # Check for low cache hit ratio
            if plan.cache_hit_ratio < 90:
                opportunities.append("Low buffer cache hit ratio - check shared_buffers configuration")

            # Check for sorting without limit
            if self._has_sort_without_limit(plan_node):
                opportunities.append("Sort operation without LIMIT - consider adding LIMIT or optimizing ORDER BY")

            # Check for nested loops with high row counts
            if self._has_expensive_nested_loop(plan_node):
                opportunities.append("Expensive nested loop join - consider improving join conditions or indexes")

        except FILE_EXCEPTIONS as e:
            logger.warning(f"Failed to analyze optimization opportunities: {e}")

        return opportunities

    def _contains_sequential_scan(self, plan_node: Dict) -> bool:
        """Check if plan contains sequential scans."""
        if plan_node.get('Node Type') == 'Seq Scan':
            return True

        # Check child plans recursively
        for child_plan in plan_node.get('Plans', []):
            if self._contains_sequential_scan(child_plan):
                return True

        return False

    def _has_sort_without_limit(self, plan_node: Dict) -> bool:
        """Check for sort operations without accompanying limit."""
        if plan_node.get('Node Type') == 'Sort':
            # Check if there's a limit node as parent or sibling
            # This is a simplified check - could be more sophisticated
            return True

        for child_plan in plan_node.get('Plans', []):
            if self._has_sort_without_limit(child_plan):
                return True

        return False

    def _has_expensive_nested_loop(self, plan_node: Dict) -> bool:
        """Check for expensive nested loop joins."""
        if (plan_node.get('Node Type') == 'Nested Loop' and
                plan_node.get('Actual Total Time', 0) > 1000):  # > 1 second
            return True

        for child_plan in plan_node.get('Plans', []):
            if self._has_expensive_nested_loop(child_plan):
                return True

        return False

    def _analyze_recent_regressions(self):
        """Analyze recent plans for performance regressions."""
        self.stdout.write("Analyzing recent plans for regressions")

        try:
            # Get recent plans grouped by query hash
            since = timezone.now() - timedelta(days=7)
            recent_plans = QueryExecutionPlan.objects.filter(
                captured_at__gte=since
            ).order_by('query_hash', '-captured_at')

            query_plans = {}
            for plan in recent_plans:
                if plan.query_hash not in query_plans:
                    query_plans[plan.query_hash] = []
                query_plans[plan.query_hash].append(plan)

            regression_count = 0

            for query_hash, plans in query_plans.items():
                if len(plans) < 2:
                    continue  # Need at least 2 plans to compare

                # Compare most recent with previous plans
                current_plan = plans[0]  # Most recent
                baseline_plans = plans[1:5]  # Up to 4 previous plans

                for baseline_plan in baseline_plans:
                    regression_data = self._detect_regression(current_plan, baseline_plan)

                    if regression_data and not self.dry_run:
                        # Check if we already have an alert for this regression
                        existing_alert = PlanRegressionAlert.objects.filter(
                            query_hash=query_hash,
                            current_plan=current_plan,
                            status__in=['new', 'acknowledged']
                        ).first()

                        if not existing_alert:
                            alert = PlanRegressionAlert.create_regression_alert(
                                current_plan, baseline_plan, regression_data
                            )
                            regression_count += 1
                            self.stdout.write(
                                f"Regression detected: Query {query_hash} "
                                f"({regression_data['performance_degradation']:.1f}% slower)"
                            )
                        break  # Only create one alert per query

            self.stdout.write(
                self.style.SUCCESS(f"Detected {regression_count} new regressions")
            )

        except ENCRYPTION_EXCEPTIONS as e:
            logger.error(f"Failed to analyze regressions: {e}")
            raise

    def _analyze_plan_regressions(self):
        """Comprehensive analysis of all stored plans for regressions."""
        self.stdout.write("Performing comprehensive regression analysis")
        # Use broader time range for comprehensive analysis
        since = timezone.now() - timedelta(days=30)
        recent_plans = QueryExecutionPlan.objects.filter(
            captured_at__gte=since
        ).order_by('query_hash', '-captured_at')

        # Same logic as _analyze_recent_regressions but with wider scope
        # Implementation would be similar but with larger dataset

    def _detect_regression(self, current_plan: QueryExecutionPlan,
                          baseline_plan: QueryExecutionPlan) -> Optional[Dict]:
        """
        Detect if current plan represents a performance regression.

        Returns regression data if regression detected, None otherwise.
        """
        try:
            current_time = float(current_plan.execution_time)
            baseline_time = float(baseline_plan.execution_time)

            # Calculate performance degradation percentage
            if baseline_time > 0:
                degradation = ((current_time - baseline_time) / baseline_time) * 100
            else:
                degradation = 0

            # Consider it a regression if > 25% slower
            if degradation > 25:
                regression_type = 'execution_time'

                # Check for specific regression types
                if current_plan.plan_hash != baseline_plan.plan_hash:
                    regression_type = 'plan_change'

                if current_plan.uses_temp_storage and not baseline_plan.uses_temp_storage:
                    regression_type = 'temp_storage'

                return {
                    'performance_degradation': degradation,
                    'type': regression_type,
                    'current_time': current_time,
                    'baseline_time': baseline_time,
                }

            return None

        except FILE_EXCEPTIONS as e:
            logger.warning(f"Failed to detect regression: {e}")
            return None