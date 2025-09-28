# Reports

_Preamble: Reporting is comprehensive, with many PDF‑style templates. Learn how to add reports and keep them fast._

## Where Things Live
- Templates: `frontend/templates/reports/pdf_reports/` and domain folders
- Queries: `apps/core/report_queries.py` and domain services
- REST/GraphQL exposure: per domain as needed

## Performance Tips
- Paginate large datasets; consider async generation (queue) if heavy.
- Cache summaries where feasible; avoid rendering megabytes of HTML in a single request.
- Keep inline scripts/styles minimal (CSP), prefer external assets.

## Extending
- Add a new template under `frontend/templates/reports/` with a clear data contract.
- Encapsulate data shaping in a service module; keep views skinny.

## Pipeline Diagram
```mermaid
flowchart LR
  A[Request params] --> B[Service: fetch & shape data]
  B --> C[Jinja/Django template]
  C --> D[HTML/PDF response]
```

## Code Sample
```python
# apps/reports/services.py
def build_workorder_summary(filters) -> dict:
    qs = WorkOrder.objects.filter(**filters).select_related('asset','assignee')
    qs = qs.only('id','status','asset__name','assignee__peoplename')
    stats = qs.values('status').annotate(n=Count('id'))
    return {"rows": list(qs[:500]), "stats": list(stats)}
```

```python
# apps/reports/views.py
def workorder_summary_view(request):
    data = build_workorder_summary(parse_filters(request))
    return render(request, 'reports/pdf_reports/work_order_list.html', data)
```

## Guidance
- Async: move heavy exports to async jobs and notify via email/WS on completion.
- Caching: cache shaped data keyed by filter hash; invalidate on mutations.
- Safety: avoid inline scripts; embed nonces if necessary; keep templates simple.

