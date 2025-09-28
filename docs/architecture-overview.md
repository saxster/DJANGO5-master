# Architecture Overview

_Preamble: This chapter orients you to the system’s shape—how settings, apps, URLs, security, and runtime concerns come together. You’ll learn the request flow, where features live, and where to plug in new modules the “platform way.”_

## Overview
- Project config: `intelliwiz_config/`
  - Settings and env: `intelliwiz_config/settings.py` (+ IA overlay in `intelliwiz_config/settings_ia.py`)
  - Domain URLs: `intelliwiz_config/urls_optimized.py` (keeps legacy URLs behind a flag)
  - ASGI/WSGI: `intelliwiz_config/asgi.py`, `intelliwiz_config/wsgi.py`
- Domain apps under `apps/`: people, attendance, activity, reports, work orders, helpdesk, MQTT, journal, wellness, streamlab, issue_tracker, onboarding (+ onboarding_api)
- Real‑time: Channels + Redis (see `CHANNEL_LAYERS` in `intelliwiz_config/settings.py`)
- Templates: Django + Jinja2 under `frontend/templates/`

## Request Flow
1. HTTP routes are defined in `intelliwiz_config/urls_optimized.py`
2. Views are mapped to domain apps or consolidated core URL groups in `apps/core/urls_*.py`
3. Security middleware wraps requests early (CSP, XSS, SQLi) from `apps/core/...`
4. Optional GraphQL (`/graphql`) via `apps/service/schema.py` and `apps/api/graphql/enhanced_schema.py`
5. WebSocket connections routed by `intelliwiz_config/asgi.py` and `apps/api/mobile_routing.py`

## Domain‑Driven IA
- Core groupings:
  - People: `apps/core/urls_people.py` (aggregates People + Attendance)
  - Operations: `apps/core/urls_operations.py`
  - Assets: `apps/core/urls_assets.py`
  - Helpdesk: `apps/core/urls_helpdesk.py`
  - Reports: `apps/reports/`
- Keep legacy routes enabled during migration using `ENABLE_LEGACY_URLS` in settings.

## Runtime Services
- PostgreSQL/PostGIS: ORM and GIS fields.
- Redis: default cache and Channels layer (db1 = cache, db2 = websockets).
- Celery (optional): config in `config/celery.py`; some features use a Postgres task queue pattern.

## Extending
- Add new domain URLs in `apps/core/urls_<domain>.py` and mount them in `intelliwiz_config/urls_optimized.py`.
- Prefer `TenantAwareModel` for multi‑tenant data models (`apps/tenants/models.py`).
- Reuse security middleware and utilities from `apps/core`.

## Component Diagram
```mermaid
flowchart LR
  subgraph Client
    B[Browser/Web]
    M[Mobile SDK]
  end
  B -->|HTTP/REST/GraphQL| S[Django (ASGI/WSGI)]
  M -->|WebSocket| S
  S -->|ORM| P[(PostgreSQL/PostGIS)]
  S -->|Cache/Channels| R[(Redis)]
  S -->|Templates| T[Frontend Templates]
  S -->|Monitoring| Mon[Monitoring Endpoints]
```

## “Where to Put What”
- Domain routes: `intelliwiz_config/urls_optimized.py`, `apps/core/urls_*.py`
- Views & services: `apps/<domain>/views.py`, `apps/<domain>/services.py`
- Models & migrations: `apps/<domain>/models/`, `apps/<domain>/migrations/`
- REST: `apps/service/rest_service/` (serializers, views, urls)
- GraphQL: `apps/service/schema.py`, `apps/api/graphql/*`
- WebSockets: `intelliwiz_config/asgi.py`, `apps/api/mobile_routing.py`, consumers under app `consumers.py`
- Security & middleware: `apps/core/middleware/*`
- Monitoring: `monitoring/` and `/monitoring/*` endpoints
