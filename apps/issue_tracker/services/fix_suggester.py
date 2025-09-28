"""
AI-powered Fix Suggestion Engine
Generates actionable fix suggestions for detected anomalies
"""

import logging
from typing import Dict, Any, List

from ..models import AnomalySignature, FixSuggestion

logger = logging.getLogger('issue_tracker.fixes')


class FixSuggestionEngine:
    """
    Generates fix suggestions for anomalies based on patterns and ML models
    """

    def __init__(self):
        self.fix_templates = self._load_fix_templates()
        self.confidence_thresholds = {
            'auto_apply': 0.95,  # Only auto-apply if > 95% confident
            'suggest': 0.6,      # Suggest if > 60% confident
            'minimum': 0.3       # Only show if > 30% confident
        }

    def _load_fix_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load fix suggestion templates"""
        return {
            'database_index': {
                'template': '''
-- Add database index for improved query performance
CREATE INDEX CONCURRENTLY idx_{table}_{columns}
ON {table} ({columns});

-- Monitor index usage:
-- SELECT schemaname, tablename, indexname, idx_scan
-- FROM pg_stat_user_indexes WHERE indexname = 'idx_{table}_{columns}';
''',
                'steps': [
                    'Identify slow queries from logs',
                    'Create index with CONCURRENTLY to avoid blocking',
                    'Monitor index usage and query performance',
                    'Verify improvement in p95 latency'
                ],
                'risk_level': 'low',
                'auto_applicable': True
            },

            'serializer_update': {
                'template': '''
# Update serializer to handle schema changes
class {SerializerName}(serializers.ModelSerializer):
    # Add optional field handling
    new_field = serializers.CharField(required=False, allow_blank=True)

    def to_internal_value(self, data):
        # Handle backward compatibility
        if 'old_field_name' in data and 'new_field_name' not in data:
            data['new_field_name'] = data['old_field_name']
        return super().to_internal_value(data)

    class Meta:
        model = {ModelName}
        fields = '__all__'
''',
                'steps': [
                    'Identify schema mismatch from error logs',
                    'Add backward compatibility handling',
                    'Test with both old and new data formats',
                    'Deploy with feature flag if needed'
                ],
                'risk_level': 'medium',
                'auto_applicable': False
            },

            'connection_pool_tuning': {
                'template': '''
# Django database connection pool settings
DATABASES = {
    'default': {
        # ... existing config ...
        'OPTIONS': {
            'MAX_CONNS': 20,  # Increase from default
            'MIN_CONNS': 5,   # Maintain minimum connections
            'CONN_MAX_AGE': 600,  # Connection lifetime in seconds
        }
    }
}

# PostgreSQL connection pooling with pgbouncer
# /etc/pgbouncer/pgbouncer.ini:
# max_client_conn = 200
# default_pool_size = 50
# pool_mode = transaction
''',
                'steps': [
                    'Monitor current connection usage',
                    'Increase connection pool size gradually',
                    'Consider pgbouncer for connection pooling',
                    'Monitor connection metrics post-change'
                ],
                'risk_level': 'medium',
                'auto_applicable': False
            },

            'rate_limiting': {
                'template': '''
# Implement exponential backoff for rate limiting
import time
import random
from django.core.cache import cache

class ExponentialBackoff:
    def __init__(self, base_delay=1, max_delay=60, max_retries=5):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries

    def retry_with_backoff(self, func, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except RateLimitExceeded:
                if attempt == self.max_retries - 1:
                    raise

                # Calculate delay with jitter
                delay = min(
                    self.base_delay * (2 ** attempt),
                    self.max_delay
                )
                jitter = random.uniform(0, delay * 0.1)
                time.sleep(delay + jitter)
''',
                'steps': [
                    'Implement exponential backoff strategy',
                    'Add jitter to prevent thundering herd',
                    'Monitor retry success rates',
                    'Adjust backoff parameters based on results'
                ],
                'risk_level': 'low',
                'auto_applicable': True
            },

            'caching_strategy': {
                'template': '''
# Add caching to reduce database load
from django.core.cache import cache
from django.views.decorators.cache import cache_page

@cache_page(60 * 5)  # Cache for 5 minutes
def expensive_view(request):
    # Your view logic here
    pass

# Or use low-level caching
def get_expensive_data(key):
    cache_key = f"expensive_data:{key}"
    result = cache.get(cache_key)

    if result is None:
        result = expensive_database_query(key)
        cache.set(cache_key, result, timeout=300)  # 5 minutes

    return result
''',
                'steps': [
                    'Identify frequently accessed data',
                    'Implement appropriate caching strategy',
                    'Set reasonable cache TTL values',
                    'Monitor cache hit rates and performance'
                ],
                'risk_level': 'low',
                'auto_applicable': True
            },

            'memory_optimization': {
                'template': '''
# Memory optimization strategies

# 1. Use select_related for foreign key lookups
queryset = Model.objects.select_related('foreign_key')

# 2. Use prefetch_related for many-to-many
queryset = Model.objects.prefetch_related('many_to_many_field')

# 3. Use iterator() for large querysets
for obj in Model.objects.iterator(chunk_size=1000):
    process(obj)

# 4. Clear unused variables
del large_data_structure

# 5. Use __slots__ for classes with many instances
class OptimizedModel:
    __slots__ = ['field1', 'field2', 'field3']
''',
                'steps': [
                    'Profile memory usage to identify bottlenecks',
                    'Optimize database queries and data structures',
                    'Implement memory-efficient algorithms',
                    'Monitor memory usage and garbage collection'
                ],
                'risk_level': 'medium',
                'auto_applicable': False
            }
        }

    async def generate_suggestions(self, signature: AnomalySignature,
                                 rule: Dict[str, Any]) -> List[FixSuggestion]:
        """Generate fix suggestions for anomaly signature"""
        try:
            from asgiref.sync import sync_to_async

            suggestions = []
            rule_fixes = rule.get('fixes', [])

            for fix_config in rule_fixes:
                suggestion = await self._create_fix_suggestion(
                    signature, fix_config, rule
                )
                if suggestion:
                    suggestions.append(suggestion)

            # Generate additional context-aware suggestions
            additional_suggestions = await self._generate_context_suggestions(signature)
            suggestions.extend(additional_suggestions)

            logger.info(
                f"Generated {len(suggestions)} fix suggestions for {signature.anomaly_type}"
            )

            return suggestions

        except (ConnectionError, TimeoutError, ValueError, asyncio.CancelledError) as e:
            logger.error(f"Fix suggestion generation failed: {e}", exc_info=True)
            return []

    async def _create_fix_suggestion(self, signature: AnomalySignature,
                                   fix_config: Dict[str, Any],
                                   rule: Dict[str, Any]) -> FixSuggestion:
        """Create individual fix suggestion"""
        try:
            from asgiref.sync import sync_to_async

            fix_type = fix_config.get('type', 'code_fix')
            confidence = fix_config.get('confidence', 0.5)

            # Get template for this fix type
            template_key = self._get_template_key(fix_type)
            template = self.fix_templates.get(template_key, {})

            # Generate contextual title and description
            title = self._generate_title(signature, fix_type)
            description = self._generate_description(
                signature, fix_config, template
            )

            # Calculate priority score
            priority_score = self._calculate_priority(signature, confidence)

            suggestion = await sync_to_async(FixSuggestion.objects.create)(
                signature=signature,
                title=title,
                description=description,
                fix_type=fix_type,
                confidence=confidence,
                priority_score=priority_score,
                patch_template=template.get('template', ''),
                implementation_steps=template.get('steps', []),
                auto_applicable=template.get('auto_applicable', False),
                risk_level=template.get('risk_level', 'medium'),
                created_by='ai_assistant'
            )

            return suggestion

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, ValueError, asyncio.CancelledError) as e:
            logger.error(f"Fix suggestion creation failed: {e}")
            return None

    def _get_template_key(self, fix_type: str) -> str:
        """Map fix type to template key"""
        mapping = {
            'index': 'database_index',
            'serializer': 'serializer_update',
            'connection_pool': 'connection_pool_tuning',
            'rate_limit': 'rate_limiting',
            'caching': 'caching_strategy',
            'memory': 'memory_optimization'
        }
        return mapping.get(fix_type, 'database_index')

    def _generate_title(self, signature: AnomalySignature, fix_type: str) -> str:
        """Generate contextual title for fix suggestion"""
        titles = {
            'index': f'Add database index for {signature.endpoint_pattern}',
            'serializer': f'Update serializer for schema compatibility',
            'connection_pool': f'Optimize connection pool settings',
            'rate_limit': f'Implement backoff strategy for rate limits',
            'caching': f'Add caching to reduce {signature.anomaly_type}',
            'memory': f'Optimize memory usage for {signature.endpoint_pattern}'
        }

        return titles.get(fix_type, f'Fix {signature.anomaly_type} in {signature.endpoint_pattern}')

    def _generate_description(self, signature: AnomalySignature,
                            fix_config: Dict[str, Any],
                            template: Dict[str, Any]) -> str:
        """Generate detailed description for fix suggestion"""
        base_description = fix_config.get('suggestion', 'Apply fix to resolve anomaly')

        context_info = [
            f"Anomaly Type: {signature.anomaly_type}",
            f"Endpoint Pattern: {signature.endpoint_pattern}",
            f"Severity: {signature.severity}",
            f"Occurrences: {signature.occurrence_count}"
        ]

        if signature.mttr_seconds:
            context_info.append(f"Average Resolution Time: {signature.mttr_seconds // 60} minutes")

        description = f"{base_description}\\n\\n"
        description += "Context:\\n" + "\\n".join(f"• {info}" for info in context_info)

        if template.get('steps'):
            description += "\\n\\nImplementation Steps:\\n"
            description += "\\n".join(f"{i+1}. {step}" for i, step in enumerate(template['steps']))

        return description

    def _calculate_priority(self, signature: AnomalySignature, confidence: float) -> int:
        """Calculate priority score for fix suggestion"""
        # Base priority from severity
        severity_scores = {'info': 2, 'warning': 4, 'error': 7, 'critical': 10}
        base_score = severity_scores.get(signature.severity, 5)

        # Adjust for confidence
        confidence_multiplier = confidence

        # Adjust for recurrence
        recurrence_multiplier = min(signature.occurrence_count / 10, 2.0)

        priority = int(base_score * confidence_multiplier * recurrence_multiplier)
        return min(max(priority, 1), 10)  # Clamp between 1-10

    async def _generate_context_suggestions(self, signature: AnomalySignature) -> List[FixSuggestion]:
        """Generate additional context-aware suggestions"""
        suggestions = []

        try:
            # Latency-specific suggestions
            if 'latency' in signature.anomaly_type:
                suggestions.append(await self._suggest_performance_optimization(signature))

            # Error-specific suggestions
            if signature.severity in ['error', 'critical']:
                suggestions.append(await self._suggest_error_handling(signature))

            # Schema-related suggestions
            if 'schema' in signature.anomaly_type:
                suggestions.append(await self._suggest_schema_versioning(signature))

            # Filter out None suggestions
            return [s for s in suggestions if s is not None]

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, ValueError, asyncio.CancelledError) as e:
            logger.error(f"Context suggestion generation failed: {e}")
            return []

    async def _suggest_performance_optimization(self, signature: AnomalySignature) -> FixSuggestion:
        """Generate performance optimization suggestion"""
        from asgiref.sync import sync_to_async

        return await sync_to_async(FixSuggestion.objects.create)(
            signature=signature,
            title='Performance Optimization Bundle',
            description=f'''
Comprehensive performance optimization for {signature.endpoint_pattern}:

• Database query optimization with select_related/prefetch_related
• Response caching with appropriate TTL
• Connection pooling configuration
• Async processing for heavy operations
• Monitoring and alerting setup

This bundle addresses the root causes of latency issues systematically.
''',
            fix_type='configuration',
            confidence=0.75,
            priority_score=6,
            auto_applicable=False,
            risk_level='medium',
            created_by='ai_assistant'
        )

    async def _suggest_error_handling(self, signature: AnomalySignature) -> FixSuggestion:
        """Generate error handling improvement suggestion"""
        from asgiref.sync import sync_to_async

        return await sync_to_async(FixSuggestion.objects.create)(
            signature=signature,
            title='Enhanced Error Handling',
            description=f'''
Improve error handling for {signature.endpoint_pattern}:

• Implement circuit breaker pattern
• Add structured error logging
• Create user-friendly error responses
• Set up error alerting and monitoring
• Add graceful degradation strategies

This reduces error impact and improves debugging capabilities.
''',
            fix_type='code_fix',
            confidence=0.80,
            priority_score=7,
            auto_applicable=False,
            risk_level='low',
            created_by='ai_assistant'
        )

    async def _suggest_schema_versioning(self, signature: AnomalySignature) -> FixSuggestion:
        """Generate schema versioning suggestion"""
        from asgiref.sync import sync_to_async

        return await sync_to_async(FixSuggestion.objects.create)(
            signature=signature,
            title='Schema Version Management',
            description=f'''
Implement schema versioning for {signature.endpoint_pattern}:

• Add API versioning headers
• Implement backward-compatible serializers
• Create schema migration strategy
• Set up schema validation with fallbacks
• Document breaking changes and migrations

This prevents future schema-related issues and improves API stability.
''',
            fix_type='schema_update',
            confidence=0.85,
            priority_score=8,
            auto_applicable=False,
            risk_level='medium',
            created_by='ai_assistant'
        )

    def get_suggestion_stats(self) -> Dict[str, Any]:
        """Get fix suggestion statistics"""
        try:
            from django.db.models import Count, Avg

            stats = {
                'total_suggestions': FixSuggestion.objects.count(),
                'by_status': dict(
                    FixSuggestion.objects.values('status')
                    .annotate(count=Count('id'))
                    .values_list('status', 'count')
                ),
                'by_fix_type': dict(
                    FixSuggestion.objects.values('fix_type')
                    .annotate(count=Count('id'))
                    .values_list('fix_type', 'count')
                ),
                'average_confidence': FixSuggestion.objects.aggregate(
                    avg=Avg('confidence')
                )['avg'] or 0,
                'auto_applicable_count': FixSuggestion.objects.filter(
                    auto_applicable=True
                ).count(),
                'high_confidence_count': FixSuggestion.objects.filter(
                    confidence__gte=0.8
                ).count()
            }

            return stats

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, ValueError, asyncio.CancelledError) as e:
            logger.error(f"Stats calculation failed: {e}")
            return {}


# Singleton instance
fix_suggester = FixSuggestionEngine()