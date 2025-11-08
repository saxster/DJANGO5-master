# ONTOLOGY INTELLIGENCE SYSTEM - IMPLEMENTATION PLAN
**Extending Coverage from 520 (80%) to 1,370+ (95%+) Components**

**Created**: 2025-11-01
**Strategy**: Evolutionary (build on existing ontology system)
**Timeline**: 12 weeks (parallel with decorator expansion)
**Team**: 2-3 engineers
**Investment**: $34,000 | **ROI**: $274k/year (808%)

---

## 🎯 VISION

Transform the ontology system from a **Python-only documentation framework** into a **full-stack, runtime-intelligent knowledge base** that gives Claude Code complete understanding of your entire system:

**Current**: 520 Python components with static metadata
**Target**: 1,370+ components (Python + templates + configs + migrations + tests) with runtime intelligence

---

## 📊 COVERAGE EXPANSION

### **Before (Current State)**
```
Python decorators:    520 components (Phases 1-10)
Templates:            0 (undocumented)
Configs:              0 (undocumented)
Migrations:           0 (undocumented)
Tests:                0 (undocumented)
Runtime intelligence: 0 (static metadata only)
────────────────────────────────────────────
TOTAL:                520 components (80% of Python, 36% of total codebase)
```

### **After (Target State)**
```
Python decorators:    520 components (gold-standard quality)
Templates:            200 components (HTML, Jinja2 parsed)
Configs:              50 components (YAML, JSON, settings)
Migrations:           100 components (Django migrations analyzed)
Tests:                500 components (pytest, unittest extracted)
Runtime intelligence: ✅ ALL components have AI scores
                      ✅ Python components have APM performance data
────────────────────────────────────────────────────────────────
TOTAL:                1,370 components (95%+ of entire codebase!)
```

---

## 🏗️ SYSTEM ARCHITECTURE

### **Component Diagram**

