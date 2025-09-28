# Common Developer Tasks

_Quick, copy‑paste friendly steps for common tasks. Each task links to deeper chapters._

## Add a GraphQL Field/Resolver
- Create/extend a `DjangoObjectType` in `apps/api/graphql/enhanced_schema.py`.
- Optimize with `get_queryset()` using `select_related/prefetch_related`.
- Batch joins via a DataLoader (see “REST & GraphQL APIs”).

Example
```python
class JobType(OptimizedDjangoObjectType):
    asset_name = graphene.String()
    class Meta: model = Job; fields = '__all__'
    def resolve_asset_name(self, info):
        return self.asset.name if self.asset_id else None
```

## Add a REST Endpoint
- Serializer in `apps/service/rest_service/serializers.py`
- ViewSet in `apps/service/rest_service/views.py`
- Register in `apps/service/rest_service/urls.py` (router)
- Mounted under `/api/v1/` (see `urls_optimized.py`)

## Add a WebSocket Consumer
- Route in `apps/api/mobile_routing.py` or dedicated module
- Consumer in `apps/.../consumers.py`; use `@database_sync_to_async` for DB
- Define message contract and error codes; log correlation IDs
- Test connect/receive/heartbeat flows

## Add a Tenant‑Aware Model
- Subclass `TenantAwareModel` from `apps/tenants/models.py`
- Add indexes for common filters
- Filter by tenant in views/queries; test isolation

Example
```python
class Example(TenantAwareModel):
    name = models.CharField(max_length=120)
    class Meta:
        indexes = [models.Index(fields=['tenant','name'])]
```

## Add a Domain Route (IA)
- Create `apps/core/urls_<domain>.py` and add patterns
- Mount in `intelliwiz_config/urls_optimized.py`
- Provide legacy redirects if needed (`ENABLE_LEGACY_URLS`)

## Add Monitoring/Metrics
- For HTTP: instrument views with timings; expose via `/monitoring/metrics/`
- For DB: watch slow queries (`monitoring/performance_monitor_enhanced.py`)
- For WS: log processing time and event counts per message type

## Add Dataloader & Invalidation
- Implement loader in `apps/api/graphql/dataloaders.py`
- Use in resolvers via `get_loaders(info)`
- After mutations, clear cache entries

```python
loaders = get_loaders(info)
loaders['people_by_id'].clear(person.id)
```

## Write Tests
- GraphQL: use fixtures and query counters; assert no N+1
- REST: test serializers, permissions, and viewsets
- WS: test consumer connect, message handling, and heartbeats

## Add a Report
- Template under `frontend/templates/reports/`
- Service to shape data; avoid heavy logic in templates
- Consider async generation for large datasets

Links
- Real‑Time & Mobile Sync: `real-time-and-mobile-sync.md`
- REST & GraphQL APIs: `rest-and-graphql-apis.md`
- Security & Compliance: `security-and-compliance.md`
- Extensibility Patterns: `extensibility-patterns.md`
- Core & IA: `core-and-information-architecture.md`
