# Extensibility Patterns

_Preamble: To keep the platform maintainable, use these patterns when adding features. They align with the platform’s security, IA, and observability posture._

## Patterns
- Domain‑first routing: add `apps/core/urls_<domain>.py`, mount in `intelliwiz_config/urls_optimized.py`, provide legacy redirects if needed.
- Services over fat views: put business logic in `services.py`; keep views thin and composable.
- GraphQL optimization: implement `get_queryset()` with `select_related/prefetch_related` and add dataloaders for N+1 edges.
- Multi‑tenancy: subclass `TenantAwareModel`; constrain queries by tenant consistently.
- Security: adopt CSP nonces, sanitize inputs, define PII rules for any stream/event capture.
- Observability: instrument heavy code paths; ensure monitoring endpoints reflect new features.

## New Feature Checklist
- Routing added with domain grouping
- Models tenant‑aware and indexed
- GraphQL resolvers optimized and tested
- REST endpoints permissioned and validated
- Templates CSP‑compatible (prefer external assets)
- Monitoring counters/timers/thresholds identified
- Docs updated in this folder

## Before/After Examples

### Fat View → Service
Before
```python
def create(request):
    # 100s of lines of validation and DB calls
    ...
```
After
```python
def create(request):
    payload = parse(request)
    result = MyService.create(payload)
    return JsonResponse(result)
```

### Raw SQL → ORM + Dataloader
Before
```python
for person in people:
    jobs = Job.objects.filter(people=person)  # N+1
```
After
```python
loaders = get_loaders(info)
jobs = loaders['jobs_by_asset'].load_many(asset_ids)
```

## PR Checklist
- Naming: modules, classes, and functions follow existing conventions.
- Tests: unit + integration; no N+1 regressions.
- Security: CSP compliant, no raw SQL; inputs validated.
- Observability: metrics and logging added for critical paths.
- Docs: chapter updated with flows/samples if relevant.

## Anti‑Patterns
- Copy‑pasting business logic across views; prefer shared services.
- Inline scripts/styles without nonces; avoid unsafe CSP.
- Unbounded queries and large payloads without pagination.