```
┌──────────────────────────────────────────────────────────────────────┐
│                    ONTOLOGY INTELLIGENCE SYSTEM                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  📝 METADATA SOURCES                                                 │
│  ┌─────────────────┐  ┌──────────────────────────────────────┐     │
│  │ Python          │  │ Non-Python                           │     │
│  │ Decorators      │  │ • TemplateMetadataCollector          │     │
│  │ @ontology()     │  │ • ConfigMetadataCollector            │     │
│  │ (520 existing)  │  │ • MigrationMetadataCollector         │     │
│  └────────┬────────┘  │ • TestMetadataCollector              │     │
│           │           └────────────┬─────────────────────────┘     │
│           │                        │                                │
│           └────────────┬───────────┘                                │
│                        ↓                                             │
│           ┌─────────────────────────────────┐                       │
│           │  Decorator-to-DB Sync           │                       │
│           │  • Hash-based change detection  │                       │
│           │  • Daily Celery task (2 AM)     │                       │
│           │  • Management command           │                       │
│           └────────────┬────────────────────┘                       │
│                        ↓                                             │
│  ═══════════════════════════════════════════════════════════════   │
│           ┌─────────────────────────────────┐                       │
│           │  PostgreSQL                      │                       │
│           │  ontology_metadata table         │                       │
│           │  • 1,370+ rows                   │                       │
│           │  • JSONB fields (tags, deps)     │                       │
│           │  • Vector embeddings (optional)  │                       │
│           │  • GIN indexes                   │                       │
│           └────────────┬────────────────────┘                       │
│  ═══════════════════════════════════════════════════════════════   │
│                        ↑                                             │
│           ┌────────────┴────────────┐                               │
│           │                         │                                │
│  🤖 AI INTELLIGENCE      📊 RUNTIME INTELLIGENCE                    │
│  ┌─────────────────┐   ┌─────────────────────────────┐            │
│  │ Importance      │   │ APM Webhook Receivers       │            │
│  │ Classifier      │   │ • New Relic                 │            │
│  │ • Complexity    │   │ • DataDog                   │            │
│  │ • Security      │   │ • Sentry                    │            │
│  │ • Usage         │   │                             │            │
│  │ • Change        │   │ Runtime Updater             │            │
│  └────────┬────────┘   │ • Performance baselines     │            │
│           │            │ • Error patterns            │            │
│           │            │ • Usage frequency           │            │
│           │            │ • Dependency CVE scanner    │            │
│           │            └────────────┬────────────────┘            │
│           └────────────┬────────────┘                              │
│                        ↓                                            │
│           (Updates ontology_metadata daily)                        │
│                        ↓                                            │
│  ═══════════════════════════════════════════════════════════════   │
│           ┌─────────────────────────────────┐                      │
│           │  Enhanced MCP Server             │                      │
│           │  • DB-first queries              │                      │
│           │  • Semantic search (vectors)     │                      │
│           │  • Runtime insights              │                      │
│           │  • Fallback to registry          │                      │
│           └────────────┬────────────────────┘                      │
│                        ↓                                            │
│           ┌─────────────────────────────────┐                      │
│           │  Claude Code (MCP Client)        │                      │
│           │  • Maximum LLM context           │                      │
│           │  • 95%+ codebase coverage        │                      │
│           │  • Runtime performance data      │                      │
│           └──────────────────────────────────┘                     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 📋 DATABASE SCHEMA

```sql
CREATE TABLE ontology_metadata (
    -- Identity
    id BIGSERIAL PRIMARY KEY,
    component_type VARCHAR(50) NOT NULL,  -- 'python', 'template', 'config', 'migration', 'test'
    file_path TEXT NOT NULL,
    component_name VARCHAR(500),
    qualified_name TEXT,

    -- Source Location
    line_start INTEGER,
    line_end INTEGER,

    -- Core Metadata
    domain VARCHAR(100),
    concept TEXT,
    purpose TEXT,
    criticality VARCHAR(20),  -- 'critical', 'high', 'medium', 'low'
    security_boundary BOOLEAN DEFAULT FALSE,
    tags JSONB DEFAULT '[]'::jsonb,

    -- Detailed Metadata
    inputs JSONB,
    outputs JSONB,
    side_effects JSONB,
    depends_on JSONB,
    used_by JSONB,
    security_notes TEXT,
    performance_notes TEXT,
    examples JSONB,

    -- AI-Computed Scores (0-100)
    importance_score INTEGER,       -- Composite: 30% usage + 25% security + 25% complexity + 20% change
    complexity_score INTEGER,       -- Cyclomatic complexity, LOC, nesting
    security_score INTEGER,         -- Security keywords, PII, criticality
    usage_score INTEGER,            -- Import count, call graph centrality, runtime calls
    change_score INTEGER,           -- Git commits, recency, authors

    -- Runtime Intelligence (from APM)
    performance_baseline JSONB,     -- {p50_ms, p95_ms, p99_ms, memory_mb}
    error_patterns JSONB,           -- [{error_type, frequency, last_seen, causes}]
    usage_frequency JSONB,          -- {daily_calls, peak_qps, users_affected}
    dependency_health JSONB,        -- [{package, version, cves}]

    -- Git Metadata
    git_last_author VARCHAR(255),
    git_last_commit_sha VARCHAR(40),
    git_last_modified TIMESTAMP,
    git_total_commits INTEGER,

    -- Sync & Provenance
    source VARCHAR(50) NOT NULL,    -- 'decorator', 'template_parser', 'apm', 'ai_classifier'
    decorator_hash VARCHAR(64),     -- SHA256 for change detection
    db_synced BOOLEAN DEFAULT FALSE,
    last_updated TIMESTAMP DEFAULT NOW(),
    last_runtime_update TIMESTAMP,
    last_ai_score_update TIMESTAMP,
    metadata_version INTEGER DEFAULT 1,

    -- LLM Optimization
    embedding VECTOR(1536),         -- OpenAI ada-002 for semantic search

    CONSTRAINT unique_component UNIQUE (file_path, component_name)
);

