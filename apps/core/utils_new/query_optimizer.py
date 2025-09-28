"""
N+1 Query Detection and Optimization Utilities

This module provides tools to:
1. Detect N+1 queries in Django ORM usage
2. Suggest optimizations
3. Provide prefetch strategies
4. Monitor query patterns

Usage:
    from apps.core.utils_new.query_optimizer import QueryOptimizer, detect_n_plus_one
    
    # Decorator to detect N+1 queries
    @detect_n_plus_one
    def my_view(request):
        # Your view code
        
    # Manual optimization suggestions
    optimizer = QueryOptimizer()
    suggestions = optimizer.analyze_queryset(MyModel.objects.all())
"""

import logging
import time
from collections import defaultdict, Counter
from functools import wraps
from django.conf import settings

logger = logging.getLogger('query_optimizer')


__all__ = [
    'QueryPattern',
    'NPlusOneDetector',
    'QueryOptimizer',
    'detect_n_plus_one',
    'QueryAnalyzer',
    'suggest_optimizations',
]


class QueryPattern:
    """Represents a database query pattern for analysis"""
    
    def __init__(self, sql: str, duration: float, stack_trace: List[str]):
        self.sql = sql
        self.duration = duration
        self.stack_trace = stack_trace
        self.table = self._extract_table()
        self.query_type = self._classify_query()
    
    def _extract_table(self) -> str:
        """Extract the main table name from SQL"""
        sql_lower = self.sql.lower().strip()
        if sql_lower.startswith('select'):
            parts = sql_lower.split()
            from_idx = -1
            for i, part in enumerate(parts):
                if part == 'from':
                    from_idx = i
                    break
            if from_idx != -1 and from_idx + 1 < len(parts):
                return parts[from_idx + 1].strip('"').strip("'")
        return 'unknown'
    
    def _classify_query(self) -> str:
        """Classify the type of query"""
        sql_lower = self.sql.lower().strip()
        if sql_lower.startswith('select'):
            if 'join' in sql_lower:
                return 'join'
            elif 'where' in sql_lower:
                return 'filtered'
            return 'select'
        elif sql_lower.startswith('insert'):
            return 'insert'
        elif sql_lower.startswith('update'):
            return 'update'
        elif sql_lower.startswith('delete'):
            return 'delete'
        return 'other'


