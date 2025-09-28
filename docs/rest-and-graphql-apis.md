# REST & GraphQL APIs

_Preamble: Two API layers—REST for focused endpoints and GraphQL for rich mobile‑friendly graphs. Learn when to use which, how to add endpoints, and how to keep them fast._

## REST (DRF)
- Base location: `apps/service/rest_service/`
- Mounted at: `/api/v1/` (see `intelliwiz_config/urls_optimized.py`)
- Use DRF permissions/serializers; put business logic in services.

## GraphQL
- Root schema: `apps/service/schema.py` (aggregates domain queries/mutations; includes Journal/Wellness GraphQL)
- Enhanced schema: `apps/api/graphql/enhanced_schema.py`
  - Optimized `DjangoObjectType` with `get_queryset()` prefetches
  - Types for People, Groups, Assets, Jobs, Jobneeds
- Dataloaders: `apps/api/graphql/dataloaders.py` (ids, relation maps, counts)
- Auth: GraphQL JWT (`GRAPHENE`, `GRAPHQL_JWT`) and `@login_required` resolvers

## Patterns
- REST: thin views, rich services, validated serializers
- GraphQL: always batch via dataloaders; avoid N+1 in resolvers; add indexes for heavy filters

## Tests
- See `tests/api/integration/test_graphql.py` for dataloader and resolver tests.

## GraphQL Pagination & Filtering
- Prefer Relay‑style pagination with `DjangoFilterConnectionField`.
- Provide filterable fields in `Meta.filter_fields` (exact, icontains, lte/gte, etc.).
- For large lists, require filters and enforce reasonable defaults on `limit`.

## GraphQL Error Handling
- Validation errors: return typed errors in mutation payloads (`errors: [String]`) and `success: Boolean`.
- Auth errors: rely on `@login_required` to short‑circuit unauthenticated access.
- Server errors: log with correlation IDs; avoid leaking internals in GraphQL error messages.

## Dataloader Caching & Invalidation
- Scope dataloader cache to a single request (`get_loaders(info)` creates a per‑request registry).
- Clear entries after mutations that update referenced objects (e.g., `loaders['people_by_id'].clear(id)`).
- Use `max_batch_size` to avoid huge SQL `IN (...)` lists.

## N+1 Detection & Performance Tests
- Wrap GraphQL calls with a query counter (see tests) to assert query ceilings.
- Add selective `select_related`/`prefetch_related` in `get_queryset()`.
- Track p95 execution time regressions in CI.

## REST Versioning & OpenAPI
- Version REST paths under `/api/v1/` and plan for `/api/v2/` when breaking changes are required.
- Document REST using drf‑spectacular (see `apps/api/docs/spectacular_settings.py`), exposing `/api/schema/` and Swagger/Redoc UIs if enabled.
- Schema evolution: prefer additive changes; deprecate fields with a window before removal.

## GraphQL DataLoader Example

```python
# apps/api/graphql/dataloaders.py
class TicketsByUserLoader(DataLoader, BatchLoadMixin):
    def batch_load_fn(self, user_ids):
        user_ids = [int(i) for i in user_ids]
        from apps.y_helpdesk.models import Ticket
        tickets_by_user = defaultdict(list)
        for t in Ticket.objects.filter(requester_id__in=user_ids).only("id","requester_id","status"):
            tickets_by_user[t.requester_id].append(t)
        return Promise.resolve([tickets_by_user.get(uid, []) for uid in user_ids])

def get_loaders(info):
    # ...existing loaders
    return {
        **existing,
        'tickets_by_user': registry.get_loader(TicketsByUserLoader),
    }
```

```python
# apps/api/graphql/enhanced_schema.py
class PeopleType(OptimizedDjangoObjectType):
    tickets = graphene.List(lambda: TicketType)

    def resolve_tickets(self, info):
        loaders = get_loaders(info)
        return loaders['tickets_by_user'].load(self.id)
```

## REST Serializer/ViewSet Example

```python
# apps/service/rest_service/serializers.py
from rest_framework import serializers
from apps.activity.models.asset_model import Asset

class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ("id","name","location","is_active")
```

```python
# apps/service/rest_service/views.py
from rest_framework import viewsets, permissions
from .serializers import AssetSerializer
from apps.activity.models.asset_model import Asset

class AssetViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Asset.objects.select_related('location').all()
    serializer_class = AssetSerializer
    permission_classes = [permissions.IsAuthenticated]
```

```python
# apps/service/rest_service/urls.py
from rest_framework.routers import DefaultRouter
from .views import AssetViewSet

router = DefaultRouter()
router.register(r'assets', AssetViewSet, basename='asset')

urlpatterns = router.urls
```