-- Indexes (12 total for query performance)
CREATE INDEX idx_file_path ON ontology_metadata(file_path);
CREATE INDEX idx_qualified_name ON ontology_metadata(qualified_name);
CREATE INDEX idx_component_type ON ontology_metadata(component_type);
CREATE INDEX idx_importance_score ON ontology_metadata(importance_score DESC NULLS LAST);
CREATE INDEX idx_criticality ON ontology_metadata(criticality);
CREATE INDEX idx_tags ON ontology_metadata USING GIN(tags);
CREATE INDEX idx_depends_on ON ontology_metadata USING GIN(depends_on);
CREATE INDEX idx_security_boundary ON ontology_metadata(security_boundary) WHERE security_boundary = TRUE;
CREATE INDEX idx_last_updated ON ontology_metadata(last_updated DESC);
CREATE INDEX idx_db_synced ON ontology_metadata(db_synced) WHERE db_synced = FALSE;
CREATE INDEX idx_embedding ON ontology_metadata USING ivfflat(embedding vector_cosine_ops);  -- Requires pgvector
```

---

## 🔧 IMPLEMENTATION PHASES (12 WEEKS)

### **PHASE A: Foundation (Weeks 1-3)**

**Goal**: PostgreSQL schema, Django app, decorator-to-DB sync

**Team**: 2 senior engineers
**Effort**: 60 hours

#### Week 1: Django App + Database (20 hours)
1. Create `apps/ontology_intelligence/` Django app (2 hours)
   ```bash
   python manage.py startapp ontology_intelligence apps/ontology_intelligence
   ```

2. Define Django model `OntologyMetadata` (6 hours)
   - Map PostgreSQL schema to Django ORM
   - JSONB fields using `django.contrib.postgres`
   - Custom manager with query helpers

3. Create migration (2 hours)
   ```bash
   python manage.py makemigrations ontology_intelligence
   python manage.py migrate
   ```

4. Add to settings (1 hour)
   ```python
   INSTALLED_APPS += ['apps.ontology_intelligence']
   ```

5. Write base tests (5 hours)
   - Model creation, JSONB queries
   - Index verification
   - Query performance

6. Documentation (4 hours)
   - Schema documentation
   - Model API documentation

#### Week 2: Decorator Sync (22 hours)
1. Implement `DecoratorToDBSync` class (10 hours)
   - Read from decorator registry
   - Compute metadata hash
   - Create/update DB entries
   - Preserve runtime data (don't overwrite)

2. Create management command (4 hours)
   ```bash
   python manage.py sync_ontology_to_db [--force] [--dry-run]
   ```

3. Add Celery beat schedule (2 hours)
   ```python
   'sync-ontology-to-db': {
       'task': 'apps.ontology_intelligence.tasks.sync_decorators_to_db',
       'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
   }
   ```

4. Testing (6 hours)
   - Test sync with Phase 1 decorators (56 components)
   - Test hash change detection
   - Test runtime data preservation
   - Test dry-run mode

#### Week 3: Base Collector Framework (18 hours)
1. Abstract `BaseMetadataCollector` class (4 hours)
   - Abstract methods: `can_handle()`, `extract_metadata()`
   - Common utilities: `_infer_domain()`, `compute_scores()`

2. File discovery logic (6 hours)
   - Iterate all Django apps
   - Filter by file type (.html, .yaml, .py in migrations/, test_*.py)
   - Parallel processing (multiprocessing)

3. Collector registry pattern (3 hours)
   - Auto-register collectors
   - Route files to appropriate collector

4. Testing framework (5 hours)
   - Test fixtures (sample templates, configs, migrations)
   - Collector base tests
   - Integration tests

**Phase A Deliverable**:
- ✅ `ontology_metadata` table created with 520 rows (synced from decorators)
- ✅ Daily auto-sync working (Celery task)
- ✅ Base collector framework ready for Phase B

---

### **PHASE B: Metadata Collectors (Weeks 4-6)**

**Goal**: Parse non-Python files (templates, configs, migrations, tests)

**Team**: 2-3 engineers
**Effort**: 80 hours

#### Week 4: Template Parser (20 hours)
**Target**: 200 HTML/Jinja2 templates

1. Jinja2 AST parsing (8 hours)
   ```python
   from jinja2 import Environment
   env = Environment()
   ast = env.parse(template_content)
   ```
   - Extract variables: `{{ user }}`, `{{ form }}`
   - Extract blocks: `{% block content %}`
   - Extract includes: `{% include "header.html" %}`
   - Extract extends: `{% extends "base.html" %}`

2. Context variable extraction (4 hours)
   - Detect all `{{ variable }}` references
   - Classify as required vs optional (inside {% if %})
   - Heuristic PII detection (user, email, phone)

3. Security analysis (6 hours)
   - Detect `{% autoescape off %}` (XSS risk)
   - Detect `{{ var|safe }}` (verify sanitization)
   - Check CSRF tokens in forms
   - Detect context in `<script>` tags (XSS risk)

4. Testing (2 hours)
   - Test with 10 sample templates
   - Verify AST parsing accuracy
   - Check security detection

**Week 4 Deliverable**: 200 templates documented in `ontology_metadata`

#### Week 5: Config + Migration Parsers (30 hours)
**Target**: 50 configs + 100 migrations

**Config Parser** (12 hours):
1. YAML/JSON parsing (4 hours)
   - yaml.safe_load() for YAML
   - json.loads() for JSON
   - Flatten nested configs

2. Python settings parsing (4 hours)
   - Parse settings files as Python modules
   - Extract constants (SECRET_KEY, DATABASE, etc.)
   - Detect environment variables

3. Security analysis (4 hours)
   - Detect hardcoded secrets
   - Flag DEBUG=True
   - Check SSL/TLS configs

**Migration Analyzer** (18 hours):
1. Django migration AST parsing (8 hours)
   - Extract operations (AddField, RemoveField, RunSQL)
   - Parse dependencies
   - Detect reversibility

2. Performance analysis (6 hours)
   - Table-locking operations (AddField with NOT NULL)
   - RunSQL performance concerns
   - Index creation time estimates

3. Security analysis (4 hours)
   - Detect data migrations touching PII
   - Check for SQL injection in RunSQL
   - Verify backward compatibility

**Week 5 Deliverable**: 150 additional components (50 configs + 100 migrations)

#### Week 6: Test Extractor (30 hours)
**Target**: 500 test files

1. pytest/unittest AST parsing (12 hours)
   - Extract test classes (unittest.TestCase)
   - Extract test methods (test_*, pytest functions)
   - Parse docstrings

2. Fixture extraction (6 hours)
   - pytest fixtures (@pytest.fixture)
   - Django fixtures (fixtures/)
   - Mock detection

3. Test classification (6 hours)
   - Unit vs integration (heuristics)
   - API tests (test_api_*)
   - Slow tests (@pytest.mark.slow)
   - Database tests (uses db fixture)

4. Coverage gap analysis (optional) (6 hours)
   - Link tests to source code
   - Identify untested components
   - Generate coverage report

**Week 6 Deliverable**:
- ✅ 1,370 total components in DB (95%+ coverage!)
- ✅ Python: 520, Templates: 200, Configs: 50, Migrations: 100, Tests: 500

---

### **PHASE C: Intelligence Layer (Weeks 7-9)**

**Goal**: AI importance scoring + runtime intelligence (APM + CVE)

**Team**: 2-3 engineers (1 must have ML experience)
**Effort**: 90 hours

#### Week 7: AI Importance Classifier (26 hours)

**Complexity Analyzer** (8 hours):
- Cyclomatic complexity (McCabe)
- Lines of code (LOC)
- Max nesting depth
- Function/class count
- Normalize to 0-100 score

**Security Sensitivity Detector** (8 hours):
- Keyword detection (password, secret, token, encrypt)
- Path-based detection (auth/, security/, crypto/)
- Metadata-based (security_boundary, criticality, PII tags)
- Normalize to 0-100 score

**Usage Metrics Analyzer** (6 hours):
- Static: Import count (grep/rg)
- Static: Call graph centrality (simplified PageRank)
- Runtime: Daily calls (from APM, if available)
- Normalize to 0-100 score

**Change Frequency Analyzer** (4 hours):
- Git history: Total commits
- Git history: Recent commits (90 days)
- Git history: Unique authors
- Normalize to 0-100 score

**Composite Score Calculation**:
```python
importance_score = (
    0.30 * usage_score +      # Highest weight - actual impact
    0.25 * security_score +   # Critical for security components
    0.25 * complexity_score + # Document complex code first
    0.20 * change_score       # Active code needs docs
)
```

**Week 7 Deliverable**: All 1,370 components have AI importance scores

#### Week 8: APM Integration (32 hours)

**Webhook Receivers** (18 hours):
1. New Relic webhook (8 hours)
   - Transaction traces → performance_baseline
   - Error analytics → error_patterns
   - Throughput data → usage_frequency

2. DataDog webhook (6 hours)
   - APM metrics → performance_baseline
   - Error tracking → error_patterns

3. Sentry webhook (4 hours)
   - Error events → error_patterns
   - Performance monitoring → performance_baseline

**Transaction Mapping Logic** (10 hours):
- Map API endpoints to viewsets
  - "Controller/api/v1/users/index" → `apps/api/viewsets/user_viewset.py`
- Map middleware to files
  - "Middleware/RateLimitingMiddleware" → `apps/core/middleware/rate_limiting.py`
- Map Celery tasks to files
  - "Task/sync_attendance_data" → `apps/attendance/tasks.py::sync_attendance_data`

**API Endpoints** (4 hours):
```python
# Django URL configuration
urlpatterns = [
    path('api/ontology/webhooks/newrelic/', views.newrelic_webhook),
    path('api/ontology/webhooks/datadog/', views.datadog_webhook),
    path('api/ontology/webhooks/sentry/', views.sentry_webhook),
]
```

**Week 8 Deliverable**: APM webhooks receiving data, updating ontology_metadata

#### Week 9: Runtime Updater + CVE Scanner (32 hours)

**Runtime Intelligence Updater** (16 hours):
1. Batch update logic (8 hours)
   - JSONB merging (append error patterns, update performance)
   - Timestamp tracking (last_runtime_update)
   - Conflict resolution (latest data wins)

2. Testing with sample APM data (8 hours)
   - Mock New Relic payloads
   - Verify JSONB merging
   - Test transaction mapping accuracy

**Dependency CVE Scanner** (16 hours):
1. `safety` CLI integration (8 hours)
   - Parse requirements.txt
   - Check each package for CVEs
   - Map packages to components (AST import analysis)

2. Scheduled scanning (4 hours)
   ```python
   'scan-dependency-cves': {
       'task': 'apps.ontology_intelligence.tasks.scan_dependencies',
       'schedule': crontab(hour=0, minute=0, day_of_week=0),  # Weekly
   }
   ```

3. Alert system (4 hours)
   - Email on critical CVE
   - Slack notification
   - Dashboard warning

**Week 9 Deliverable**:
- ✅ 520 Python components have runtime data (performance, errors, usage)
- ✅ All 1,370 components have dependency health status
- ✅ CVE alerts working

---

### **PHASE D: Integration & Polish (Weeks 10-12)**

**Goal**: Enhanced MCP server, semantic search, Dashboard v2

**Team**: 2 engineers
**Effort**: 50 hours

#### Week 10: Enhanced MCP Server (20 hours)

1. DB query implementation (8 hours)
   ```python
   @mcp.tool()
   async def ontology_query_intelligent(
       domain: str = None,
       tags: List[str] = None,
       min_importance: int = 70,
       include_runtime_data: bool = True
   ) -> Dict:
       # Query PostgreSQL
       queryset = OntologyMetadata.objects.all()
       if domain:
           queryset = queryset.filter(domain=domain)
       if tags:
           queryset = queryset.filter(tags__contains=tags)
       if min_importance:
           queryset = queryset.filter(importance_score__gte=min_importance)

       return format_mcp_response(queryset)
   ```

2. Fallback logic (4 hours)
   - Try DB query
   - Catch errors, fall back to decorator registry
   - Log fallback events

3. New MCP tools (6 hours)
   - `ontology_get_critical_components(min_score=80)`
   - `ontology_get_runtime_insights(file_path)`
   - `ontology_get_by_type(component_type='template')`

4. Testing with Claude Code (2 hours)
   - Manual testing via MCP inspector
   - Verify runtime data appears
   - Test fallback when DB down

**Week 10 Deliverable**: Enhanced MCP server operational

#### Week 11: Semantic Search (18 hours)

1. Vector embedding generation (10 hours)
   - OpenAI API integration
   - Batch embed all 1,370 components
   - Store in `embedding` column
   - Cost: 1,370 * 0.0001 = $0.14 (negligible)

2. pgvector integration (4 hours)
   - Install pgvector extension
   - Create ivfflat index
   - Test cosine similarity queries

3. Semantic search MCP tool (4 hours)
   ```python
   @mcp.tool()
   async def ontology_search_semantic(query: str, limit: int = 20) -> Dict:
       # Embed query
       query_embedding = openai.Embedding.create(input=query)['data'][0]['embedding']

       # Vector similarity search
       results = OntologyMetadata.objects.annotate(
           distance=CosineDistance('embedding', query_embedding)
       ).order_by('distance')[:limit]

       return format_results(results)
   ```

**Week 11 Deliverable**: Semantic search working (e.g., "GPS fraud detection" → geofence_validation_service.py)

#### Week 12: Dashboard V2 + Launch (12 hours)

1. Dashboard with runtime intelligence (8 hours)
   - Performance heatmap (slowest components)
   - Error frequency chart (most error-prone components)
   - Importance distribution (histogram)
   - CVE alerts (critical vulnerabilities)
   - Coverage by component type (Python, template, config, etc.)

2. Documentation (2 hours)
   - API documentation
   - MCP tool reference
   - Team training guide

3. Training session (2 hours)
   - Demo to team
   - Q&A
   - Feedback collection

**Week 12 Deliverable**:
- ✅ Full ontology intelligence system operational
- ✅ Dashboard v2 live
- ✅ Team trained
- 🎉 Launch celebration!

---

## 📦 DJANGO APP STRUCTURE

```
apps/ontology_intelligence/
├── __init__.py
├── apps.py
├── models.py                          # OntologyMetadata model
├── admin.py                           # Django admin for metadata
│
├── collectors/
│   ├── __init__.py
│   ├── base.py                        # BaseMetadataCollector
│   ├── template_collector.py         # TemplateMetadataCollector
│   ├── config_collector.py           # ConfigMetadataCollector
│   ├── migration_collector.py        # MigrationMetadataCollector
│   └── test_collector.py             # TestMetadataCollector
│
├── classifiers/
│   ├── __init__.py
│   ├── importance_classifier.py      # Composite importance scorer
│   ├── complexity_analyzer.py        # ComplexityAnalyzer
│   ├── security_detector.py          # SecuritySensitivityDetector
│   ├── usage_analyzer.py             # UsageMetricsAnalyzer
│   └── change_analyzer.py            # ChangeFrequencyAnalyzer
│
├── runtime/
│   ├── __init__.py
│   ├── apm_webhook_receiver.py       # APMWebhookReceiver
│   ├── newrelic_processor.py         # NewRelicProcessor
│   ├── datadog_processor.py          # DataDogProcessor
│   ├── sentry_processor.py           # SentryProcessor
│   ├── runtime_updater.py            # RuntimeIntelligenceUpdater
│   └── dependency_scanner.py         # DependencyHealthScanner
│
├── sync/
│   ├── __init__.py
│   ├── decorator_sync.py             # DecoratorToDBSync
│   └── embedding_sync.py             # VectorEmbeddingSync
│
├── management/
│   └── commands/
│       ├── sync_ontology_to_db.py    # Sync decorators → DB
│       ├── collect_all_metadata.py   # Run all collectors
│       ├── compute_ai_scores.py      # Compute importance scores
│       └── generate_embeddings.py    # Generate vector embeddings
│
├── tasks.py                          # Celery tasks (sync, collect, score, scan)
├── views.py                          # Webhook endpoints
├── urls.py                           # API routes
│
├── tests/
│   ├── test_collectors.py
│   ├── test_classifiers.py
│   ├── test_runtime.py
│   └── test_sync.py
│
└── migrations/
    └── 0001_initial.py               # Create ontology_metadata table
