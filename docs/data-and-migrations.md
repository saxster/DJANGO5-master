# Data & Migrations

_Preamble: Database configuration is environment‑driven, with PostGIS and Redis integrations. This chapter covers local setup and safe migrations._

## Databases
- Configured via env in `intelliwiz_config/settings.py`.
- Postgres/PostGIS driver: `django.contrib.gis.db.backends.postgis`.
- Sessions: PostgreSQL session engine with index guidance and cleanup settings.

## Redis
- Cache: Redis db 1 (default cache)
- Channels: Redis db 2 (websockets)

## Migrations
- Apps manage their own `migrations/` folders.
- Typical flow: `makemigrations` → `migrate`; ensure tenant‑aware constraints where needed.
- For Postgres optimizations and phased rollout, see `postgresql_migration/` guidance and tests.

## Tenant‑Aware Migration Recipes
- Adding a FK to `Tenant` with backfill:
```python
def forwards(apps, schema_editor):
    Model = apps.get_model('myapp','Model')
    Tenant = apps.get_model('tenants','Tenant')
    default_tenant = Tenant.objects.first()
    Model.objects.filter(tenant__isnull=True).update(tenant=default_tenant)
```
- Enforce non‑null after backfill via a follow‑up migration.

## PostGIS Tips
- Set SRID explicitly for `PointField`/`PolygonField` (e.g., 4326) to avoid surprises.
- Add GIST indexes for spatial queries; consider BRIN for large append‑only tables.

## Zero‑Downtime Patterns
- Prefer additive changes: add new columns, backfill in batches, then switch code paths.
- Use feature flags to gate behavior; avoid dropping old columns until adoption complete.
- For heavy backfills, schedule during low traffic; commit in chunks.

