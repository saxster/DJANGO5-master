# Local Setup Guide

_Preamble: A concise checklist to get productive locally without surprises._

## Requirements
- Python 3.10+
- PostgreSQL + PostGIS
- Redis (db1 cache, db2 channels)
- GEOS/PROJ libraries (for GIS fields when required by OS)

## Environment
- Active env file is configured in `intelliwiz_config/settings.py` → `ENV_FILE`.
- Provide DB, Redis, media/static paths, email sender, and security flags in `intelliwiz_config/envs/`.

## Run
1. `python manage.py migrate`
2. Create an admin user (via admin or custom script honoring `PeopleManager`)
3. `python manage.py runserver`

## Health & Debug
- Health: `/health`, `/ready`, `/alive`, `/monitoring/health/`
- Static/media (dev): served by Django with WhiteNoise settings

## Optional Services
- Celery worker/beat if turning on background tasks (see `config/celery.py`)

## Sample .env (development)
```
DEBUG=1
SECRET_KEY=dev-secret
DBUSER=postgres
DBPASS=postgres
DBNAME=youtility5
DBHOST=127.0.0.1
MEDIA_ROOT=/tmp/y5_media
STATIC_ROOT=/tmp/y5_static
MQTT_BROKER_ADDRESS=localhost
MQTT_BROKER_PORT=1883
DEFAULT_FROM_EMAIL=dev@example.com
EMAIL_FROM_ADDRESS=dev@example.com
HOST=localhost
```

## Docker Compose (Postgres + Redis)
```yaml
version: '3.8'
services:
  db:
    image: postgis/postgis:13-3.1
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: youtility5
    ports: ["5432:5432"]
  redis:
    image: redis:7
    command: ["redis-server", "--appendonly", "yes"]
    ports: ["6379:6379"]
```

## Admin Creation Snippet
```python
from apps.peoples.models import People
u = People.objects.create_superuser(loginid='admin', password='admin123', peoplename='Admin')
print(u.id)
```

## Service Topologies
- Channels: run ASGI server (Daphne/Uvicorn) with multiple workers; Redis as channel layer.
- Celery: worker + beat if background tasks are enabled by feature flags.