```

---

## 🎯 SUCCESS METRICS

### **Coverage Metrics**

| Milestone | Week | Python | Non-Python | Total | Coverage % |
|-----------|------|--------|------------|-------|------------|
| Baseline | 0 | 56 | 0 | 56 | 10.6% |
| Phase A complete | 3 | 520 | 0 | 520 | 98% Python |
| Templates added | 4 | 520 | 200 | 720 | 50% overall |
| Configs + migrations | 5 | 520 | 350 | 870 | 60% |
| Tests complete | 6 | 520 | 850 | 1,370 | **95.1%** ✅ |
| AI scores added | 9 | 520 | 850 | 1,370 | 95.1% |
| Semantic search | 11 | 520 | 850 | 1,370 | 95.1% |
| **Launch** | 12 | 520 | 850 | **1,370** | **95.1%** ✅ |

### **Quality Metrics**

| Metric | Target | How Measured |
|--------|--------|--------------|
| DB sync accuracy | 100% | `decorator_hash` matches |
| Collector success rate | 95%+ | % files successfully parsed |
| APM webhook uptime | 99%+ | Webhook receive rate |
| AI score accuracy | 80%+ | Manual spot-check (top 100 components) |
| MCP query latency | <100ms | DB query performance |
| Semantic search relevance | 70%+ | User feedback (top 10 results) |

### **ROI Metrics**

**Investment**: $34,000 (280 hours * $120/hour)

**Annual Returns**:
- Python decorator expansion: $194,000 (from original plan)
- Non-Python coverage: +$50,000 (template/config understanding)
- Runtime intelligence: +$30,000 (faster debugging, perf optimization)
- **Total**: **$274,000/year**

**ROI**: $274k / $34k = **808% in first year** 🎯

---

## 🚀 EXECUTION STRATEGY

### **Parallel Execution**

**Track 1: Decorator Expansion** (existing 20-week plan)
- Weeks 1-20: Decorate 520 Python components
- Team: 2-4 engineers
- Focus: Quality, security review, validation

**Track 2: Intelligence System** (this plan)
- Weeks 1-12: Build intelligence infrastructure
- Team: 2-3 engineers (different team!)
- Focus: Collectors, AI, runtime integration

**Synchronization Points**:
- Week 3: Track 2 syncs Track 1's decorated components to DB
- Week 6: Track 2 has full non-Python coverage (850 components)
- Week 12: Track 2 complete, Track 1 continues to Week 20
- Week 20: Both tracks complete, **1,370+ components with runtime intelligence!**

---

### **Team Coordination**

**Track 1 Team (Decorator Expansion)**:
- Engineer A: Phase 2-3 (security services)
- Engineer B: Phase 4-6 (business logic)
- Engineer C: Phase 7-10 (API, tasks, utilities)

**Track 2 Team (Intelligence System)**:
- Engineer D: Phase A-B (foundation, collectors)
- Engineer E: Phase B (collectors - parallel)
- Engineer F: Phase C (AI classifier, APM integration)

**No overlap! Teams work independently, sync at milestones.**

---

## 🎁 QUICK WINS

### **Week 3 (Phase A Complete)**:
- ✅ 520 decorated components now in PostgreSQL
- ✅ Daily auto-sync working
- ✅ Can query ontology via SQL (much faster than in-memory registry)

### **Week 6 (Phase B Complete)**:
- ✅ 1,370 total components (95%+ coverage!)
- ✅ Templates searchable ("find forms with CSRF issues")
- ✅ Configs searchable ("show all hardcoded secrets")
- ✅ Migrations searchable ("which migrations alter PII tables?")
- ✅ Tests searchable ("find slow integration tests")

### **Week 9 (Phase C Complete)**:
- ✅ AI importance scores (auto-prioritize decorator work)
- ✅ Runtime performance data (identify slow endpoints)
- ✅ Error patterns (identify bug-prone components)
- ✅ CVE alerts (dependency security)

### **Week 12 (Phase D Complete)**:
- ✅ Semantic search ("how does authentication work?" → relevant components)
- ✅ Dashboard v2 (runtime intelligence visualizations)
- ✅ Claude Code has **maximum LLM context** for 95%+ of system!

---

## 📝 MANAGEMENT COMMANDS

```bash
# Sync decorators to DB
python manage.py sync_ontology_to_db [--force] [--dry-run]

