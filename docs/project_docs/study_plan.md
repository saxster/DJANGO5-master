# YOUTILITY5 — Comprehensive Interview Study Plan

This plan is tailored to the YOUTILITY5 repository and prioritizes the exact frameworks, patterns, and integrations present here. Use it as a week-by-week tracker with concrete “Read/Do/Check” tasks and interview prompts.

---

## 1) Project Snapshot (What’s In Use)

- Django monolith with multiple apps and custom user model
- PostgreSQL + PostGIS (GeoDjango)
- Django REST Framework + drf-spectacular (OpenAPI)
- GraphQL with Graphene + graphql-jwt
- WebSockets with Django Channels
- Celery + django-celery-beat/results + Redis
- Redis caching + custom caching strategies
- Multi-tenancy via DB router and thread-local
- Security hardening (CSP, custom SQLi/XSS middlewares, API keys)
- PDF generation with WeasyPrint
- MQTT integrations
- Templates: Django Templates + Jinja2 hybrid
- Testing: pytest + pytest-django + channels testing
- Monitoring/observability scaffolding

Key entry points to skim first:
- `intelliwiz_config/settings.py`
- `apps/core/` (cache, queries, middlewares, consumers)
- `apps/service/` (DRF + GraphQL schemas, serializers)
- `apps/api/` (docs config, routing)
- `background_tasks/tasks.py`, `config/celery.py`
- `apps/mqtt/` (client + tests)
- `apps/reports/` (WeasyPrint)
- `apps/tenants/` (middleware, models)
- `tests/` (integration, channels, IA/performance benchmarks)

---

## 2) Skills Matrix

### Master (Core Depth)
- Python 3.10+: typing, async/await, context managers, logging
- Django fundamentals: models, signals, middleware, auth, admin, static/media, email
- PostgreSQL + ORM: QuerySets, annotations, select_related/prefetch_related, transactions
- DRF: serializers, viewsets, routers, auth, pagination/filtering; OpenAPI docs
- Celery: retries, scheduling, results, routing/queues
- Redis + Caching: keying, TTLs, invalidation, per-view vs low-level
- Security: sessions/CSRF, cookies, CSP, rate limiting, API keys
- Testing: pytest-django fixtures, DB tests, channels tests
- Deployment basics: Gunicorn, static assets, WhiteNoise, env-based settings

### Refresh (Active in Repo)
- GraphQL (Graphene): schema/mutations, auth, N+1 avoidance, complexity control
- Django Channels: consumers, channel layers, auth, backpressure
- Multi-tenancy: DB routers, thread-local, tenant-aware models
- GeoDjango + PostGIS: spatial fields, queries, indexes
- WeasyPrint: font handling, memory/perf, async/offload via Celery
- Jinja2 + Django templates hybrid: context processors, tags/filters, security
- MQTT: client lifecycle, topic/QoS design, idempotency, Celery offload
- Caching/performance: cache-aside, invalidation strategies, query optimization
- Logging/Monitoring: correlation IDs, handlers, metrics

### Learn/New (Advanced/Adjacent)
- Advanced Postgres: JSONB, GIN/GIST, partial indexes, materialized views, query plans
- Async architecture choices: Channels vs Celery vs DB queues; idempotent workers; backpressure
- API observability: schema evolution, client SDKs, contract testing
- Security depth: OAuth2/OIDC, key rotation, webhook signing, DRF throttling strategies
- CI/CD: coverage gates, flaky tests, container scanning, secrets management
- Real-time UX: reconnection, offline queues, event modeling for mobile
- Data pipelines: long-running tasks, resumability, artifact lifecycle

---

## 3) Week-by-Week Tracker

Each week includes Read → Do → Checklist → Interview Prompts. Keep notes on gotchas and drafts for answers.

### Week 1 — Django + DRF + Celery/Redis (Core)

Read
- Settings and core stack (apps, middleware, caches, celery, auth)
- DRF serializers + read-only viewsets
- Celery tasks and scheduling config
- Cache manager + strategies

Do
- Add a DRF endpoint that serves cached data with explicit invalidation; measure queries before/after
- Write a Celery task with retry/backoff and idempotency (e.g., dedupe key)
- Tests: 2 serializer unit tests + 1 view test (pytest-django)

Checklist
- [ ] Explain INSTALLED_APPS and MIDDLEWARE choices and side effects
- [ ] Show a ModelSerializer + ViewSet + Router end-to-end
- [ ] Implement Celery retries/idempotency; justify queue/route choice
- [ ] Design cache keys + TTL and invalidation strategy for a list endpoint

Interview Prompts
- Preventing N+1 in DRF responses and queryset tuning
- Offloading criteria: inline vs Celery; timeouts and retries
- Cache invalidation strategies used and why

### Week 2 — GraphQL, Channels (WebSockets), Multi‑Tenancy

Read
- GraphQL schema/mutations and JWT integration
- Channels consumers + routing, channel layers, auth
- Tenant DB router + thread‑local context; tenant-aware models

Do
- Implement a GraphQL mutation with validation and auth; reduce N+1 via select_related/prefetch
- Build a Channels consumer that broadcasts a simple event; add an integration test (WebsocketCommunicator)
- Add a tenant-aware queryset filter that demonstrates isolation via thread-local DB selection

Checklist
- [ ] Mutation with robust validation + error handling
- [ ] Demonstrate Channels lifecycle and authenticated connections
- [ ] Explain tenant routing end-to-end and isolation risks

Interview Prompts
- Tradeoffs of REST vs GraphQL in this codebase
- Handling backpressure and fan‑out in Channels
- Ensuring tenant isolation, testing cross-tenant data leaks

### Week 3 — PostgreSQL/PostGIS Performance + Caching

