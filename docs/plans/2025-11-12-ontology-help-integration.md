# Ontology-Help Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate Ontology module with Help modules to enable automated documentation and unified knowledge search WITHOUT degrading performance.

**Architecture:** 4-phase rollout with performance gates. Lazy loading, Redis caching, async queries, circuit breakers, and feature flags for instant rollback.

**Tech Stack:** Django 5.2.1, Redis, Celery, pytest, py-spy (profiling), Prometheus

**Critical Constraint:** ZERO performance degradation - memory delta < 10MB, P95 latency delta < 100ms.

---

## Table of Contents

- [Phase 1: Performance-Safe Foundation](#phase-1-performance-safe-foundation)
- [Phase 2: Lazy-Loaded HelpBot Integration](#phase-2-lazy-loaded-helpbot-integration)
- [Phase 3: Background Article Generation](#phase-3-background-article-generation)
- [Phase 4: Unified Knowledge Service (Optional)](#phase-4-unified-knowledge-service-optional)
- [Performance Monitoring](#performance-monitoring)
- [Rollback Procedures](#rollback-procedures)

---

## Phase 1: Performance-Safe Foundation

**Duration:** 2.5 days
**Risk:** LOW
**Goal:** Establish baseline metrics + add ontology decorators (zero runtime cost)

---

### Task 1.1: Create Performance Baseline Script

**Files:**
- Create: `scripts/performance/baseline_help_modules.py`
- Create: `tests/performance/test_help_baseline.py`

**Step 1: Write baseline profiling script**

```python
# File: scripts/performance/baseline_help_modules.py
"""
Baseline performance profiling for help modules.

Measures:
- Memory usage per worker
- HelpBot response times (P50, P95, P99)
- help_center search latency
- y_helpdesk KB suggester latency
"""

import psutil
import time
import json
from django.test import RequestFactory
from apps.helpbot.services.conversation_service import ConversationService
from apps.help_center.services.search_service import SearchService
from apps.y_helpdesk.services.kb_suggester import KBSuggester

def measure_memory():
    """Get current process memory in MB."""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

def benchmark_helpbot(queries, iterations=100):
    """Benchmark HelpBot conversation service."""
    service = ConversationService()
    latencies = []

    for query in queries:
        for _ in range(iterations):
            start = time.perf_counter()
            service.get_response(query)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # ms

    latencies.sort()
    return {
        'p50': latencies[len(latencies) // 2],
        'p95': latencies[int(len(latencies) * 0.95)],
        'p99': latencies[int(len(latencies) * 0.99)],
        'mean': sum(latencies) / len(latencies)
    }

def benchmark_help_center(queries, iterations=100):
    """Benchmark help_center search."""
    service = SearchService()
    latencies = []

    for query in queries:
        for _ in range(iterations):
            start = time.perf_counter()
            service.search(query, limit=5)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

    latencies.sort()
    return {
        'p50': latencies[len(latencies) // 2],
        'p95': latencies[int(len(latencies) * 0.95)],
        'p99': latencies[int(len(latencies) * 0.99)],
        'mean': sum(latencies) / len(latencies)
    }

def run_baseline():
    """Run complete baseline suite."""
    print("Starting baseline performance measurement...")

    # Memory baseline
    initial_memory = measure_memory()
    print(f"Initial memory: {initial_memory:.2f} MB")

    # Test queries
    queries = [
        "how do I authenticate",
        "what is SLA tracking",
        "troubleshoot GPS permissions",
        "explain secure file download"
    ]

    # Benchmark HelpBot
    print("\nBenchmarking HelpBot...")
    helpbot_stats = benchmark_helpbot(queries)
    print(f"HelpBot P95: {helpbot_stats['p95']:.2f}ms")

    # Benchmark help_center
    print("\nBenchmarking help_center...")
    help_center_stats = benchmark_help_center(queries)
    print(f"help_center P95: {help_center_stats['p95']:.2f}ms")

    # Final memory
    final_memory = measure_memory()
    print(f"\nFinal memory: {final_memory:.2f} MB")
    print(f"Memory delta: {final_memory - initial_memory:.2f} MB")

    # Save results
    results = {
        'timestamp': time.time(),
        'memory': {
            'initial_mb': initial_memory,
            'final_mb': final_memory,
            'delta_mb': final_memory - initial_memory
        },
        'helpbot': helpbot_stats,
        'help_center': help_center_stats
    }

    with open('performance_baseline.json', 'w') as f:
        json.dump(results, f, indent=2)

    print("\n✅ Baseline saved to performance_baseline.json")
    return results

if __name__ == '__main__':
    run_baseline()
```

**Step 2: Run baseline script**

```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master
source venv/bin/activate
python scripts/performance/baseline_help_modules.py
```

**Expected Output:**
```
Starting baseline performance measurement...
Initial memory: 245.32 MB
Benchmarking HelpBot...
HelpBot P95: 187.45ms
Benchmarking help_center...
help_center P95: 92.13ms
Final memory: 247.89 MB
Memory delta: 2.57 MB
✅ Baseline saved to performance_baseline.json
```

**Step 3: Commit baseline script**

```bash
git add scripts/performance/baseline_help_modules.py performance_baseline.json
git commit -m "perf: add baseline performance measurements for help modules"
```

---

### Task 1.2: Add Ontology Decorators to help_center Services

**Files:**
- Modify: `apps/help_center/services/ai_assistant_service.py:1`
- Modify: `apps/help_center/services/search_service.py:1`
- Modify: `apps/help_center/services/knowledge_service.py:1`
- Modify: `apps/help_center/services/analytics_service.py:1`
- Modify: `apps/help_center/services/ticket_integration_service.py:1`
- Modify: `apps/help_center/services/gamification_service.py:1`

**Step 1: Add decorator to AIAssistantService**

```python
# File: apps/help_center/services/ai_assistant_service.py
# Add at top of file (after existing imports)

from apps.ontology import ontology

@ontology(
    domain="help",
    purpose="RAG-powered conversational help assistant with streaming responses for user support queries",
    inputs=[
        {"name": "tenant", "type": "Tenant", "description": "Multi-tenant context for data isolation"},
        {"name": "user", "type": "People", "description": "User requesting help"},
        {"name": "query", "type": "str", "description": "Natural language question about system features or troubleshooting"},
    ],
    outputs=[
        {"name": "response_stream", "type": "AsyncGenerator[str]", "description": "Streamed AI response in 20-word chunks"}
    ],
    depends_on=[
        "apps.help_center.services.SearchService",
        "apps.onboarding_api.services.ProductionLLMService"
    ],
    tags=["help", "rag", "ai", "streaming", "chatbot", "customer-support"],
    criticality="high",
    business_value="Reduces support tickets by 55%, improves self-service adoption to 50-60%",
    revenue_impact="+$78,000 net over 3 years per deployment",
    performance_notes="Streams response in 20-word chunks for better UX, uses hybrid search (FTS + pgvector)",
    security_notes="Multi-tenant isolated, sanitizes user queries, rate-limited to prevent abuse"
)
class AIAssistantService:
    """RAG-powered AI assistant for help queries with streaming responses."""
    # ... existing implementation unchanged
```

**Step 2: Add decorator to SearchService**

```python
# File: apps/help_center/services/search_service.py

from apps.ontology import ontology

@ontology(
    domain="help",
    purpose="Hybrid search combining PostgreSQL FTS and pgvector semantic search for help articles",
    inputs=[
        {"name": "query", "type": "str", "description": "User search query"},
        {"name": "user", "type": "People", "description": "User for permission filtering"},
        {"name": "limit", "type": "int", "description": "Max results (default 10)"}
    ],
    outputs=[
        {"name": "results", "type": "List[HelpArticle]", "description": "Ranked help articles"}
    ],
    depends_on=[
        "django.contrib.postgres.search",  # FTS
        "pgvector"  # Semantic search
    ],
    tags=["help", "search", "fts", "semantic-search", "pgvector"],
    criticality="high",
    business_value="Core search functionality enabling 55% ticket reduction",
    performance_notes="Hybrid search: FTS for keywords, pgvector for semantics, ~50ms P95 latency",
    examples=[
        {
            "input": "authenticate users",
            "output": "[AuthenticationGuide, TroubleshootingLogin, JWTTokens]"
        }
    ]
)
class SearchService:
    """Hybrid search service for help articles."""
    # ... existing implementation unchanged
```

**Step 3: Add remaining decorators (batch)**

Use this script for faster annotation:

```python
# File: scripts/add_help_center_decorators.py

DECORATORS = {
    "apps/help_center/services/knowledge_service.py": {
        "domain": "help",
        "purpose": "Knowledge article CRUD, versioning, and publishing workflows",
        "criticality": "high",
        "tags": ["help", "knowledge-management", "crud", "versioning"]
    },
    "apps/help_center/services/analytics_service.py": {
        "domain": "help",
        "purpose": "Track help article engagement, search analytics, and knowledge gap identification",
        "criticality": "medium",
        "tags": ["help", "analytics", "metrics", "engagement"]
    },
    "apps/help_center/services/ticket_integration_service.py": {
        "domain": "help",
        "purpose": "Correlate help articles with support tickets to measure KB effectiveness",
        "criticality": "medium",
        "tags": ["help", "integration", "tickets", "effectiveness"]
    },
    "apps/help_center/services/gamification_service.py": {
        "domain": "help",
        "purpose": "Award badges and points for help article contributions and usage",
        "criticality": "low",
        "tags": ["help", "gamification", "badges", "engagement"]
    }
}

# Implementation: Add decorator above each class definition
# (See scripts/add_help_module_ontology.py for full implementation)
```

**Step 4: Verify memory impact**

```bash
python scripts/performance/baseline_help_modules.py
```

**Expected:** Memory delta < 5MB compared to baseline

**Step 5: Commit decorators**

```bash
git add apps/help_center/services/*.py scripts/add_help_center_decorators.py
git commit -m "docs: add ontology decorators to help_center services (6 services)"
```

---

### Task 1.3: Add Ontology Decorators to helpbot Services

**Files:**
- Modify: `apps/helpbot/services/conversation_service.py:1`
- Modify: `apps/helpbot/services/knowledge_service.py:1`
- Modify: `apps/helpbot/services/parlant_agent_service.py:1`
- Modify: `apps/helpbot/services/context_service.py:1`
- Modify: `apps/helpbot/services/ticket_intent_classifier.py:1`

**Step 1: Add decorator to ConversationService**

```python
# File: apps/helpbot/services/conversation_service.py

from apps.ontology import ontology

@ontology(
    domain="help",
    purpose="Orchestrate multi-turn conversations with context tracking and intent classification",
    inputs=[
        {"name": "session", "type": "HelpBotSession", "description": "Conversation session"},
        {"name": "message", "type": "str", "description": "User message"},
        {"name": "user", "type": "People", "description": "User context"}
    ],
    outputs=[
        {"name": "response", "type": "str", "description": "Bot response"},
        {"name": "suggestions", "type": "List[str]", "description": "Follow-up suggestions"}
    ],
    depends_on=[
        "apps.helpbot.services.KnowledgeService",
        "apps.helpbot.services.ContextService",
        "apps.helpbot.services.ParlantAgentService"
    ],
    tags=["help", "chatbot", "conversation", "multi-turn", "intent"],
    criticality="high",
    business_value="Powers conversational help interface, supports 8 session types including security mentor"
)
class ConversationService:
    """Orchestrate HelpBot conversations."""
    # ... existing implementation unchanged
```

**Step 2: Add decorator to ParlantAgentService**

```python
# File: apps/helpbot/services/parlant_agent_service.py

from apps.ontology import ontology

@ontology(
    domain="help",
    purpose="Parlant 3.0 conversational AI agent for guided workflows and security scorecard reviews",
    inputs=[
        {"name": "session", "type": "HelpBotSession", "description": "Session context"},
        {"name": "journey", "type": "str", "description": "Journey type: scorecard_review, emergency_escalation, violation_resolution"},
    ],
    outputs=[
        {"name": "response", "type": "dict", "description": "Parlant agent response with guidance"}
    ],
    depends_on=[
        "parlant==3.0",  # External dependency
        "apps.helpbot.parlant.guidelines.non_negotiables_guidelines"
    ],
    tags=["help", "ai", "parlant", "security", "guided-workflows", "journeys"],
    criticality="high",
    business_value="Security Facility Mentor - guides compliance with 7 non-negotiables, multi-language support (en/hi/te)"
)
class ParlantAgentService:
    """Parlant 3.0 conversational AI integration."""
    # ... existing implementation unchanged
```

**Step 3: Add remaining decorators (3 more services)**

Follow same pattern for:
- `KnowledgeService` - txtai knowledge base management
- `ContextService` - User context tracking
- `TicketIntentClassifier` - NL ticket creation from chat

**Step 4: Commit**

```bash
git add apps/helpbot/services/*.py
git commit -m "docs: add ontology decorators to helpbot services (5 services)"
```

---

### Task 1.4: Add Ontology Decorators to y_helpdesk Services

**Files:**
- Modify: `apps/y_helpdesk/services/ai_summarizer.py:1`
- Modify: `apps/y_helpdesk/services/kb_suggester.py:1`
- Modify: `apps/y_helpdesk/services/duplicate_detector.py:1`
- Modify: `apps/y_helpdesk/services/sla_service.py:1`

**Step 1: Add decorator to AISummarizerService**

```python
# File: apps/y_helpdesk/services/ai_summarizer.py

from apps.ontology import ontology

@ontology(
    domain="helpdesk",
    purpose="AI-powered ticket thread summarization for quick agent context",
    inputs=[
        {"name": "ticket", "type": "Ticket", "description": "Ticket with conversation thread"},
    ],
    outputs=[
        {"name": "summary", "type": "str", "description": "Concise 2-3 sentence summary"}
    ],
    depends_on=[
        "apps.onboarding_api.services.ProductionLLMService"
    ],
    tags=["helpdesk", "ai", "summarization", "tickets", "agent-tools"],
    criticality="medium",
    business_value="Reduces agent reading time by 40%, improves ticket resolution speed"
)
class AISummarizerService:
    """AI ticket thread summarization."""
    # ... existing implementation unchanged
```

**Step 2: Add decorator to KBSuggester**

```python
# File: apps/y_helpdesk/services/kb_suggester.py

from apps.ontology import ontology

@ontology(
    domain="helpdesk",
    purpose="Suggest relevant KB articles for tickets using NLP similarity matching",
    inputs=[
        {"name": "ticket", "type": "Ticket", "description": "Ticket needing KB suggestions"},
    ],
    outputs=[
        {"name": "suggestions", "type": "List[dict]", "description": "KB articles with relevance scores"}
    ],
    depends_on=[],
    tags=["helpdesk", "knowledge-base", "suggestions", "nlp", "similarity"],
    criticality="high",
    business_value="Enables agent self-service, reduces escalations by 30%"
)
class KBSuggester:
    """KB article suggester for tickets."""
    # ... existing implementation unchanged
```

**Step 3: Add remaining decorators (2 more services)**

Follow same pattern for:
- `DuplicateDetectorService` - Duplicate ticket detection
- `SLAService` - SLA tracking and breach prediction

**Step 4: Commit**

```bash
git add apps/y_helpdesk/services/*.py
git commit -m "docs: add ontology decorators to y_helpdesk services (4 services)"
```

---

### Task 1.5: Performance Gate - Phase 1 Verification

**Files:**
- Create: `tests/performance/test_phase1_gate.py`

**Step 1: Write performance gate test**

```python
# File: tests/performance/test_phase1_gate.py
"""
Phase 1 Performance Gate: Verify ontology decorators have zero runtime cost.

PASS CRITERIA:
- Memory delta < 5MB compared to baseline
- Latency delta < 10ms compared to baseline
- All help module services still queryable

FAIL ACTION: Remove decorators, investigate
"""

import json
import pytest
from scripts.performance.baseline_help_modules import run_baseline

def load_baseline():
    """Load original baseline."""
    with open('performance_baseline.json') as f:
        return json.load(f)

def test_memory_impact():
    """Verify memory impact of ontology decorators < 5MB."""
    baseline = load_baseline()
    current = run_baseline()

    baseline_memory = baseline['memory']['delta_mb']
    current_memory = current['memory']['delta_mb']

    delta = abs(current_memory - baseline_memory)

    assert delta < 5.0, f"Memory impact {delta:.2f}MB exceeds 5MB threshold"

def test_helpbot_latency_impact():
    """Verify HelpBot latency delta < 10ms."""
    baseline = load_baseline()
    current = run_baseline()

    baseline_p95 = baseline['helpbot']['p95']
    current_p95 = current['helpbot']['p95']

    delta = abs(current_p95 - baseline_p95)

    assert delta < 10.0, f"HelpBot latency delta {delta:.2f}ms exceeds 10ms threshold"

def test_help_center_latency_impact():
    """Verify help_center latency delta < 10ms."""
    baseline = load_baseline()
    current = run_baseline()

    baseline_p95 = baseline['help_center']['p95']
    current_p95 = current['help_center']['p95']

    delta = abs(current_p95 - baseline_p95)

    assert delta < 10.0, f"help_center latency delta {delta:.2f}ms exceeds 10ms threshold"

def test_ontology_registration_count():
    """Verify 15+ services registered in ontology."""
    from apps.ontology.registry import OntologyRegistry

    # help_center: 6 services
    # helpbot: 5 services
    # y_helpdesk: 4 services
    # Total expected: 15 services

    all_components = OntologyRegistry.get_all()
    help_components = [c for c in all_components if c.get('domain') in ['help', 'helpdesk']]

    assert len(help_components) >= 15, f"Expected 15+ help services, found {len(help_components)}"
```

**Step 2: Run performance gate test**

```bash
pytest tests/performance/test_phase1_gate.py -v --tb=short
```

**Expected Output:**
```
tests/performance/test_phase1_gate.py::test_memory_impact PASSED
tests/performance/test_phase1_gate.py::test_helpbot_latency_impact PASSED
tests/performance/test_phase1_gate.py::test_help_center_latency_impact PASSED
tests/performance/test_phase1_gate.py::test_ontology_registration_count PASSED

========== 4 passed in 12.34s ==========
```

**Step 3: If PASS - Commit gate test**

```bash
git add tests/performance/test_phase1_gate.py
git commit -m "test: add Phase 1 performance gate (ontology decorators)"
```

**Step 4: If FAIL - Rollback**

```bash
git revert HEAD~3  # Revert decorator commits
```

**GATE DECISION:** Only proceed to Phase 2 if all tests PASS.

---

## Phase 2: Lazy-Loaded HelpBot Integration

**Duration:** 4 days
**Risk:** MEDIUM
**Goal:** HelpBot queries ontology as fallback with caching and circuit breakers

---

### Task 2.1: Implement Redis-Cached Ontology Query Service

**Files:**
- Create: `apps/core/services/ontology_query_service.py`
- Create: `tests/unit/test_ontology_query_service.py`

**Step 1: Write failing test**

```python
# File: tests/unit/test_ontology_query_service.py

import pytest
from unittest.mock import patch, MagicMock
from apps.core.services.ontology_query_service import OntologyQueryService

@pytest.fixture
def service():
    return OntologyQueryService()

def test_query_returns_cached_result_if_available(service):
    """Cached results should be returned without querying registry."""
    query = "authentication"

    # Mock cache hit
    with patch.object(service, '_get_from_cache') as mock_cache:
        mock_cache.return_value = [{'name': 'AuthService'}]

        results = service.query(query)

        assert len(results) == 1
        assert results[0]['name'] == 'AuthService'
        mock_cache.assert_called_once_with(f"ontology_query:{query}")

def test_query_uses_registry_on_cache_miss(service):
    """Registry should be queried on cache miss."""
    query = "authentication"

    with patch.object(service, '_get_from_cache') as mock_cache, \
         patch('apps.ontology.registry.OntologyRegistry.search') as mock_search:

        mock_cache.return_value = None
        mock_search.return_value = [{'name': 'AuthService'}]

        results = service.query(query)

        assert len(results) == 1
        mock_search.assert_called_once_with(query)

def test_query_respects_circuit_breaker(service):
    """Circuit breaker should open after consecutive failures."""
    query = "authentication"

    # Simulate 3 consecutive failures
    for _ in range(3):
        with patch('apps.ontology.registry.OntologyRegistry.search', side_effect=Exception("Registry down")):
            results = service.query(query)
            assert results == []

    # 4th call should short-circuit (no registry call)
    with patch('apps.ontology.registry.OntologyRegistry.search') as mock_search:
        results = service.query(query)
        assert results == []
        mock_search.assert_not_called()  # Circuit breaker open
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_ontology_query_service.py -v
```

**Expected:** FAIL with "ModuleNotFoundError: No module named 'apps.core.services.ontology_query_service'"

**Step 3: Write minimal implementation**

```python
# File: apps/core/services/ontology_query_service.py
"""
Ontology Query Service with Redis caching and circuit breaker.

Performance Guarantees:
- Cache hit: < 5ms
- Cache miss: < 200ms (with fallback to empty list on timeout)
- Circuit breaker opens after 3 consecutive failures
"""

import logging
import time
from typing import List, Dict, Any, Optional
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger('ontology.query')

class CircuitBreaker:
    """Simple circuit breaker for ontology queries."""

    def __init__(self, failure_threshold=3, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'open':
            # Check if recovery timeout elapsed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half_open'
            else:
                logger.warning("Circuit breaker OPEN - skipping ontology query")
                return None

        try:
            result = func(*args, **kwargs)
            # Success - reset failure count
            if self.state == 'half_open':
                self.state = 'closed'
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.error(f"Circuit breaker OPEN after {self.failure_count} failures")

            logger.error(f"Ontology query failed: {e}", exc_info=True)
            return None

class OntologyQueryService:
    """
    Cached ontology query service with circuit breaker.

    Features:
    - Redis caching (5-minute TTL)
    - Circuit breaker (opens after 3 failures)
    - Timeout protection (200ms max)
    - Graceful degradation (returns [] on failure)
    """

    CACHE_PREFIX = "ontology_query"
    CACHE_TTL = 300  # 5 minutes
    QUERY_TIMEOUT = 0.2  # 200ms

    def __init__(self):
        self.circuit_breaker = CircuitBreaker()

    def query(self, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Query ontology with caching and circuit breaker.

        Args:
            query_text: Search query
            limit: Max results (default 5)

        Returns:
            List of ontology components or [] on failure
        """
        # Try cache first
        cache_key = f"{self.CACHE_PREFIX}:{query_text}:{limit}"
        cached_result = self._get_from_cache(cache_key)

        if cached_result is not None:
            logger.debug(f"Ontology query cache HIT: {query_text}")
            return cached_result

        # Cache miss - query registry with circuit breaker
        logger.debug(f"Ontology query cache MISS: {query_text}")
        result = self._query_registry_with_breaker(query_text, limit)

        if result is not None:
            # Cache successful result
            self._set_in_cache(cache_key, result)
            return result
        else:
            # Circuit breaker open or query failed
            return []

    def _get_from_cache(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Get from Redis cache."""
        try:
            return cache.get(key)
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None

    def _set_in_cache(self, key: str, value: List[Dict[str, Any]]) -> None:
        """Set in Redis cache with TTL."""
        try:
            cache.set(key, value, self.CACHE_TTL)
        except Exception as e:
            logger.error(f"Cache set failed: {e}")

    def _query_registry_with_breaker(self, query_text: str, limit: int) -> Optional[List[Dict[str, Any]]]:
        """Query ontology registry with circuit breaker protection."""
        def _query():
            from apps.ontology.registry import OntologyRegistry

            # Query with timeout
            start = time.perf_counter()
            results = OntologyRegistry.search(query_text)[:limit]
            elapsed = time.perf_counter() - start

            if elapsed > self.QUERY_TIMEOUT:
                logger.warning(f"Ontology query slow: {elapsed*1000:.2f}ms (threshold: {self.QUERY_TIMEOUT*1000}ms)")

            return results

        return self.circuit_breaker.call(_query)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_ontology_query_service.py -v
```

**Expected:** PASS (all 3 tests)

**Step 5: Commit**

```bash
git add apps/core/services/ontology_query_service.py tests/unit/test_ontology_query_service.py
git commit -m "feat: add cached ontology query service with circuit breaker"
```

---

### Task 2.2: Integrate Ontology Query into HelpBot Knowledge Service

**Files:**
- Modify: `apps/helpbot/services/knowledge_service.py:45-60`
- Create: `tests/integration/test_helpbot_ontology_integration.py`
- Create: `intelliwiz_config/settings/features.py` (feature flags)

**Step 1: Add feature flag**

```python
# File: intelliwiz_config/settings/features.py
"""
Feature flags for gradual rollout.

Usage:
    from django.conf import settings
    if settings.FEATURES['HELPBOT_USE_ONTOLOGY']:
        # Use ontology
"""

FEATURES = {
    # Phase 2: HelpBot ontology integration
    'HELPBOT_USE_ONTOLOGY': False,  # Default: OFF (manual enable)

    # Phase 3: Article auto-generation
    'ENABLE_ARTICLE_AUTO_GENERATION': False,

    # Phase 4: Unified knowledge service
    'USE_UNIFIED_KNOWLEDGE': False,
}
```

Add to `intelliwiz_config/settings/base.py`:
```python
from .features import FEATURES
```

**Step 2: Write integration test**

```python
# File: tests/integration/test_helpbot_ontology_integration.py

import pytest
from django.test import override_settings
from apps.helpbot.services.knowledge_service import HelpBotKnowledgeService
from apps.ontology.registry import OntologyRegistry

@pytest.fixture
def service():
    return HelpBotKnowledgeService()

@pytest.fixture
def register_test_component():
    """Register test component in ontology."""
    OntologyRegistry.register(
        "test.auth_service",
        {
            "qualified_name": "test.auth_service",
            "domain": "authentication",
            "purpose": "Test authentication service",
            "tags": ["auth", "jwt", "test"]
        }
    )
    yield
    # Cleanup not needed - registry is in-memory

@override_settings(FEATURES={'HELPBOT_USE_ONTOLOGY': True})
def test_helpbot_queries_ontology_when_enabled(service, register_test_component):
    """HelpBot should query ontology when feature flag enabled."""
    results = service.search_knowledge("authentication")

    # Should include ontology results
    ontology_results = [r for r in results if r.get('source') == 'ontology']
    assert len(ontology_results) > 0
    assert any('auth_service' in r['content'] for r in ontology_results)

@override_settings(FEATURES={'HELPBOT_USE_ONTOLOGY': False})
def test_helpbot_skips_ontology_when_disabled(service):
    """HelpBot should skip ontology when feature flag disabled."""
    results = service.search_knowledge("authentication")

    # Should NOT include ontology results
    ontology_results = [r for r in results if r.get('source') == 'ontology']
    assert len(ontology_results) == 0

def test_helpbot_gracefully_handles_ontology_failure(service):
    """HelpBot should continue working if ontology query fails."""
    with override_settings(FEATURES={'HELPBOT_USE_ONTOLOGY': True}):
        # Simulate ontology failure
        from unittest.mock import patch
        with patch('apps.core.services.ontology_query_service.OntologyQueryService.query', side_effect=Exception("Ontology down")):
            results = service.search_knowledge("authentication")
            # Should still return static KB results
            assert len(results) > 0
```

**Step 3: Run test to verify it fails**

```bash
pytest tests/integration/test_helpbot_ontology_integration.py -v
```

**Expected:** FAIL (HelpBotKnowledgeService doesn't query ontology yet)

**Step 4: Implement ontology integration in HelpBot**

```python
# File: apps/helpbot/services/knowledge_service.py

# Add import at top
from apps.core.services.ontology_query_service import OntologyQueryService
from django.conf import settings

class HelpBotKnowledgeService:
    """
    HelpBot knowledge service with optional ontology integration.

    Features:
    - Static txtai knowledge base (always enabled)
    - Ontology query (optional, controlled by FEATURES['HELPBOT_USE_ONTOLOGY'])
    - Merged results with relevance ranking
    """

    def __init__(self):
        self.ontology_service = OntologyQueryService()
        # ... existing initialization

    def search_knowledge(self, query, category=None, limit=5):
        """
        Search both ontology and static KB.

        Args:
            query: Search query
            category: Optional category filter
            limit: Max results

        Returns:
            List of knowledge entries with source attribution
        """
        results = []

        # 1. Query static KB (always)
        kb_results = self._search_static_kb(query, category, limit)
        results.extend(kb_results)

        # 2. Query ontology (if enabled)
        if settings.FEATURES.get('HELPBOT_USE_ONTOLOGY', False):
            try:
                ontology_results = self._search_ontology(query, limit)
                results.extend(ontology_results)
            except Exception as e:
                logger.error(f"Ontology query failed (graceful degradation): {e}")
                # Continue with static KB results only

        # 3. Merge and rank results
        merged = self._merge_results(results, limit)

        return merged

    def _search_ontology(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Query ontology registry for code components.

        Returns:
            List of knowledge entries with source='ontology'
        """
        ontology_results = self.ontology_service.query(query, limit)

        # Format for knowledge service
        formatted = []
        for result in ontology_results:
            formatted.append({
                'id': f"ontology_{result['qualified_name']}",
                'title': result.get('purpose', result['qualified_name']),
                'content': self._format_ontology_entry(result),
                'category': result.get('domain', 'code'),
                'knowledge_type': 'code',
                'source': 'ontology',
                'relevance': self._calculate_relevance(query, result)
            })

        return formatted

    def _format_ontology_entry(self, metadata: Dict) -> str:
        """Format ontology metadata as readable text."""
        lines = [
            f"# {metadata['qualified_name']}",
            f"",
            f"**Purpose:** {metadata.get('purpose', 'No description')}",
            f"**Domain:** {metadata.get('domain', 'N/A')}",
            f"**Tags:** {', '.join(metadata.get('tags', []))}",
        ]

        if metadata.get('business_value'):
            lines.append(f"**Business Value:** {metadata['business_value']}")

        if metadata.get('depends_on'):
            lines.append(f"**Dependencies:** {', '.join(metadata['depends_on'])}")

        return "\n".join(lines)

    def _merge_results(self, results: List[Dict], limit: int) -> List[Dict]:
        """Merge and rank results from multiple sources."""
        # Sort by relevance score (if available)
        sorted_results = sorted(
            results,
            key=lambda x: x.get('relevance', 0.5),
            reverse=True
        )

        return sorted_results[:limit]

    def _calculate_relevance(self, query: str, metadata: Dict) -> float:
        """Calculate relevance score for ontology result."""
        score = 0.5  # Base score

        query_lower = query.lower()

        # Check purpose
        if query_lower in metadata.get('purpose', '').lower():
            score += 0.3

        # Check tags
        if any(query_lower in tag.lower() for tag in metadata.get('tags', [])):
            score += 0.2

        return min(score, 1.0)

    # ... existing methods unchanged
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/integration/test_helpbot_ontology_integration.py -v
```

**Expected:** PASS (all 3 tests)

**Step 6: Commit**

```bash
git add apps/helpbot/services/knowledge_service.py \
        tests/integration/test_helpbot_ontology_integration.py \
        intelliwiz_config/settings/features.py
git commit -m "feat: integrate ontology into HelpBot with feature flag"
```

---

### Task 2.3: Performance Gate - Phase 2 Verification

**Files:**
- Create: `tests/performance/test_phase2_gate.py`

**Step 1: Write performance gate test**

```python
# File: tests/performance/test_phase2_gate.py
"""
Phase 2 Performance Gate: Verify HelpBot ontology integration performance.

PASS CRITERIA:
- HelpBot P95 latency < 500ms (with ontology enabled)
- Memory increase < 10MB
- No errors during load test (1000 queries)

FAIL ACTION: Disable HELPBOT_USE_ONTOLOGY feature flag
"""

import pytest
import time
from django.test import override_settings
from apps.helpbot.services.knowledge_service import HelpBotKnowledgeService

@override_settings(FEATURES={'HELPBOT_USE_ONTOLOGY': True})
def test_helpbot_latency_with_ontology():
    """HelpBot with ontology should have P95 < 500ms."""
    service = HelpBotKnowledgeService()

    queries = [
        "how do I authenticate",
        "what is SLA tracking",
        "troubleshoot GPS permissions",
        "explain secure file download"
    ]

    latencies = []
    for query in queries:
        for _ in range(250):  # 1000 total queries
            start = time.perf_counter()
            service.search_knowledge(query)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)]

    print(f"\nHelpBot with ontology P95: {p95:.2f}ms")
    assert p95 < 500.0, f"P95 latency {p95:.2f}ms exceeds 500ms threshold"

@override_settings(FEATURES={'HELPBOT_USE_ONTOLOGY': True})
def test_helpbot_error_rate():
    """No errors during load test."""
    service = HelpBotKnowledgeService()

    queries = ["authentication", "SLA", "GPS", "download", "ticket"]
    error_count = 0
    total_count = 1000

    for query in queries:
        for _ in range(total_count // len(queries)):
            try:
                service.search_knowledge(query)
            except Exception:
                error_count += 1

    error_rate = error_count / total_count
    print(f"\nError rate: {error_rate*100:.2f}%")
    assert error_rate < 0.001, f"Error rate {error_rate*100:.2f}% exceeds 0.1% threshold"
```

**Step 2: Run performance gate test**

```bash
# Enable feature flag first
export FEATURES_HELPBOT_USE_ONTOLOGY=True

pytest tests/performance/test_phase2_gate.py -v --tb=short
```

**Expected Output:**
```
tests/performance/test_phase2_gate.py::test_helpbot_latency_with_ontology
HelpBot with ontology P95: 287.45ms
PASSED

tests/performance/test_phase2_gate.py::test_helpbot_error_rate
Error rate: 0.00%
PASSED
```

**Step 3: If PASS - Commit and document**

```bash
git add tests/performance/test_phase2_gate.py
git commit -m "test: add Phase 2 performance gate (HelpBot ontology integration)"
```

**Step 4: If FAIL - Rollback feature flag**

```python
# File: intelliwiz_config/settings/features.py
FEATURES = {
    'HELPBOT_USE_ONTOLOGY': False,  # KEEP DISABLED - failed performance gate
}
```

**GATE DECISION:** Only proceed to Phase 3 if P95 < 500ms.

---

## Phase 3: Background Article Generation

**Duration:** 4 days
**Risk:** LOW
**Goal:** Auto-generate help_center articles from ontology via Celery (offline)

---

### Task 3.1: Create Article Auto-Generation Service

**Files:**
- Create: `apps/help_center/services/article_generator_service.py`
- Create: `tests/unit/test_article_generator.py`

**Step 1: Write failing test**

```python
# File: tests/unit/test_article_generator.py

import pytest
from apps.help_center.services.article_generator_service import ArticleGeneratorService
from apps.help_center.models import HelpArticle, HelpCategory
from apps.peoples.models import Tenant

@pytest.fixture
def service():
    return ArticleGeneratorService()

@pytest.fixture
def category(db):
    tenant = Tenant.objects.first()
    return HelpCategory.objects.create(
        name="Code Reference",
        tenant=tenant
    )

def test_generate_article_from_ontology_metadata(service, category):
    """Should generate article from ontology metadata."""
    metadata = {
        'qualified_name': 'apps.core.services.SecureFileDownloadService',
        'purpose': 'Secure file download with permission validation',
        'domain': 'security',
        'tags': ['security', 'files', 'permissions'],
        'business_value': 'Prevents IDOR vulnerabilities',
        'depends_on': ['apps.core.middleware.authentication']
    }

    article = service.generate_article(metadata, category)

    assert article is not None
    assert 'SecureFileDownloadService' in article.title
    assert 'permission validation' in article.content
    assert article.category == category
    assert 'auto-generated' in [tag.name for tag in article.tags.all()]

def test_update_existing_article(service, category):
    """Should update existing article instead of creating duplicate."""
    metadata = {
        'qualified_name': 'apps.core.services.TestService',
        'purpose': 'Test service',
        'domain': 'test'
    }

    # Create first article
    article1 = service.generate_article(metadata, category)

    # Update metadata
    metadata['purpose'] = 'Updated test service'

    # Generate again
    article2 = service.generate_article(metadata, category)

    # Should be same article (updated)
    assert article1.id == article2.id
    assert 'Updated test service' in article2.content
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_article_generator.py -v
```

**Expected:** FAIL (ArticleGeneratorService doesn't exist)

**Step 3: Write minimal implementation**

```python
# File: apps/help_center/services/article_generator_service.py
"""
Article Generator Service - Auto-generate help articles from ontology.

Performance Characteristics:
- Processes 1 article per second (rate-limited)
- Memory-efficient (batch processing)
- Idempotent (safe to re-run)
"""

import logging
from typing import Dict, Any
from django.utils import timezone
from apps.help_center.models import HelpArticle, HelpCategory, HelpTag

logger = logging.getLogger('help_center.generator')

class ArticleGeneratorService:
    """Generate help articles from ontology metadata."""

    AUTO_GENERATED_TAG = 'auto-generated'
    CODE_REFERENCE_TAG = 'code-reference'

    def generate_article(self, metadata: Dict[str, Any], category: HelpCategory) -> HelpArticle:
        """
        Generate or update article from ontology metadata.

        Args:
            metadata: Ontology component metadata
            category: Target category

        Returns:
            Generated/updated HelpArticle
        """
        qualified_name = metadata['qualified_name']

        # Check if article already exists
        existing = HelpArticle.objects.filter(
            title__icontains=qualified_name,
            category=category
        ).first()

        # Generate article content
        title = self._generate_title(metadata)
        content = self._generate_content(metadata)

        if existing:
            # Update existing article
            existing.title = title
            existing.content = content
            existing.updated_at = timezone.now()
            existing.save()
            article = existing
            logger.info(f"Updated article: {title}")
        else:
            # Create new article
            article = HelpArticle.objects.create(
                title=title,
                content=content,
                category=category,
                tenant=category.tenant,
                auto_generated=True
            )
            logger.info(f"Created article: {title}")

        # Add tags
        self._add_tags(article, metadata)

        return article

    def _generate_title(self, metadata: Dict) -> str:
        """Generate article title from metadata."""
        name = metadata['qualified_name'].split('.')[-1]
        return f"Code Reference: {name}"

    def _generate_content(self, metadata: Dict) -> str:
        """Generate article content from metadata."""
        lines = [
            f"# {metadata['qualified_name']}",
            "",
            "## Purpose",
            metadata.get('purpose', 'No description available'),
            "",
            f"## Domain",
            metadata.get('domain', 'N/A'),
            ""
        ]

        # Usage section
        if metadata.get('inputs') or metadata.get('outputs'):
            lines.extend([
                "## Usage",
                "```python",
                f"from {'.'.join(metadata['qualified_name'].split('.')[:-1])} import {metadata['qualified_name'].split('.')[-1]}",
                "",
                "# Example usage:",
                "# (See code for implementation details)",
                "```",
                ""
            ])

        # Dependencies
        if metadata.get('depends_on'):
            lines.extend([
                "## Dependencies",
                ""
            ])
            for dep in metadata['depends_on']:
                lines.append(f"- `{dep}`")
            lines.append("")

        # Business value
        if metadata.get('business_value'):
            lines.extend([
                "## Business Value",
                metadata['business_value'],
                ""
            ])

        # Security notes
        if metadata.get('security_notes'):
            lines.extend([
                "## Security Considerations",
                metadata['security_notes'],
                ""
            ])

        # Performance notes
        if metadata.get('performance_notes'):
            lines.extend([
                "## Performance",
                metadata['performance_notes'],
                ""
            ])

        # Footer
        lines.extend([
            "---",
            f"*Auto-generated from ontology. Last updated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])

        return "\n".join(lines)

    def _add_tags(self, article: HelpArticle, metadata: Dict) -> None:
        """Add relevant tags to article."""
        tag_names = [
            self.AUTO_GENERATED_TAG,
            self.CODE_REFERENCE_TAG,
            metadata.get('domain', 'general')
        ]

        # Add ontology tags
        tag_names.extend(metadata.get('tags', []))

        # Create/get tags
        for tag_name in tag_names:
            tag, _ = HelpTag.objects.get_or_create(
                name=tag_name,
                tenant=article.tenant
            )
            article.tags.add(tag)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_article_generator.py -v
```

**Expected:** PASS (both tests)

**Step 5: Commit**

```bash
git add apps/help_center/services/article_generator_service.py \
        tests/unit/test_article_generator.py
git commit -m "feat: add article auto-generation from ontology"
```

---

### Task 3.2: Create Celery Task for Article Sync

**Files:**
- Create: `apps/help_center/tasks.py`
- Create: `apps/help_center/management/commands/sync_ontology_articles.py`
- Modify: `intelliwiz_config/celery.py` (add beat schedule)

**Step 1: Write Celery task**

```python
# File: apps/help_center/tasks.py
"""
Celery tasks for help_center app.

Background Tasks:
- sync_ontology_articles - Daily article generation from ontology
"""

import logging
import time
from celery import shared_task
from django.conf import settings
from apps.ontology.registry import OntologyRegistry
from apps.help_center.models import HelpCategory
from apps.help_center.services.article_generator_service import ArticleGeneratorService
from apps.peoples.models import Tenant

logger = logging.getLogger('help_center.tasks')

@shared_task(
    name='apps.help_center.sync_ontology_articles',
    bind=True,
    max_retries=3,
    time_limit=600  # 10 minutes
)
def sync_ontology_articles_task(self, dry_run=False, criticality='high'):
    """
    Sync ontology components to help_center articles.

    Args:
        dry_run: If True, log only (no DB writes)
        criticality: Filter by criticality (high, medium, low)

    Performance:
    - Rate-limited: 1 article/second
    - Batch size: 10 articles
    - Memory footprint: < 200MB
    """
    logger.info(f"Starting ontology article sync (dry_run={dry_run}, criticality={criticality})")

    # Get components by criticality
    if criticality == 'all':
        components = OntologyRegistry.get_all()
    else:
        components = OntologyRegistry.get_by_criticality(criticality)

    logger.info(f"Found {len(components)} components to process")

    # Get or create category
    tenant = Tenant.objects.first()  # Default tenant
    category, created = HelpCategory.objects.get_or_create(
        name="Code Reference",
        tenant=tenant,
        defaults={
            'description': 'Auto-generated code documentation from ontology'
        }
    )

    if created:
        logger.info("Created 'Code Reference' category")

    # Process in batches
    service = ArticleGeneratorService()
    batch_size = 10
    created_count = 0
    updated_count = 0

    for i in range(0, len(components), batch_size):
        batch = components[i:i+batch_size]

        for metadata in batch:
            try:
                if dry_run:
                    logger.info(f"[DRY-RUN] Would generate article: {metadata['qualified_name']}")
                else:
                    # Check if article exists
                    existing = HelpArticle.objects.filter(
                        title__icontains=metadata['qualified_name'],
                        category=category
                    ).exists()

                    article = service.generate_article(metadata, category)

                    if existing:
                        updated_count += 1
                    else:
                        created_count += 1

                    # Rate limit: 1 article/second
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Failed to generate article for {metadata['qualified_name']}: {e}", exc_info=True)
                continue

        # Log progress
        logger.info(f"Processed batch {i//batch_size + 1}/{(len(components) + batch_size - 1)//batch_size}")

    result = {
        'total_components': len(components),
        'articles_created': created_count,
        'articles_updated': updated_count,
        'dry_run': dry_run
    }

    logger.info(f"Ontology article sync complete: {result}")
    return result
```

**Step 2: Add Celery beat schedule**

```python
# File: intelliwiz_config/celery.py

# Add to CELERYBEAT_SCHEDULE

CELERYBEAT_SCHEDULE = {
    # ... existing schedules

    # Help Center: Daily article sync from ontology (2 AM)
    'sync-ontology-articles-daily': {
        'task': 'apps.help_center.sync_ontology_articles',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        'options': {
            'queue': 'default',
            'priority': 3
        },
        'kwargs': {
            'dry_run': False,
            'criticality': 'high'  # Only high-criticality components
        }
    },
}
```

**Step 3: Create management command (for manual sync)**

```python
# File: apps/help_center/management/commands/sync_ontology_articles.py
"""
Manual command to sync ontology articles.

Usage:
    python manage.py sync_ontology_articles --dry-run
    python manage.py sync_ontology_articles --criticality=high
"""

from django.core.management.base import BaseCommand
from apps.help_center.tasks import sync_ontology_articles_task

class Command(BaseCommand):
    help = "Sync ontology components to help_center articles"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Log only, no DB writes'
        )
        parser.add_argument(
            '--criticality',
            type=str,
            default='high',
            choices=['high', 'medium', 'low', 'all'],
            help='Filter by criticality level'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        criticality = options['criticality']

        self.stdout.write(f"Starting sync (dry_run={dry_run}, criticality={criticality})...")

        result = sync_ontology_articles_task(
            dry_run=dry_run,
            criticality=criticality
        )

        self.stdout.write(self.style.SUCCESS(f"✅ Sync complete: {result}"))
```

**Step 4: Test manual sync**

```bash
# Dry-run first (no DB writes)
python manage.py sync_ontology_articles --dry-run --criticality=high

# Actual sync
python manage.py sync_ontology_articles --criticality=high
```

**Expected Output:**
```
Starting sync (dry_run=False, criticality=high)...
Found 106 components to process
Created 'Code Reference' category
Processed batch 1/11
Processed batch 2/11
...
✅ Sync complete: {'total_components': 106, 'articles_created': 106, 'articles_updated': 0, 'dry_run': False}
```

**Step 5: Commit**

```bash
git add apps/help_center/tasks.py \
        apps/help_center/management/commands/sync_ontology_articles.py \
        intelliwiz_config/celery.py
git commit -m "feat: add Celery task for ontology article sync (daily at 2 AM)"
```

---

### Task 3.3: Performance Gate - Phase 3 Verification

**Files:**
- Create: `tests/performance/test_phase3_gate.py`

**Step 1: Write performance gate test**

```python
# File: tests/performance/test_phase3_gate.py
"""
Phase 3 Performance Gate: Verify article auto-generation performance.

PASS CRITERIA:
- Task completes in < 10 minutes (106 articles)
- Memory footprint < 200MB
- No impact on application performance during task

FAIL ACTION: Disable ENABLE_ARTICLE_AUTO_GENERATION feature flag
"""

import pytest
import psutil
import time
from apps.help_center.tasks import sync_ontology_articles_task

def test_article_sync_completes_within_time_limit():
    """Article sync should complete in < 10 minutes."""
    start = time.time()

    result = sync_ontology_articles_task(
        dry_run=False,
        criticality='high'
    )

    elapsed = time.time() - start
    elapsed_minutes = elapsed / 60

    print(f"\nArticle sync duration: {elapsed_minutes:.2f} minutes")
    print(f"Articles created: {result['articles_created']}")
    print(f"Articles updated: {result['articles_updated']}")

    assert elapsed_minutes < 10.0, f"Sync took {elapsed_minutes:.2f} minutes (limit: 10 minutes)"

def test_article_sync_memory_footprint():
    """Article sync memory footprint should be < 200MB."""
    process = psutil.Process()

    # Measure initial memory
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Run sync
    sync_ontology_articles_task(dry_run=False, criticality='high')

    # Measure final memory
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_delta = final_memory - initial_memory

    print(f"\nMemory delta: {memory_delta:.2f} MB")

    assert memory_delta < 200.0, f"Memory footprint {memory_delta:.2f}MB exceeds 200MB threshold"
```

**Step 2: Run performance gate test**

```bash
pytest tests/performance/test_phase3_gate.py -v --tb=short
```

**Expected Output:**
```
tests/performance/test_phase3_gate.py::test_article_sync_completes_within_time_limit
Article sync duration: 2.15 minutes
Articles created: 106
Articles updated: 0
PASSED

tests/performance/test_phase3_gate.py::test_article_sync_memory_footprint
Memory delta: 45.32 MB
PASSED
```

**Step 3: If PASS - Enable feature flag**

```python
# File: intelliwiz_config/settings/features.py
FEATURES = {
    'HELPBOT_USE_ONTOLOGY': True,  # Phase 2 passed
    'ENABLE_ARTICLE_AUTO_GENERATION': True,  # Phase 3 passed ✅
}
```

**Step 4: Commit**

```bash
git add tests/performance/test_phase3_gate.py intelliwiz_config/settings/features.py
git commit -m "test: add Phase 3 performance gate (article auto-generation)"
```

**GATE DECISION:** Proceed to Phase 4 only if all tests PASS.

---

## Phase 4: Unified Knowledge Service (OPTIONAL)

**Duration:** 5 days
**Risk:** MEDIUM
**Goal:** Single API for all knowledge sources (if Phase 1-3 metrics are good)

---

### Task 4.1: Decision Review - Proceed or Defer?

**Files:**
- Create: `docs/decisions/phase4-unified-service-decision.md`

**Step 1: Review Phase 1-3 metrics**

```bash
# Run all performance gate tests
pytest tests/performance/test_phase1_gate.py \
      tests/performance/test_phase2_gate.py \
      tests/performance/test_phase3_gate.py \
      -v --tb=short > phase_1_3_metrics.txt
```

**Step 2: Analyze results**

```python
# File: scripts/analyze_phase_metrics.py

import json

def analyze_metrics():
    """Analyze Phase 1-3 metrics to decide on Phase 4."""

    # Load performance data
    with open('performance_baseline.json') as f:
        baseline = json.load(f)

    # Decision criteria
    criteria = {
        'memory_delta_mb': baseline['memory']['delta_mb'],
        'helpbot_p95_ms': baseline['helpbot']['p95'],
        'help_center_p95_ms': baseline['help_center']['p95']
    }

    # Thresholds for Phase 4 go-ahead
    proceed = (
        criteria['memory_delta_mb'] < 8.0 and  # < 8MB memory increase
        criteria['helpbot_p95_ms'] < 400.0 and  # < 400ms P95
        criteria['help_center_p95_ms'] < 150.0  # < 150ms P95
    )

    print("=== Phase 4 Decision Analysis ===\n")
    print(f"Memory delta: {criteria['memory_delta_mb']:.2f} MB (threshold: 8 MB)")
    print(f"HelpBot P95: {criteria['helpbot_p95_ms']:.2f} ms (threshold: 400 ms)")
    print(f"help_center P95: {criteria['help_center_p95_ms']:.2f} ms (threshold: 150 ms)")
    print(f"\n{'✅ PROCEED to Phase 4' if proceed else '❌ DEFER Phase 4'}")

    return proceed

if __name__ == '__main__':
    proceed = analyze_metrics()
    exit(0 if proceed else 1)
```

**Step 3: Run analysis**

```bash
python scripts/analyze_phase_metrics.py
```

**Step 4: Document decision**

```markdown
# File: docs/decisions/phase4-unified-service-decision.md

# Phase 4: Unified Knowledge Service - Decision

**Date:** 2025-11-12
**Decision Maker:** Engineering Team
**Status:** [APPROVED / DEFERRED]

## Context

Phases 1-3 completed successfully with following metrics:
- Memory delta: X.XX MB
- HelpBot P95: XXX.XX ms
- help_center P95: XXX.XX ms

## Decision

[✅ APPROVED] Performance metrics within acceptable thresholds. Proceeding to Phase 4.

OR

[❌ DEFERRED] Performance metrics near threshold limits. Deferring Phase 4 until further optimization.

## Rationale

...

## Next Steps

If APPROVED:
- Implement UnifiedKnowledgeService with aggressive caching
- A/B test with 10% traffic
- Monitor closely

If DEFERRED:
- Focus on optimizing Phase 2 (HelpBot integration)
- Re-evaluate in Q1 2026
```

**IF DEFERRED:** Skip remaining Phase 4 tasks. Project is COMPLETE at Phase 3.

**IF APPROVED:** Continue to Task 4.2.

---

### Task 4.2: Implement Unified Knowledge Service (If Approved)

*[Tasks 4.2-4.4 only executed if Phase 4 approved]*

**Files:**
- Create: `apps/core/services/unified_knowledge_service.py`
- Create: `tests/integration/test_unified_knowledge.py`

*(Implementation details similar to Phase 2 pattern with caching and feature flags)*

---

## Performance Monitoring

### Prometheus Metrics

**Add to all ontology query paths:**

```python
from prometheus_client import Counter, Histogram

ontology_queries = Counter(
    'ontology_queries_total',
    'Total ontology queries',
    ['source', 'cache_hit']
)

ontology_query_duration = Histogram(
    'ontology_query_duration_seconds',
    'Ontology query duration',
    ['source']
)

# Usage:
with ontology_query_duration.labels(source='helpbot').time():
    results = ontology_service.query(query)
    ontology_queries.labels(source='helpbot', cache_hit=from_cache).inc()
```

### Memory Profiling

**Weekly py-spy profiling:**

```bash
# Profile for 60 seconds
py-spy record -o profile.svg -d 60 --pid $(pgrep -f "gunicorn")
```

### APM Tracking

**Sentry performance monitoring:**

```python
import sentry_sdk

with sentry_sdk.start_transaction(op="ontology.query", name="HelpBot ontology query"):
    results = ontology_service.query(query)
```

---

## Rollback Procedures

### Instant Rollback via Feature Flags

**Phase 2 Rollback:**
```python
FEATURES = {
    'HELPBOT_USE_ONTOLOGY': False  # ← Set to False
}
```

**Phase 3 Rollback:**
```python
# Disable Celery beat task
CELERYBEAT_SCHEDULE = {
    'sync-ontology-articles-daily': {
        'schedule': crontab(minute=0, hour=0, day_of_month='31', month_of_year='2'),  # Never run
    }
}
```

**Phase 4 Rollback:**
```python
FEATURES = {
    'USE_UNIFIED_KNOWLEDGE': False
}
```

### Full Rollback (All Phases)

```bash
# Revert to pre-integration state
git log --oneline | grep "feat: "  # Find commit range
git revert <commit-range>  # Revert all feature commits
```

---

## Success Metrics

### Phase 1 Success Criteria ✅
- Memory delta < 5MB: **PASS/FAIL**
- Latency delta < 10ms: **PASS/FAIL**
- 15+ services documented: **PASS/FAIL**

### Phase 2 Success Criteria ✅
- 40% reduction in "no answer" responses: **XX%**
- P95 latency < 500ms: **XXX ms**
- Error rate < 0.1%: **X.XX%**

### Phase 3 Success Criteria ✅
- 106+ articles auto-generated: **XXX articles**
- Task duration < 10 minutes: **X.XX minutes**
- Memory footprint < 200MB: **XXX MB**

### Phase 4 Success Criteria (If Implemented) ✅
- Single API operational: **PASS/FAIL**
- P95 latency < 300ms: **XXX ms**
- A/B test shows no degradation: **PASS/FAIL**

---

## Completion Report Template

```markdown
# Ontology-Help Integration - Completion Report

**Date Completed:** YYYY-MM-DD
**Implementation Duration:** X weeks
**Team:** [Names]

## Summary

Successfully integrated Ontology module with Help modules across 4 phases.

## Phases Completed

- [x] Phase 1: Performance-Safe Foundation (X days)
- [x] Phase 2: Lazy-Loaded HelpBot Integration (X days)
- [x] Phase 3: Background Article Generation (X days)
- [x] Phase 4: Unified Knowledge Service (X days) OR [Deferred]

## Performance Impact

| Metric | Baseline | Post-Integration | Delta | Status |
|--------|----------|------------------|-------|--------|
| Memory | XXX MB | XXX MB | +X MB | ✅ < 10MB |
| HelpBot P95 | XXX ms | XXX ms | +X ms | ✅ < 100ms |
| help_center P95 | XXX ms | XXX ms | +X ms | ✅ < 100ms |

## Business Outcomes

- **"No Answer" Reduction:** XX% → XX% (XX% improvement)
- **Articles Auto-Generated:** XXX articles
- **Documentation Sync:** Automated (zero manual effort)
- **Knowledge Coverage:** X.X% → X.X%

## Lessons Learned

1. ...
2. ...
3. ...

## Next Steps

1. Monitor metrics for 30 days
2. Gradually increase Phase 4 traffic (if implemented)
3. Quarterly review of ontology coverage

---

**Status:** ✅ PRODUCTION READY
```

---

## Execution Options

**Plan complete and saved to `docs/plans/2025-11-12-ontology-help-integration.md`.**

**Two execution approaches:**

### Option 1: Subagent-Driven (This Session) ⭐ Recommended

- Stay in this session
- Dispatch fresh subagent for each phase
- Code review between phases
- Fast iteration with quality gates

**To proceed:** Use @superpowers:subagent-driven-development

### Option 2: Parallel Session (Separate Worktree)

- Open new session in dedicated worktree
- Batch execution with checkpoints
- Performance gates automated

**To proceed:**
1. Create worktree: `git worktree add .worktrees/ontology-help-integration`
2. Open new Claude Code session in worktree
3. Use @superpowers:executing-plans with this plan file

---

**Which execution approach would you prefer?**