# Run all collectors (templates, configs, migrations, tests)
python manage.py collect_all_metadata [--type template|config|migration|test]

# Compute AI importance scores
python manage.py compute_ai_scores [--recompute-all]

# Scan dependencies for CVEs
python manage.py scan_dependency_cves [--requirements-file base.txt]

# Generate vector embeddings
python manage.py generate_embeddings [--batch-size 100]

# Full pipeline (run all)
python manage.py ontology_full_refresh
```

---

## 🚨 RISK MITIGATION

### **Risk 1: Collector Parsing Errors**
- **Likelihood**: HIGH (templates/migrations have edge cases)
- **Impact**: MEDIUM (some files won't be documented)
- **Mitigation**: Robust error handling, log parse failures, skip unparseable files
- **Acceptable**: 95% success rate (5% edge cases can be manual)

### **Risk 2: APM Webhook Unreliability**
- **Likelihood**: MEDIUM (network issues, webhook downtime)
- **Impact**: LOW (runtime data is enhancement, not critical)
- **Mitigation**: Queue webhooks in Redis, retry failed updates, alert on prolonged silence

### **Risk 3: AI Scores Inaccurate**
- **Likelihood**: MEDIUM (heuristics may be wrong)
- **Impact**: MEDIUM (incorrect prioritization)
- **Mitigation**: Manual spot-checks, tune weights based on feedback, allow manual score override

### **Risk 4: DB Performance Degradation**
- **Likelihood**: LOW (proper indexes designed)
- **Impact**: HIGH (slow MCP queries hurt Claude Code UX)
- **Mitigation**: Query limits (max 100 results), proper indexes, EXPLAIN ANALYZE during dev, connection pooling

### **Risk 5: Vector Embedding Costs**
- **Likelihood**: LOW (ada-002 is cheap)
- **Impact**: LOW (budget impact minimal)
- **Mitigation**: Batch embeddings, cache embeddings, only re-embed on content change

---

## ✅ FINAL VERIFICATION

**Design Completeness Check**:

- [x] Database schema covers all requirements (metadata + runtime + AI scores)
- [x] Collectors handle all non-Python file types (templates, configs, migrations, tests)
- [x] AI classifier uses all 4 dimensions (usage, security, complexity, change)
- [x] Runtime intelligence integrates with APM (New Relic, DataDog, Sentry)
- [x] Decorator sync preserves runtime data (doesn't overwrite)
- [x] Enhanced MCP provides maximum LLM context
- [x] Semantic search enables natural language queries
- [x] Timeline is realistic (12 weeks with 2-3 engineers)
- [x] Budget is justified (808% ROI)
- [x] Risks identified and mitigated

**This design is complete and ready for implementation!** ✅

---

## 🎯 DELIVERABLES

**Upon completion (Week 12)**:

1. **Coverage**: 1,370+ components (95%+ of codebase)
   - Python: 520 (decorators)
   - Templates: 200 (parsed)
   - Configs: 50 (parsed)
   - Migrations: 100 (analyzed)
   - Tests: 500 (extracted)

2. **Intelligence**: All components have AI scores + runtime data
   - Importance scores (0-100)
   - Performance baselines (p50/p95/p99)
   - Error patterns (common failures)
   - Usage frequency (calls/day)
   - Dependency health (CVEs)

3. **MCP Integration**: Enhanced queries for Claude Code
   - Query by importance
   - Semantic search
   - Runtime insights
   - Non-Python file queries

4. **ROI**: $274k/year vs $34k investment (808%)