Read
- DB + PostGIS configuration and usage
- Query layers and raw SQL entry points
- Materialized view cache (Select2) and refresh strategy

Do
- Pick one heavy queryset; run EXPLAIN ANALYZE; optimize (index/related fetches); document before/after
- Create a materialized view and a scheduled refresh demo aligned with Select2 cache behavior
- Implement cache‑aside on a GeoDjango queryset; explain invalidation

Checklist
- [ ] Optimize one query and capture query plan improvement
- [ ] Explain GIN vs GIST and when to use each
- [ ] Safe invalidation flow for filtered lists (avoid stale, avoid thundering herd)

Interview Prompts
- Diagnosing slow queries in production; sampling/logging
- When and why to use raw SQL in this repo

### Week 4 — Security, Docs, PDF, Testing

Read
- Security middlewares (SQLi/XSS), headers (CSP, cookies), rate limiting
- API documentation wiring (drf-spectacular) and DRF config
- WeasyPrint usage for reports
- Channels testing and integration test patterns

Do
- Add a hardened API endpoint (strict permissions + throttling), documented in OpenAPI; verify interactive docs
- Add/adjust CSP to block unsafe inline; verify via a controlled violation report path
- Generate a PDF with custom fonts and big pages; observe memory/time; offload when needed

Checklist
- [ ] Explain SQLi/XSS defenses and where they hook into request lifecycle
- [ ] Produce OpenAPI doc for a new endpoint; demonstrate schema references/examples
- [ ] WeasyPrint PDF generation with external assets; performance considerations
- [ ] Write 3 tests covering auth failure, permission denial, and success

Interview Prompts
- Structuring security logging and alerting; correlating incidents
- JWT refresh/rotation considerations in GraphQL and REST

### Ongoing — Observability, MQTT, System Design

Read
- Performance monitoring and instrumentation scaffolding
- MQTT client flow; Celery offload for processing mutations

Do
- Add correlation IDs across request → Celery task → WebSocket broadcast; show trace in logs
- Extend MQTT client with a new topic and confirm idempotent handling

Checklist
- [ ] Correlate logs across subsystems; demonstrate traceability
- [ ] Explain MQTT QoS selection and duplicate suppression strategy

Interview Prompts
- Event-driven vs request‑response design here; when to use each
- How to split the monolith safely (domain boundaries, DB, events)

---

## 4) Must‑Read Code Map

- Settings and stack: `intelliwiz_config/settings.py`
- Celery + tasks: `background_tasks/tasks.py`, `config/celery.py`
- DRF + OpenAPI: `apps/service/serializers.py`, `apps/service/rest_service/views.py`, `apps/api/docs/spectacular_settings.py`
- GraphQL: `apps/service/schema.py`, `apps/api/graphql/enhanced_schema.py`
- Channels: `apps/api/mobile_consumers.py`, `apps/api/mobile_routing.py`, `apps/core/consumers.py`
- Caching/Performance: `apps/core/cache_manager.py`, `apps/core/cache_strategies.py`, `apps/core/queries.py`
- Multi‑tenancy: `apps/tenants/middlewares.py`, `apps/tenants/models.py`
- Security: `apps/core/sql_security.py`, `apps/core/xss_protection.py`, `apps/core/middleware/api_authentication.py`
- PDF: `apps/reports/utils.py`, `apps/reports/views.py`
- Tests (patterns): `tests/integration/test_realtime_monitoring.py`, `tests/test_ia_performance_benchmarks.py`

---

## 5) Definition of Done (Interview‑Ready)

- [ ] Explain the full request path for REST and GraphQL, including auth and caching
- [ ] Implement a Celery task with retries, idempotency, and monitoring
- [ ] Optimize at least one slow query and justify indexing choices
- [ ] Build and test a Channels consumer; explain channel layers and backpressure
- [ ] Describe tenant routing and isolation boundaries; show a tenant-aware query pattern
- [ ] Articulate XSS/SQLi mitigations present and how to extend them
- [ ] Produce and serve OpenAPI docs with drf-spectacular for a new endpoint
- [ ] 8–10 targeted tests across serializers, views, channels, and tasks with good fixtures

---

## 6) Daily/Weekly Rhythm

- Daily (45–60 min)
  - Read 1–2 focused files; write notes (what, why, pitfalls)
  - Implement 1 micro-task (≤30 min) aligned to the week’s goals
- Weekly (3–5 hrs)
  - Complete “Do” tasks and the checklist
  - Capture interview answers for the prompt list; practice out loud

---

## 7) Resources (Shortlist)

- Django/DRF docs; DRF ViewSets/Serializers/Permissions
- Graphene/GraphQL docs; graphql-jwt usage and best practices
- Django Channels docs; channels testing with `WebsocketCommunicator`
- Celery docs (retry, ETA, chords) + django-celery-beat
- Redis + django-redis; cache-aside pattern articles
- Postgres: EXPLAIN ANALYZE, indexing, materialized views; PostGIS gist/gIN
- WeasyPrint docs; font loading and memory tips
- drf-spectacular docs; schema customizations and examples

---

## 8) Appendix — Suggested Exercise Ideas

1) Cached list endpoint with per-tenant cache keys; invalidation on create/update
2) Bulk mutation (GraphQL) with validation; return partial success reports
3) WebSocket dashboard that streams an aggregate metric; cache results; back-off under load
4) Long-running PDF batch generation with resumability via Celery and artifacts cleanup
5) Add a new spatial query (e.g., points-in-polygon) and benchmark with/without GIST
6) Add request → task → WebSocket correlation IDs and a Kibana-style search query proposal

---

Happy studying. Iterate weekly, capture learnings, and rehearse concise answers. When in doubt, tie explanations back to concrete code in this repo.