class NPlusOneDetector:
    """Detects N+1 query patterns in Django ORM usage"""
    
    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self.query_patterns: List[QueryPattern] = []
        self.similar_queries: Dict[str, List[QueryPattern]] = defaultdict(list)
    
    def start_monitoring(self):
        """Start monitoring database queries"""
        reset_queries()
        self.start_time = time.time()
        self.start_query_count = len(connection.queries)
    
    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and analyze queries"""
        end_time = time.time()
        duration = end_time - self.start_time
        queries = connection.queries[self.start_query_count:]
        
        # Analyze queries for patterns
        self.query_patterns = []
        for query in queries:
            pattern = QueryPattern(
                sql=query['sql'],
                duration=float(query['time']),
                stack_trace=[]  # Could be enhanced to capture stack trace
            )
            self.query_patterns.append(pattern)
        
        return self._analyze_patterns(duration)
    
    def _analyze_patterns(self, total_duration: float) -> Dict[str, Any]:
        """Analyze query patterns for N+1 issues"""
        # Group similar queries
        self.similar_queries = defaultdict(list)
        query_signatures = defaultdict(list)
        
        for pattern in self.query_patterns:
            # Create a signature by removing specific values
            signature = self._create_query_signature(pattern.sql)
            query_signatures[signature].append(pattern)
        
        # Identify potential N+1 patterns
        n_plus_one_issues = []
        for signature, patterns in query_signatures.items():
            if len(patterns) >= self.threshold:
                n_plus_one_issues.append({
                    'signature': signature,
                    'count': len(patterns),
                    'total_duration': sum(p.duration for p in patterns),
                    'avg_duration': sum(p.duration for p in patterns) / len(patterns),
                    'table': patterns[0].table,
                    'query_type': patterns[0].query_type,
                    'example_sql': patterns[0].sql,
                    'suggestion': self._suggest_optimization(signature, patterns)
                })
        
        return {
            'total_queries': len(self.query_patterns),
            'total_duration': total_duration,
            'n_plus_one_issues': sorted(n_plus_one_issues, key=lambda x: x['total_duration'], reverse=True),
            'query_breakdown': self._get_query_breakdown(),
            'slow_queries': [p for p in self.query_patterns if p.duration > 0.1],  # Queries > 100ms
        }
    
    def _create_query_signature(self, sql: str) -> str:
        """Create a normalized signature for SQL queries"""
        import re
        
        # Remove specific values and normalize
        signature = sql
        
        # Replace numbers and quoted strings
        signature = re.sub(r'\b\d+\b', 'N', signature)
        signature = re.sub(r"'[^']*'", "'VALUE'", signature)
        signature = re.sub(r'"[^"]*"', '"VALUE"', signature)
        
        # Normalize whitespace
        signature = re.sub(r'\s+', ' ', signature).strip()
        
        return signature
    
    def _suggest_optimization(self, signature: str, patterns: List[QueryPattern]) -> str:
        """Suggest optimization based on query pattern"""
        table = patterns[0].table
        count = len(patterns)
        
        if 'SELECT' in signature.upper() and 'WHERE' in signature.upper():
            if count > 10:
                return f"Consider using select_related() or prefetch_related() for {table} queries. " \
                       f"Found {count} similar queries that could be combined."
            else:
                return f"Consider optimizing {table} queries with better indexing or query restructuring."
        elif 'JOIN' in signature.upper():
            return f"Review join strategy for {table}. Consider using select_related() for forward relationships."
        else:
            return f"Consider caching or batch processing for {table} queries."
    
    def _get_query_breakdown(self) -> Dict[str, int]:
        """Get breakdown of query types"""
        breakdown = Counter()
        for pattern in self.query_patterns:
            breakdown[pattern.query_type] += 1
        return dict(breakdown)


class QueryOptimizer:
    """Provides optimization suggestions for Django ORM queries"""
    
    def __init__(self):
        self.detector = NPlusOneDetector()
    
    def analyze_queryset(self, queryset: QuerySet) -> Dict[str, Any]:
        """Analyze a queryset for optimization opportunities"""
        model = queryset.model
        suggestions = {
            'model': model.__name__,
            'current_query': str(queryset.query),
            'optimizations': [],
            'prefetch_suggestions': [],
            'index_suggestions': []
        }
        
        # Analyze relationships
        relationships = self._get_model_relationships(model)
        
        # Suggest select_related for forward relationships
        forward_relations = [rel for rel in relationships if rel['type'] in ['ForeignKey', 'OneToOneField']]
        if forward_relations:
            suggestions['optimizations'].append({
                'type': 'select_related',
                'description': 'Use select_related() for forward relationships to reduce queries',
                'fields': [rel['field'] for rel in forward_relations],
                'example': f".select_related({', '.join(repr(rel['field']) for rel in forward_relations[:3])})"
            })
        
        # Suggest prefetch_related for reverse/m2m relationships
        reverse_relations = [rel for rel in relationships if rel['type'] in ['ManyToManyField', 'reverse']]
        if reverse_relations:
            prefetch_fields = []
            for rel in reverse_relations:
                prefetch_fields.append(rel['field'])
                suggestions['prefetch_suggestions'].append({
                    'field': rel['field'],
                    'type': rel['type'],
                    'description': f"Prefetch {rel['field']} to avoid N+1 queries"
                })
            
            if prefetch_fields:
                suggestions['optimizations'].append({
                    'type': 'prefetch_related',
                    'description': 'Use prefetch_related() for reverse and many-to-many relationships',
                    'fields': prefetch_fields,
                    'example': f".prefetch_related({', '.join(repr(field) for field in prefetch_fields[:3])})"
                })
        
        # Suggest field selection optimizations
        all_fields = [f.name for f in model._meta.get_fields() if hasattr(f, 'name')]
        text_fields = [f.name for f in model._meta.get_fields() 
                      if hasattr(f, 'name') and getattr(f, 'max_length', 0) > 500]
        
        if text_fields:
            suggestions['optimizations'].append({
                'type': 'defer_large_fields',
                'description': 'Defer large text fields unless needed',
                'fields': text_fields,
                'example': f".defer({', '.join(repr(field) for field in text_fields)})"
            })
        
        # Suggest using only() for specific field access
        essential_fields = ['id', 'name', 'title', 'created_at', 'updated_at']
        available_essential = [f for f in essential_fields if f in all_fields]
        
        suggestions['optimizations'].append({
            'type': 'only_specific_fields',
            'description': 'Use only() when accessing specific fields',
            'fields': available_essential,
            'example': f".only({', '.join(repr(field) for field in available_essential)})"
        })
        
        return suggestions
    
    def _get_model_relationships(self, model) -> List[Dict[str, Any]]:
        """Get all relationships for a model"""
        relationships = []
        
        # Forward relationships (ForeignKey, OneToOneField)
        for field in model._meta.get_fields():
            if isinstance(field, (ForeignKey, OneToOneField)):
                relationships.append({
                    'field': field.name,
                    'type': field.__class__.__name__,
                    'related_model': field.related_model.__name__,
                    'direction': 'forward'
                })
            elif isinstance(field, ManyToManyField):
                relationships.append({
                    'field': field.name,
                    'type': 'ManyToManyField',
                    'related_model': field.related_model.__name__,
                    'direction': 'forward'
                })
        
        # Reverse relationships
        for field in model._meta.get_fields():
            if isinstance(field, ForeignObjectRel):
                relationships.append({
                    'field': field.get_accessor_name(),
                    'type': 'reverse',
                    'related_model': field.related_model.__name__,
                    'direction': 'reverse'
                })
        
        return relationships
    
    def generate_prefetch_objects(self, model, depth: int = 2) -> List[str]:
        """Generate optimized Prefetch objects for a model"""
        relationships = self._get_model_relationships(model)
        prefetch_suggestions = []
        
        for rel in relationships:
            if rel['direction'] == 'reverse' or rel['type'] == 'ManyToManyField':
                # Basic prefetch
                prefetch_suggestions.append(f"'{rel['field']}'")
                
                # Nested prefetch with optimization
                if depth > 1:
                    try:
                        related_model = model._meta.get_field(rel['field']).related_model
                        related_relationships = self._get_model_relationships(related_model)
                        
                        # Find important fields to select_related in the prefetch
                        select_related_fields = [r['field'] for r in related_relationships 
                                               if r['direction'] == 'forward'][:2]  # Limit to prevent deep nesting
                        
                        if select_related_fields:
                            prefetch_obj = f"Prefetch('{rel['field']}', queryset={related_model.__name__}.objects.select_related({', '.join(repr(f) for f in select_related_fields)}))"
                            prefetch_suggestions.append(prefetch_obj)
                    except:
                        pass  # Skip if we can't analyze the related model
        
        return prefetch_suggestions


# Decorator for detecting N+1 queries
def detect_n_plus_one(threshold: int = 5):
    """
    Decorator to detect N+1 queries in a function/view
    
    Usage:
        @detect_n_plus_one(threshold=10)
        def my_view(request):
            # Your code here
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not settings.DEBUG:
                # Only run in debug mode
                return func(*args, **kwargs)
            
            detector = NPlusOneDetector(threshold=threshold)
            detector.start_monitoring()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                analysis = detector.stop_monitoring()
                
                # Log results
                if analysis['n_plus_one_issues']:
                    logger.warning(f"N+1 Query Issues detected in {func.__name__}:")
                    for issue in analysis['n_plus_one_issues']:
                        logger.warning(f"  - {issue['count']} similar queries on {issue['table']} "
                                     f"({issue['total_duration']:.3f}s total)")
                        logger.warning(f"    Suggestion: {issue['suggestion']}")
                
                if analysis['slow_queries']:
                    logger.warning(f"Slow queries detected in {func.__name__}:")
                    for query in analysis['slow_queries'][:5]:  # Top 5 slow queries
                        logger.warning(f"  - {query.duration:.3f}s: {query.sql[:100]}...")
        
        return wrapper
    return decorator


