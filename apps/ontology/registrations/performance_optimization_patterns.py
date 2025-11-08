"""
Ontology registrations for Performance Optimization Patterns.

This module registers all N+1 query optimization patterns, performance testing
utilities, and best practices discovered during the November 2025 optimization work.

Domain: Performance Optimization
Components: 25+ patterns, utilities, and examples
"""

from apps.ontology.registry import OntologyRegistry

import logging
logger = logging.getLogger(__name__)



def register_performance_optimization_patterns():
    """Register performance optimization knowledge with the ontology registry."""
    
    patterns = [
        # ===================================================================
        # CORE CONCEPTS - N+1 Query Problem
        # ===================================================================
        
        {
            "qualified_name": "concepts.n_plus_one_query_problem",
            "type": "concept",
            "domain": "performance.database",
            "purpose": (
                "The N+1 query problem occurs when code executes 1 query to fetch N items, "
                "then N additional queries to fetch related data for each item. This results "
                "in N+1 total queries instead of 2 queries using proper JOINs."
            ),
            "tags": ["performance", "database", "anti-pattern", "n+1"],
            "criticality": "high",
            "examples": [
                {
                    "title": "N+1 Problem Example",
                    "code": """# ❌ BAD: N+1 query problem
users = People.objects.all()  # 1 query
for user in users:
    logger.debug(user.profile.gender)  # N queries (1 per user)
# Total: 1 + N queries

# ✅ GOOD: Optimized with select_related
users = People.objects.select_related('profile').all()  # 1 query with JOIN
for user in users:
    logger.debug(user.profile.gender)
# Total: 1 query""",
                    "impact": "For 100 users: 101 queries → 1 query (99% reduction)"
                }
            ],
            "related_concepts": [
                "concepts.select_related",
                "concepts.prefetch_related",
                "apps.core.utils_new.query_optimizer.NPlusOneDetector"
            ],
            "documentation": [
                "docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md",
                "docs/troubleshooting/COMMON_ISSUES.md#Performance"
            ],
        },
        
        # ===================================================================
        # OPTIMIZATION TECHNIQUES
        # ===================================================================
        
        {
            "qualified_name": "concepts.select_related",
            "type": "concept",
            "domain": "performance.database",
            "purpose": (
                "Django ORM method that performs SQL JOIN to fetch related objects in a single "
                "query. Use for ForeignKey and OneToOne relationships (forward direction)."
            ),
            "tags": ["performance", "database", "optimization", "orm"],
            "criticality": "high",
            "examples": [
                {
                    "title": "Basic select_related Usage",
                    "code": """# Single relationship
users = People.objects.select_related('profile')

# Multiple relationships
users = People.objects.select_related('profile', 'organizational')

# Nested relationships
jobs = Job.objects.select_related('asset__type', 'asset__location')

# In custom manager
class PeopleManager(models.Manager):
    def with_full_details(self):
        return self.select_related('profile', 'organizational', 'shift')""",
                },
                {
                    "title": "When to Use select_related",
                    "description": (
                        "✅ Use for: ForeignKey, OneToOneField (forward)\n"
                        "❌ Don't use for: ManyToMany, Reverse ForeignKey (use prefetch_related)"
                    )
                }
            ],
            "related_concepts": [
                "concepts.prefetch_related",
                "concepts.query_optimization",
                "apps.core.services.query_optimization_service.QueryOptimizer"
            ],
            "documentation": [
                "https://docs.djangoproject.com/en/5.0/ref/models/querysets/#select-related",
                "docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md"
            ],
        },
        
        {
            "qualified_name": "concepts.prefetch_related",
            "type": "concept",
            "domain": "performance.database",
            "purpose": (
                "Django ORM method that performs separate query for related objects, then "
                "joins them in Python. Use for ManyToMany and reverse ForeignKey relationships."
            ),
            "tags": ["performance", "database", "optimization", "orm"],
            "criticality": "high",
            "examples": [
                {
                    "title": "Basic prefetch_related Usage",
                    "code": """# ManyToMany relationship
tasks = Task.objects.prefetch_related('assigned_people')

# Reverse ForeignKey
users = People.objects.prefetch_related('attendance_records')

# Multiple relationships
incidents = NOCIncident.objects.prefetch_related('alerts', 'notifications')""",
                },
                {
                    "title": "Advanced: Custom Prefetch Object",
                    "code": """from django.db.models import Prefetch

# Prefetch with custom queryset
tasks = Task.objects.prefetch_related(
    Prefetch(
        'assigned_people',
        queryset=People.objects.select_related('profile', 'shift'),
        to_attr='optimized_people'
    )
)

# Access via to_attr
for task in tasks:
    people = task.optimized_people  # Already optimized""",
                }
            ],
            "related_concepts": [
                "concepts.select_related",
                "concepts.prefetch_object",
                "apps.core.services.query_optimization_service.QueryOptimizer.create_optimized_prefetch"
            ],
            "documentation": [
                "https://docs.djangoproject.com/en/5.0/ref/models/querysets/#prefetch-related",
                "docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md"
            ],
        },
        
        {
            "qualified_name": "concepts.prefetch_object",
            "type": "concept",
            "domain": "performance.database",
            "purpose": (
                "Django's Prefetch object allows custom querysets for prefetch_related, "
                "enabling nested optimizations and filtering of prefetched data."
            ),
            "tags": ["performance", "database", "optimization", "orm", "advanced"],
            "criticality": "medium",
            "examples": [
                {
                    "title": "Nested Optimization with Prefetch",
                    "code": """from django.db.models import Prefetch

# Optimize nested relationships
incidents = NOCIncident.objects.prefetch_related(
    Prefetch(
        'alerts',
        queryset=NOCAlert.objects.select_related('device', 'severity')
            .order_by('-created_at')[:10],
        to_attr='recent_alerts'
    )
)

# Efficient access - no N+1
for incident in incidents:
    for alert in incident.recent_alerts:  # Already prefetched with device/severity
        logger.debug(f"{alert.device.name}: {alert.severity.level}")
                },
                {
                    "title": "Filter Prefetched Data",
                    "code": """# Prefetch only active items
users = People.objects.prefetch_related(
    Prefetch(
        'attendance_records',
        queryset=Attendance.objects.filter(is_active=True)
            .select_related('site', 'shift'),
        to_attr='active_attendance'
    )
)""",
                }
            ],
            "related_concepts": [
                "concepts.prefetch_related",
                "apps.core.services.query_optimization_service.QueryOptimizer.create_optimized_prefetch"
            ],
            "documentation": [
                "https://docs.djangoproject.com/en/5.0/ref/models/querysets/#prefetch-objects"
            ],
        },
        
        {
            "qualified_name": "concepts.custom_manager_methods",
            "type": "concept",
            "domain": "performance.database",
            "purpose": (
                "Custom queryset methods that encapsulate optimization patterns, "
                "making them reusable and discoverable across the codebase."
            ),
            "tags": ["performance", "database", "orm", "pattern", "reusability"],
            "criticality": "medium",
            "examples": [
                {
                    "title": "with_full_details() Pattern",
                    "code": """class PeopleManager(models.Manager):
    def with_full_details(self):
        '''Fetch user with all related data optimized.'''
        return self.select_related(
            'profile',
            'organizational',
            'shift'
        ).prefetch_related(
            'attendance_records'
        )

# Usage
users = People.objects.with_full_details()  # Fully optimized""",
                },
                {
                    "title": "Domain-Specific Optimization",
                    "code": """class JobManager(models.Manager):
    def with_full_details(self):
        '''Optimize job queries with asset and location data.'''
        return self.select_related(
            'asset__type',
            'asset__category',
            'asset__location',
            'qset__client',
            'location__client'
        )

# Usage in service layer
jobs = Job.objects.with_full_details().filter(status='active')""",
                }
            ],
            "related_concepts": [
                "apps.core.managers.optimized_managers.OptimizedManager",
                "apps.peoples.managers.PeopleManager.with_full_details",
                "apps.activity.models.job_model.JobManager.with_full_details"
            ],
            "implementations": [
                "apps/peoples/managers.py:82",
                "apps/activity/models/job_model.py (JobManager)",
                "apps/noc/models/incident.py:21",
                "apps/core/managers/optimized_managers.py:192"
            ],
            "documentation": [
                "docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md#Pattern-1-Manager-with-Optimization"
            ],
        },
        
        # ===================================================================
        # DETECTION & MONITORING TOOLS
        # ===================================================================
        
        {
            "qualified_name": "apps.core.utils_new.query_optimizer.NPlusOneDetector",
            "type": "class",
            "domain": "performance.monitoring",
            "purpose": (
                "Runtime N+1 query detector that monitors query patterns during execution "
                "and alerts when repeated similar queries exceed a threshold."
            ),
            "tags": ["performance", "monitoring", "n+1", "detection", "debugging"],
            "criticality": "high",
            "inputs": [
                {"name": "threshold", "type": "int", "description": "Max similar queries before alert (default: 5)"},
                {"name": "log_queries", "type": "bool", "description": "Whether to log detected queries"}
            ],
            "outputs": [
                {"name": "report", "type": "dict", "description": "Detection report with query patterns"}
            ],
            "examples": [
                {
                    "title": "As Context Manager",
                    "code": """from apps.core.utils_new.query_optimizer import NPlusOneDetector

with NPlusOneDetector(threshold=5) as detector:
    users = People.objects.all()
    for user in users:
        logger.debug(user.profile.gender)
    
    report = detector.get_report()
    if detector.has_issues():
        logger.debug(f"N+1 detected: {report['similar_queries']}")
                },
                {
                    "title": "As Decorator",
                    "code": """from apps.core.utils_new.query_optimizer import detect_n_plus_one

@detect_n_plus_one
def my_view(request):
    '''Automatically monitor for N+1 in development.'''
    users = People.objects.all()
    for user in users:
        # N+1 would be logged
        process_user(user)
    return render(request, 'template.html')""",
                }
            ],
            "related_concepts": [
                "concepts.n_plus_one_query_problem",
                "apps.core.services.query_optimization_service.QueryOptimizer"
            ],
            "implementation": "apps/core/utils_new/query_optimizer.py:33-150",
            "documentation": [
                "docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md#1-Runtime-Detection--Monitoring"
            ],
        },
        
        {
            "qualified_name": "apps.core.services.query_optimization_service.QueryOptimizer",
            "type": "class",
            "domain": "performance.optimization",
            "purpose": (
                "Service-layer query optimizer that automatically analyzes Django models "
                "and applies select_related/prefetch_related based on optimization profiles."
            ),
            "tags": ["performance", "optimization", "service", "automation"],
            "criticality": "high",
            "inputs": [
                {"name": "queryset", "type": "QuerySet", "description": "Django queryset to optimize"},
                {"name": "profile", "type": "str", "description": "Optimization profile: minimal/default/aggressive"}
            ],
            "outputs": [
                {"name": "queryset", "type": "QuerySet", "description": "Optimized queryset with select_related/prefetch_related"}
            ],
            "examples": [
                {
                    "title": "Automatic Optimization",
                    "code": """from apps.core.services.query_optimization_service import QueryOptimizer

# Default profile (recommended)
jobs = Job.objects.filter(status='active')
optimized = QueryOptimizer.optimize_queryset(jobs, profile='default')

# Aggressive profile for admin/reports
jobs = QueryOptimizer.optimize_queryset(jobs, profile='aggressive')

# Minimal profile for memory-constrained scenarios
jobs = QueryOptimizer.optimize_queryset(jobs, profile='minimal')""",
                },
                {
                    "title": "Domain-Specific Optimization",
                    "code": """# Pre-configured optimization for common models
people_qs = QueryOptimizer.optimize_people_queries()
activity_qs = QueryOptimizer.optimize_activity_queries()

# Custom prefetch patterns
prefetch = QueryOptimizer.create_optimized_prefetch(
    'assigned_people',
    queryset=People.objects.select_related('shift'),
    to_attr='optimized_people'
)""",
                }
            ],
            "optimization_profiles": {
                "minimal": "Only critical non-nullable FKs (memory-constrained)",
                "default": "High-impact relationships (recommended for production)",
                "aggressive": "All relationships (admin interfaces, reports)"
            },
            "related_concepts": [
                "apps.core.managers.optimized_managers.OptimizedManager",
                "apps.core.utils_new.query_optimizer.NPlusOneDetector"
            ],
            "implementation": "apps/core/services/query_optimization_service.py",
            "documentation": [
                "docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md#2-Service-Layer-Optimization"
            ],
        },
        
        # ===================================================================
        # TESTING UTILITIES
        # ===================================================================
        
        {
            "qualified_name": "concepts.assertNumQueries",
            "type": "concept",
            "domain": "performance.testing",
            "purpose": (
                "Django test utility that asserts a specific number of database queries "
                "are executed within a code block. Critical for preventing N+1 regressions."
            ),
            "tags": ["testing", "performance", "assertion", "regression-prevention"],
            "criticality": "high",
            "examples": [
                {
                    "title": "Basic Query Count Test",
                    "code": """from django.test import TestCase

class PerformanceTestCase(TestCase):
    def test_optimized_user_list(self):
        '''Ensure user list is optimized.'''
        with self.assertNumQueries(1):
            users = list(People.objects.select_related('profile'))
            for user in users:
                _ = user.profile.gender  # Should not trigger query""",
                },
                {
                    "title": "Complex Optimization Test",
                    "code": """def test_incident_detail_queries(self):
    '''NOC incident detail should use <= 4 queries.'''
    incident = NOCIncident.objects.with_full_details().first()
    
    # Verify optimization
    with self.assertNumQueries(4):  # 1 main + 3 prefetch
        incident = NOCIncident.objects.with_full_details().get(pk=incident.pk)
        
        # Access related data - should be cached
        _ = incident.alerts.all()
        _ = incident.notifications.all()
        _ = incident.site.name""",
                }
            ],
            "related_concepts": [
                "concepts.performance_benchmarking",
                "apps.core.utils_new.query_optimizer.NPlusOneDetector"
            ],
            "implementations": [
                "apps/noc/tests/test_performance/test_n1_optimizations.py",
                "apps/peoples/tests/test_user_model.py:213"
            ],
            "documentation": [
                "https://docs.djangoproject.com/en/5.0/topics/testing/tools/#django.test.TransactionTestCase.assertNumQueries"
            ],
        },
        
        {
            "qualified_name": "concepts.performance_benchmarking",
            "type": "concept",
            "domain": "performance.testing",
            "purpose": (
                "Practice of measuring and comparing query performance before/after "
                "optimizations to ensure improvements are effective."
            ),
            "tags": ["testing", "performance", "benchmarking", "metrics"],
            "criticality": "medium",
            "examples": [
                {
                    "title": "Benchmark N+1 Fix",
                    "code": """import time
from django.test import TestCase

class BenchmarkTestCase(TestCase):
    def test_user_query_performance(self):
        '''Compare unoptimized vs optimized query performance.'''
        
        # Unoptimized baseline
        start = time.time()
        users = People.objects.all()
        for user in users:
            _ = user.profile.gender  # N+1 queries
        unoptimized_time = time.time() - start
        
        # Optimized version
        start = time.time()
        users = People.objects.select_related('profile').all()
        for user in users:
            _ = user.profile.gender  # No extra queries
        optimized_time = time.time() - start
        
        # Verify improvement
        improvement = (unoptimized_time - optimized_time) / unoptimized_time
        self.assertGreater(improvement, 0.5, "Should be at least 50% faster")""",
                }
            ],
            "related_concepts": [
                "concepts.assertNumQueries",
                "apps.core.utils_new.query_optimizer.QueryAnalyzer"
            ],
        },
        
        {
            "qualified_name": "concepts.query_count_testing",
            "type": "concept",
            "domain": "performance.testing",
            "purpose": (
                "Testing practice that verifies specific query count thresholds to prevent "
                "performance regressions and ensure optimizations remain effective."
            ),
            "tags": ["testing", "performance", "regression-prevention", "ci-cd"],
            "criticality": "high",
            "examples": [
                {
                    "title": "Test Suite with Query Assertions",
                    "code": """class NOCPerformanceTestCase(TestCase):
    '''N+1 optimization verification for NOC module.'''
    
    def test_incident_list_query_count(self):
        '''List view should use minimal queries.'''
        with self.assertNumQueries(3):  # 1 main + 2 prefetch
            incidents = list(NOCIncident.objects.with_full_details()[:20])
    
    def test_incident_detail_access(self):
        '''Detail view should not trigger N+1.'''
        incident = NOCIncident.objects.with_full_details().first()
        
        with self.assertNumQueries(0):  # All data already fetched
            _ = incident.site.name
            _ = list(incident.alerts.all())
            _ = list(incident.notifications.all())""",
                }
            ],
            "implementations": [
                "apps/noc/tests/test_performance/test_n1_optimizations.py:277",
                "apps/peoples/tests/test_user_integration.py:358"
            ],
            "documentation": [
                "docs/testing/TESTING_AND_QUALITY_GUIDE.md"
            ],
        },
        
        # ===================================================================
        # IMPLEMENTATION EXAMPLES
        # ===================================================================
        
        {
            "qualified_name": "examples.noc_incident_optimization",
            "type": "example",
            "domain": "performance.implementation",
            "purpose": "Real-world N+1 optimization in NOC incident queries",
            "tags": ["example", "noc", "optimization", "case-study"],
            "before_code": """# ❌ BEFORE: N+1 problem
incidents = NOCIncident.objects.filter(status='active')
for incident in incidents:  # 1 query
    logger.debug(incident.site.name)
    for alert in incident.alerts.all():  # N queries
        logger.debug(alert.device.name)
            "after_code": """# ✅ AFTER: Optimized with custom manager
class NOCIncidentManager(models.Manager):
    def with_full_details(self):
        return self.select_related(
            'site',
            'severity',
            'assigned_to'
        ).prefetch_related(
            Prefetch(
                'alerts',
                queryset=NOCAlert.objects.select_related('device', 'severity')
            )
        )

# Usage
incidents = NOCIncident.objects.with_full_details().filter(status='active')
for incident in incidents:  # 1 query
    logger.debug(incident.site.name)
    for alert in incident.alerts.all():  # No query - prefetched
        logger.debug(alert.device.name)
            "impact": "101 queries → 3 queries (97% reduction)",
            "implementation": "apps/noc/models/incident.py:21",
            "test_coverage": "apps/noc/tests/test_performance/test_n1_optimizations.py:277",
        },
        
        {
            "qualified_name": "examples.people_manager_optimization",
            "type": "example",
            "domain": "performance.implementation",
            "purpose": "Optimized user queries with profile and organizational data",
            "tags": ["example", "peoples", "optimization", "case-study"],
            "before_code": """# ❌ BEFORE: Multiple queries per user
users = People.objects.filter(enable=True)
for user in users:  # 1 query
    logger.debug(user.profile.gender)
    logger.debug(user.organizational.designation)
    logger.debug(user.shift.name if user.shift else 'None')
            "after_code": """# ✅ AFTER: Single query with joins
class PeopleManager(models.Manager):
    def with_full_details(self):
        return self.select_related('profile', 'organizational', 'shift')

# Usage
users = People.objects.with_full_details().filter(enable=True)
for user in users:  # 1 query with JOINs
    logger.debug(user.profile.gender)
    logger.debug(user.organizational.designation)
    logger.debug(user.shift.name if user.shift else 'None')
            "impact": "301 queries → 1 query (99.7% reduction)",
            "implementation": "apps/peoples/managers.py:82",
            "test_coverage": "apps/peoples/tests/test_user_model.py:213",
            "documentation": "apps/peoples/models/user_model.py:88 (docstring)",
        },
        
        {
            "qualified_name": "examples.reports_service_optimization",
            "type": "example",
            "domain": "performance.implementation",
            "purpose": "Optimized report generation with prefetch_related",
            "tags": ["example", "reports", "optimization", "case-study"],
            "before_code": """# ❌ BEFORE: N+1 in report generation
def generate_site_report(site_id):
    site = Site.objects.get(id=site_id)  # 1 query
    users = site.people_set.all()  # 1 query
    
    for user in users:  # N iterations
        attendance = user.attendance_records.filter(date=today)  # N queries
        tasks = user.assigned_tasks.all()  # N queries
        # Total: 1 + 1 + 2N queries""",
            "after_code": """# ✅ AFTER: Prefetch all related data
def generate_site_report(site_id):
    site = Site.objects.prefetch_related(
        Prefetch(
            'people_set',
            queryset=People.objects.prefetch_related(
                Prefetch('attendance_records', 
                         queryset=Attendance.objects.filter(date=today)),
                'assigned_tasks'
            )
        )
    ).get(id=site_id)  # 1 query + 3 prefetch queries
    
    users = site.people_set.all()
    for user in users:
        attendance = user.attendance_records.all()  # No query - cached
        tasks = user.assigned_tasks.all()  # No query - cached
    # Total: 4 queries""",
            "impact": "For 50 users: 102 queries → 4 queries (96% reduction)",
            "implementation": "apps/reports/services/ (various report services)",
        },
        
        # ===================================================================
        # ANTI-PATTERNS TO AVOID
        # ===================================================================
        
        {
            "qualified_name": "anti_patterns.over_prefetching",
            "type": "anti-pattern",
            "domain": "performance.pitfalls",
            "purpose": "Avoid fetching too much data unnecessarily",
            "tags": ["anti-pattern", "performance", "memory", "optimization"],
            "description": (
                "Using aggressive optimization profile when only accessing a few fields "
                "wastes memory and can slow down queries with too many JOINs."
            ),
            "bad_example": """# ❌ BAD: Fetching everything when only need name
users = People.objects.select_related(
    'profile', 'organizational', 'shift', 'site', 
    'attendance_records', 'manager', 'department'
)
for user in users:
    logger.debug(user.username)
            "good_example": """# ✅ GOOD: Only fetch what you need
users = People.objects.only('username', 'id')
for user in users:
    logger.debug(user.username)
            "solution": "Use 'minimal' profile or only() for limited field access",
        },
        
        {
            "qualified_name": "anti_patterns.missing_to_attr",
            "type": "anti-pattern",
            "domain": "performance.pitfalls",
            "purpose": "Always use to_attr with nested Prefetch to avoid query duplication",
            "tags": ["anti-pattern", "performance", "prefetch", "orm"],
            "description": (
                "Nested prefetch_related without to_attr can cause duplicate queries "
                "when the same relationship is accessed multiple times."
            ),
            "bad_example": """# ❌ BAD: Missing to_attr
incidents = NOCIncident.objects.prefetch_related(
    Prefetch('alerts', queryset=NOCAlert.objects.select_related('device'))
)
# May re-query if alerts accessed differently""",
            "good_example": """# ✅ GOOD: Use to_attr for caching
incidents = NOCIncident.objects.prefetch_related(
    Prefetch(
        'alerts',
        queryset=NOCAlert.objects.select_related('device'),
        to_attr='cached_alerts'  # Stored as list
    )
)
# Access via cached_alerts - guaranteed no re-query""",
            "documentation": [
                "https://docs.djangoproject.com/en/5.0/ref/models/querysets/#prefetch-objects"
            ],
        },
        
        {
            "qualified_name": "anti_patterns.queryset_in_loop",
            "type": "anti-pattern",
            "domain": "performance.pitfalls",
            "purpose": "Never execute queries inside loops - batch them",
            "tags": ["anti-pattern", "performance", "n+1", "loops"],
            "description": "Classic N+1 pattern - executing database queries inside a loop",
            "bad_example": """# ❌ BAD: Query in loop
user_ids = [1, 2, 3, 4, 5]
users = []
for user_id in user_ids:
    user = People.objects.get(id=user_id)  # 5 queries
    users.append(user)""",
            "good_example": """# ✅ GOOD: Single batch query
user_ids = [1, 2, 3, 4, 5]
users = People.objects.filter(id__in=user_ids)  # 1 query""",
            "related_concepts": [
                "concepts.n_plus_one_query_problem"
            ],
        },
        
        # ===================================================================
        # CACHING INTEGRATION
        # ===================================================================
        
        {
            "qualified_name": "concepts.query_result_caching",
            "type": "concept",
            "domain": "performance.caching",
            "purpose": (
                "Cache frequently-accessed query results in Redis to avoid repeated "
                "database queries, complementing query optimization."
            ),
            "tags": ["performance", "caching", "redis", "optimization"],
            "criticality": "medium",
            "examples": [
                {
                    "title": "Cache with Query Optimization",
                    "code": """from django.core.cache import cache

def get_active_users_cached():
    '''Get active users with caching + optimization.'''
    cache_key = 'active_users_v1'
    users = cache.get(cache_key)
    
    if not users:
        # Optimized query
        users = list(People.objects.with_full_details()
                     .filter(enable=True))
        cache.set(cache_key, users, timeout=300)  # 5 minutes
    
    return users""",
                }
            ],
            "related_concepts": [
                "apps.core.services.query_optimization_service.QueryOptimizer"
            ],
            "documentation": [
                "docs/features/DOMAIN_SPECIFIC_SYSTEMS.md#Caching-Strategy"
            ],
        },
        
        # ===================================================================
        # DOCUMENTATION & GUIDES
        # ===================================================================
        
        {
            "qualified_name": "documentation.query_optimization_architecture",
            "type": "documentation",
            "domain": "performance.reference",
            "purpose": "Complete architectural guide for query optimization system",
            "tags": ["documentation", "architecture", "reference"],
            "path": "docs/architecture/QUERY_OPTIMIZATION_ARCHITECTURE.md",
            "sections": [
                "Module Breakdown",
                "Decision Tree",
                "Common Patterns",
                "Performance Guidelines",
                "Testing Strategy"
            ],
            "related_concepts": [
                "apps.core.utils_new.query_optimizer.NPlusOneDetector",
                "apps.core.services.query_optimization_service.QueryOptimizer"
            ],
        },
        
        {
            "qualified_name": "documentation.n1_optimization_deliverables",
            "type": "documentation",
            "domain": "performance.reference",
            "purpose": "Complete list of N+1 fixes delivered across all apps",
            "tags": ["documentation", "deliverables", "reference"],
            "files": [
                "N1_OPTIMIZATION_PART2_DELIVERABLES.md",
                "N1_OPTIMIZATION_QUICK_REFERENCE.md",
                "N_PLUS_ONE_FIXES_PART1_COMPLETE.md"
            ],
            "apps_optimized": [
                "noc", "reports", "activity", "peoples", "work_order_management",
                "attendance", "journal", "wellness", "y_helpdesk"
            ],
        },
        
        # ===================================================================
        # MANAGER IMPLEMENTATIONS
        # ===================================================================
        
        {
            "qualified_name": "apps.core.managers.optimized_managers.OptimizedManager",
            "type": "class",
            "domain": "performance.managers",
            "purpose": (
                "Base manager class that provides optimized querysets with automatic "
                "select_related and prefetch_related based on model relationships."
            ),
            "tags": ["performance", "manager", "orm", "base-class"],
            "criticality": "high",
            "methods": [
                {
                    "name": "with_optimizations",
                    "purpose": "Get queryset with default optimizations",
                    "example": "users = People.objects.with_optimizations()"
                },
                {
                    "name": "with_full_details",
                    "purpose": "Get queryset with all relationships optimized",
                    "example": "users = People.objects.with_full_details()"
                }
            ],
            "usage": "Extend this class in your custom managers to get optimization methods",
            "implementation": "apps/core/managers/optimized_managers.py",
            "related_concepts": [
                "apps.core.services.query_optimization_service.QueryOptimizer"
            ],
        },
        
        {
            "qualified_name": "apps.peoples.managers.PeopleManager.with_full_details",
            "type": "method",
            "domain": "performance.managers",
            "purpose": "Optimized queryset for People model with profile and org data",
            "tags": ["performance", "peoples", "optimization", "manager"],
            "implementation": "apps/peoples/managers.py:82",
            "optimizations": [
                "select_related('profile')",
                "select_related('organizational')",
                "select_related('shift')"
            ],
            "test_coverage": [
                "apps/peoples/tests/test_user_model.py:213",
                "apps/peoples/tests/test_user_integration.py:358"
            ],
            "documentation": "apps/peoples/models/user_model.py:88",
        },
        
        {
            "qualified_name": "apps.noc.models.incident.NOCIncidentManager.with_full_details",
            "type": "method",
            "domain": "performance.managers",
            "purpose": "Optimized queryset for NOC incidents with alerts and notifications",
            "tags": ["performance", "noc", "optimization", "manager"],
            "implementation": "apps/noc/models/incident.py:21",
            "optimizations": [
                "select_related('site', 'severity', 'assigned_to')",
                "prefetch_related('alerts', 'notifications')"
            ],
            "test_coverage": "apps/noc/tests/test_performance/test_n1_optimizations.py:277",
        },
    ]
    
    # Bulk register all patterns
    OntologyRegistry.bulk_register(patterns)
    
    return len(patterns)


def get_performance_summary():
    """Get summary of registered performance patterns."""
    concepts = OntologyRegistry.get_by_domain("performance.database")
    testing = OntologyRegistry.get_by_domain("performance.testing")
    monitoring = OntologyRegistry.get_by_domain("performance.monitoring")
    
    return {
        "database_concepts": len(concepts),
        "testing_concepts": len(testing),
        "monitoring_tools": len(monitoring),
        "total_registered": len(concepts) + len(testing) + len(monitoring),
    }
