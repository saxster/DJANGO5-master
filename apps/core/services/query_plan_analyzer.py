"""
Query Execution Plan Analysis Service

Service for integrating execution plan monitoring with slow query detection.
Automatically captures and analyzes execution plans when performance issues
are detected.

Features:
- Automatic plan capture for slow queries
- Plan regression detection
- Optimization recommendation generation
- Integration with existing monitoring systems

Compliance:
- Rule #7: Service class < 150 lines
- Rule #14: Utility functions < 50 lines
- Enterprise monitoring standards
"""

import json
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import timedelta

from django.db import connection
from django.utils import timezone
from django.core.cache import cache

from apps.core.models.query_execution_plans import QueryExecutionPlan, PlanRegressionAlert
from apps.core.models.query_performance import SlowQueryAlert

logger = logging.getLogger("query_plan_analyzer")


class QueryPlanAnalyzer:
    """
    Service for analyzing query execution plans and detecting regressions.

    Integrates with slow query monitoring to provide comprehensive
    performance analysis capabilities.
    """

    def __init__(self):
        self.plan_capture_enabled = True
        self.sample_rate = 0.1  # Capture plans for 10% of slow queries
        self.regression_threshold = 25.0  # 25% degradation threshold

    def analyze_slow_query(self, slow_query_alert: SlowQueryAlert) -> Optional[QueryExecutionPlan]:
        """
        Analyze a slow query alert and optionally capture execution plan.

        Args:
            slow_query_alert: SlowQueryAlert instance to analyze

        Returns:
            QueryExecutionPlan if plan was captured, None otherwise
        """
        try:
            # Sample-based plan capture to avoid overhead
            if not self._should_capture_plan(slow_query_alert):
                return None

            # Get query from pg_stat_statements
            query_text = self._get_query_text(slow_query_alert.query_hash)
            if not query_text:
                logger.warning(f"Query text not found for hash {slow_query_alert.query_hash}")
                return None

            # Capture execution plan
            execution_plan = self._capture_execution_plan(
                query_text,
                slow_query_alert.query_hash,
                capture_method='automatic'
            )

            if execution_plan:
                # Check for regressions against previous plans
                self._check_for_regression(execution_plan)

                logger.info(f"Captured plan for slow query {slow_query_alert.query_hash}")

            return execution_plan

        except Exception as e:
            logger.error(f"Failed to analyze slow query {slow_query_alert.query_hash}: {e}")
            return None

    def capture_manual_plan(self, query_text: str, query_hash: int, user=None) -> Optional[QueryExecutionPlan]:
        """
        Manually capture execution plan for a specific query.

        Args:
            query_text: SQL query text
            query_hash: Query hash identifier
            user: User requesting the capture

        Returns:
            QueryExecutionPlan if successful, None otherwise
        """
        try:
            execution_plan = self._capture_execution_plan(
                query_text,
                query_hash,
                capture_method='manual',
                captured_by=user
            )

            if execution_plan:
                logger.info(f"Manually captured plan for query {query_hash}")

            return execution_plan

        except Exception as e:
            logger.error(f"Failed to manually capture plan for query {query_hash}: {e}")
            return None

    def _should_capture_plan(self, slow_query_alert: SlowQueryAlert) -> bool:
        """Determine if we should capture plan for this slow query."""
        # Always capture for critical alerts
        if slow_query_alert.severity == 'critical':
            return True

        # Check if we already have a recent plan
        recent_plan_exists = QueryExecutionPlan.objects.filter(
            query_hash=slow_query_alert.query_hash,
            captured_at__gte=timezone.now() - timedelta(hours=24)
        ).exists()

        if recent_plan_exists:
            return False

        # Sample-based capture for other alerts
        import random
        return random.random() < self.sample_rate

    def _get_query_text(self, query_hash: int) -> Optional[str]:
        """Get query text from pg_stat_statements."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT query
                    FROM pg_stat_statements
                    WHERE queryid = %s;
                """, [query_hash])

                row = cursor.fetchone()
                return row[0] if row else None

        except Exception as e:
            logger.error(f"Failed to get query text for hash {query_hash}: {e}")
            return None

    def _capture_execution_plan(self, query_text: str, query_hash: int,
                               capture_method: str = 'automatic',
                               captured_by=None) -> Optional[QueryExecutionPlan]:
        """Capture execution plan for a query."""
        try:
            with connection.cursor() as cursor:
                # Execute EXPLAIN ANALYZE with resource tracking
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

                # Extract buffer usage recursively from all nodes
                buffer_stats = self._extract_buffer_stats(plan_node)

                # Create execution plan record
                execution_plan = QueryExecutionPlan.objects.create(
                    query_hash=query_hash,
                    query_text=query_text[:2000],  # Truncate long queries
                    execution_plan=plan_result,
                    execution_time=Decimal(str(execution_time)),
                    planning_time=Decimal(str(planning_time)),
                    total_cost=Decimal(str(total_cost)),
                    rows_returned=actual_rows,
                    shared_hit_blocks=buffer_stats['shared_hit'],
                    shared_read_blocks=buffer_stats['shared_read'],
                    temp_read_blocks=buffer_stats['temp_read'],
                    temp_written_blocks=buffer_stats['temp_written'],
                    capture_method=capture_method,
                    captured_by=captured_by
                )

                # Generate optimization opportunities
                opportunities = self._analyze_plan_for_optimizations(execution_plan)
                if opportunities:
                    execution_plan.optimization_opportunities = opportunities
                    execution_plan.save(update_fields=['optimization_opportunities'])

                return execution_plan

        except Exception as e:
            logger.error(f"Failed to capture execution plan: {e}")
            return None

    def _extract_buffer_stats(self, plan_node: Dict) -> Dict[str, int]:
        """Extract buffer statistics from plan node and its children."""
        stats = {
            'shared_hit': plan_node.get('Shared Hit Blocks', 0),
            'shared_read': plan_node.get('Shared Read Blocks', 0),
            'temp_read': plan_node.get('Temp Read Blocks', 0),
            'temp_written': plan_node.get('Temp Written Blocks', 0),
        }

        # Recursively sum stats from child plans
        for child_plan in plan_node.get('Plans', []):
            child_stats = self._extract_buffer_stats(child_plan)
            for key in stats:
                stats[key] += child_stats[key]

        return stats

    def _analyze_plan_for_optimizations(self, plan: QueryExecutionPlan) -> List[str]:
        """Generate optimization recommendations for an execution plan."""
        opportunities = []

        try:
            plan_data = plan.execution_plan[0]
            plan_node = plan_data.get('Plan', {})

            # Check for common optimization opportunities
            opportunities.extend(self._check_index_opportunities(plan_node))
            opportunities.extend(self._check_join_opportunities(plan_node))
            opportunities.extend(self._check_resource_opportunities(plan))

        except Exception as e:
            logger.warning(f"Failed to analyze plan optimizations: {e}")

        return opportunities

    def _check_index_opportunities(self, plan_node: Dict) -> List[str]:
        """Check for index-related optimization opportunities."""
        opportunities = []

        # Check for sequential scans
        if self._find_sequential_scans(plan_node):
            opportunities.append("Sequential scans detected - consider adding indexes")

        # Check for index scans with high cost
        if plan_node.get('Node Type') == 'Index Scan' and plan_node.get('Total Cost', 0) > 1000:
            opportunities.append("High-cost index scan - verify index selectivity")

        return opportunities

    def _check_join_opportunities(self, plan_node: Dict) -> List[str]:
        """Check for join-related optimization opportunities."""
        opportunities = []

        # Check for expensive nested loops
        if (plan_node.get('Node Type') == 'Nested Loop' and
                plan_node.get('Actual Total Time', 0) > 1000):
            opportunities.append("Expensive nested loop - consider hash or merge join")

        # Check for hash joins with large memory usage
        if (plan_node.get('Node Type') == 'Hash Join' and
                plan_node.get('Peak Memory Usage', 0) > 100000):  # > 100MB
            opportunities.append("Large hash join - consider increasing work_mem")

        return opportunities

    def _check_resource_opportunities(self, plan: QueryExecutionPlan) -> List[str]:
        """Check for resource-related optimization opportunities."""
        opportunities = []

        # Check cache hit ratio
        if plan.cache_hit_ratio < 90:
            opportunities.append("Low buffer cache hit ratio - consider tuning shared_buffers")

        # Check temp storage usage
        if plan.uses_temp_storage:
            opportunities.append("Temporary storage used - consider increasing work_mem")

        # Check execution time vs cost correlation
        if float(plan.execution_time) > 0 and float(plan.total_cost) > 0:
            time_to_cost_ratio = float(plan.execution_time) / float(plan.total_cost)
            if time_to_cost_ratio > 1.0:  # Execution time much higher than estimated
                opportunities.append("Actual time exceeds cost estimate - update table statistics")

        return opportunities

    def _find_sequential_scans(self, plan_node: Dict) -> bool:
        """Recursively find sequential scans in plan."""
        if plan_node.get('Node Type') == 'Seq Scan':
            return True

        for child_plan in plan_node.get('Plans', []):
            if self._find_sequential_scans(child_plan):
                return True

        return False

    def _check_for_regression(self, current_plan: QueryExecutionPlan) -> None:
        """Check if current plan represents a regression."""
        try:
            # Get recent plans for comparison (last 7 days)
            since = timezone.now() - timedelta(days=7)
            previous_plans = QueryExecutionPlan.objects.filter(
                query_hash=current_plan.query_hash,
                captured_at__gte=since,
                captured_at__lt=current_plan.captured_at
            ).order_by('-captured_at')[:5]  # Compare with up to 5 recent plans

            for baseline_plan in previous_plans:
                regression_data = self._detect_performance_regression(current_plan, baseline_plan)

                if regression_data:
                    # Check if we already have an alert for this regression
                    existing_alert = PlanRegressionAlert.objects.filter(
                        query_hash=current_plan.query_hash,
                        current_plan=current_plan,
                        status__in=['new', 'acknowledged']
                    ).first()

                    if not existing_alert:
                        PlanRegressionAlert.create_regression_alert(
                            current_plan, baseline_plan, regression_data
                        )
                        logger.warning(
                            f"Performance regression detected for query {current_plan.query_hash}: "
                            f"{regression_data['performance_degradation']:.1f}% slower"
                        )

                    # Only create one alert per query
                    break

        except Exception as e:
            logger.error(f"Failed to check for regression: {e}")

    def _detect_performance_regression(self, current_plan: QueryExecutionPlan,
                                     baseline_plan: QueryExecutionPlan) -> Optional[Dict]:
        """Detect performance regression between two plans."""
        try:
            current_time = float(current_plan.execution_time)
            baseline_time = float(baseline_plan.execution_time)

            if baseline_time <= 0:
                return None

            # Calculate performance degradation
            degradation = ((current_time - baseline_time) / baseline_time) * 100

            if degradation > self.regression_threshold:
                regression_type = 'execution_time'

                # Determine specific regression type
                if current_plan.plan_hash != baseline_plan.plan_hash:
                    regression_type = 'plan_change'
                elif current_plan.uses_temp_storage and not baseline_plan.uses_temp_storage:
                    regression_type = 'temp_storage'
                elif self._plan_lost_index_usage(current_plan, baseline_plan):
                    regression_type = 'index_not_used'

                return {
                    'performance_degradation': degradation,
                    'type': regression_type,
                    'current_time': current_time,
                    'baseline_time': baseline_time,
                }

            return None

        except Exception as e:
            logger.warning(f"Failed to detect regression: {e}")
            return None

    def _plan_lost_index_usage(self, current_plan: QueryExecutionPlan,
                              baseline_plan: QueryExecutionPlan) -> bool:
        """Check if current plan lost index usage compared to baseline."""
        try:
            # Simplified check - could be more sophisticated
            current_has_seqscan = 'Seq Scan' in str(current_plan.execution_plan)
            baseline_has_seqscan = 'Seq Scan' in str(baseline_plan.execution_plan)

            return current_has_seqscan and not baseline_has_seqscan

        except Exception:
            return False