# Context manager for query analysis
class QueryAnalyzer:
    """Context manager for analyzing queries in a code block"""
    
    def __init__(self, threshold: int = 5, log_results: bool = True):
        self.detector = NPlusOneDetector(threshold=threshold)
        self.log_results = log_results
        self.analysis = None
    
    def __enter__(self):
        self.detector.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.analysis = self.detector.stop_monitoring()
        
        if self.log_results and self.analysis['n_plus_one_issues']:
            logger.info(f"Query Analysis Results:")
            logger.info(f"  Total queries: {self.analysis['total_queries']}")
            logger.info(f"  Total duration: {self.analysis['total_duration']:.3f}s")
            
            for issue in self.analysis['n_plus_one_issues']:
                logger.warning(f"  N+1 Issue: {issue['count']} queries on {issue['table']} "
                             f"({issue['total_duration']:.3f}s)")


# Utility function for quick optimization suggestions
def suggest_optimizations(model_or_queryset) -> Dict[str, Any]:
    """
    Quick function to get optimization suggestions for a model or queryset
    
    Usage:
        suggestions = suggest_optimizations(MyModel)
        # or
        suggestions = suggest_optimizations(MyModel.objects.all())
    """
    optimizer = QueryOptimizer()
    
    if isinstance(model_or_queryset, QuerySet):
        return optimizer.analyze_queryset(model_or_queryset)
    else:
        # Assume it's a model class
        queryset = model_or_queryset.objects.all()
        return optimizer.analyze_queryset(queryset)


# Example usage and testing
if __name__ == "__main__":
    # Example of how to use the query optimizer
    print("Query Optimization Tools loaded successfully")
    print("Use the following decorators and utilities:")
    print("  @detect_n_plus_one")
    print("  QueryAnalyzer() context manager")
    print("  suggest_optimizations(Model)")