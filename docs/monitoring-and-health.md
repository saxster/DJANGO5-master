# Monitoring & Health

_Preamble: Beyond health checks, the system detects slow queries, regressions, and N+1. Learn endpoints and middleware that keep performance in check._

## Endpoints
- `monitoring/urls.py`
  - Health: `/monitoring/health/`, plus `/health`, `/ready`, `/alive`
  - Metrics: `/monitoring/metrics/` (Prometheus variant available)
  - Performance: `/monitoring/performance/queries/`, `/monitoring/performance/cache/`
  - Alerts & dashboard JSON feeds

## Enhanced Monitor
- Module: `monitoring/performance_monitor_enhanced.py`
  - Slow queries with suggestions, regression checks vs baselines, N+1 detection, resource monitoring

## Extending
- Emit counters/timers around heavy code paths.
- Adjust thresholds via settings (e.g., `SLOW_QUERY_THRESHOLD`, `REGRESSION_THRESHOLD`).

## Architecture (Performance Capture)
```mermaid
flowchart TB
    A[Request/WS Message] --> B[Timing hooks + query capture]
    B --> C[N+1 Detector]
    B --> D[Slow Query Analyzer]
    C --> E[PerformanceMonitor (baselines)]
    D --> E
    E --> F[Alerts/Email/Webhooks]
    E --> G[/metrics endpoint]
```

## PromQL Examples
- p95 response time per route
```
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{route!=""}[5m])) by (le, route))
```
- Error rate (5m)
```
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
```

## Adding Custom Metrics
```python
import time
from monitoring.performance_monitor_enhanced import monitor

def expensive_view(request):
    t0 = time.time()
    try:
        # ... work ...
        return JsonResponse({"ok": True})
    finally:
        monitor.record_metric("view_ms", (time.time()-t0)*1000, tags={"path": request.path})
```

## Runbooks
- Slow queries
  - Inspect recent slow query logs; check for missing indexes and N+1.
  - Add `select_related/prefetch_related`; create targeted indexes; limit columns.
- Elevated error rate
  - Check recent deploys; fetch stack traces; correlate with traffic spikes.
  - Rollback or hotfix; add test coverage for the scenario.
- Memory pressure
  - Investigate large query sets/materialized responses; cap pagination; watch caches.

