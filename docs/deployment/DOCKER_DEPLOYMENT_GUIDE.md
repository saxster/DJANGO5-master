# Docker Deployment Guide for IntelliWiz

Complete guide for deploying the IntelliWiz enterprise facility management platform using Docker and Docker Compose.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Development Environment](#development-environment)
- [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [Backup & Restore](#backup--restore)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Overview

### Architecture

The Docker deployment consists of **13 containers** orchestrated by Docker Compose:

**Infrastructure Layer:**
1. **postgres** - PostgreSQL 14.2 with PostGIS
2. **redis** - Redis 7.x (cache & message broker)

**Application Layer:**
3. **web** - Django application (Gunicorn)
4. **daphne** - ASGI server for WebSockets

**Background Processing (8 specialized Celery workers):**
5. **celery-default** - Default queue (concurrency: 4)
6. **celery-email** - Email tasks (concurrency: 2)
7. **celery-reports** - Report generation (concurrency: 2)
8. **celery-onboarding** - Onboarding tasks (concurrency: 2)
9. **celery-ml** - ML/AI processing (concurrency: 2, 4 CPU cores)
10. **celery-priority** - High-priority tasks (concurrency: 4)
11. **celery-scheduled** - Scheduled tasks (concurrency: 2)
12. **celery-gcs** - GCS file operations (concurrency: 2)
13. **celery-beat** - Periodic task scheduler (1 instance only)

**Supporting Services:**
14. **flower** - Celery monitoring dashboard
15. **nginx** - Reverse proxy & static file server
16. **postgres-backup** - Automated daily backups

### Benefits

✅ **Portability** - Deploy anywhere (on-prem, cloud, hybrid)
✅ **Consistency** - Identical dev/staging/production environments
✅ **Isolation** - Resource limits, network isolation, security
✅ **Scalability** - Scale individual services independently
✅ **Fast rollback** - Version-tagged images, instant rollback
✅ **Developer productivity** - 30-minute setup vs 4+ hours manual

---

## Prerequisites

### System Requirements

**Minimum (Development):**
- CPU: 4 cores
- RAM: 8 GB
- Disk: 50 GB free space
- Docker Engine: 24.0+
- Docker Compose: 2.20+

**Recommended (Production):**
- CPU: 8+ cores
- RAM: 16+ GB
- Disk: 200+ GB SSD
- Docker Engine: 24.0+
- Docker Compose: 2.20+

### Software Installation

**Ubuntu/Debian:**
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

**macOS:**
```bash
# Install Docker Desktop
brew install --cask docker

# Start Docker Desktop application
open /Applications/Docker.app

# Verify installation
docker --version
docker compose version
```

---

## Quick Start

### Development Environment (5 minutes)

```bash
# 1. Clone repository
git clone <repository-url>
cd DJANGO5-master

# 2. Copy environment file
cp .env.dev .env

# 3. Build and start containers
docker-compose -f docker-compose.dev.yml up --build

# 4. Access the application
# Django: http://localhost:8000
# Flower: http://localhost:5555 (admin/admin)
# PostgreSQL: localhost:5432
# Redis: localhost:6379
```

**First-time setup:**
```bash
# Create superuser
docker-compose -f docker-compose.dev.yml exec web python manage.py createsuperuser

# Initialize database (if needed)
docker-compose -f docker-compose.dev.yml exec web python manage.py init_intelliwiz default
```

---

## Development Environment

### Daily Workflow

```bash
# Start all services
docker-compose -f docker-compose.dev.yml up

# Start in background
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f
docker-compose -f docker-compose.dev.yml logs -f web  # specific service

# Stop services
docker-compose -f docker-compose.dev.yml down

# Restart a service
docker-compose -f docker-compose.dev.yml restart web
```

### Hot Reload

Code changes automatically reload in development:
- **Django**: runserver auto-reloads on file changes
- **Celery**: restart worker manually: `docker-compose -f docker-compose.dev.yml restart celery-worker`
- **Static files**: served by Django (no collectstatic needed)

### Running Commands

```bash
# Django management commands
docker-compose -f docker-compose.dev.yml exec web python manage.py migrate
docker-compose -f docker-compose.dev.yml exec web python manage.py makemigrations
docker-compose -f docker-compose.dev.yml exec web python manage.py shell

# Celery commands
docker-compose -f docker-compose.dev.yml exec celery-worker celery -A intelliwiz_config inspect active

# Database access
docker-compose -f docker-compose.dev.yml exec postgres psql -U postgres -d intelliwiz_dev

# Redis access
docker-compose -f docker-compose.dev.yml exec redis redis-cli
```

### Running Tests

```bash
# Run all tests
docker-compose -f docker-compose.dev.yml exec web python -m pytest

# Run specific test
docker-compose -f docker-compose.dev.yml exec web python -m pytest apps/attendance/tests/

# With coverage
docker-compose -f docker-compose.dev.yml exec web python -m pytest --cov=apps --cov-report=html
```

### Debugging

**Using pdb/ipdb:**
```bash
# Start with attached terminal
docker-compose -f docker-compose.dev.yml up

# In code, add:
import ipdb; ipdb.set_trace()

# Debugger will activate in the terminal
```

**Access database directly:**
```bash
# Using pgAdmin or DBeaver
Host: localhost
Port: 5432
Database: intelliwiz_dev
Username: postgres
Password: postgres
```

---

## Production Deployment

### Initial Setup

**1. Prepare Environment:**
```bash
# On production server
cd /opt
git clone <repository-url> intelliwiz
cd intelliwiz

# Copy and configure environment
cp .env.template .env.prod
nano .env.prod  # Edit with production values
```

**2. Configure Environment Variables:**

Edit `.env.prod` with production values:
```bash
# Critical settings
SECRET_KEY=<generate-50-char-random-string>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DB_NAME=intelliwiz_prod
DB_USER=intelliwiz_user
DB_PASSWORD=<strong-secure-password>

# Redis
REDIS_PASSWORD=<redis-password>

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=<your-email>
EMAIL_HOST_PASSWORD=<app-password>
```

**3. Build Images:**
```bash
docker-compose -f docker-compose.prod.yml build --no-cache
```

**4. Start Infrastructure:**
```bash
# Start database and redis first
docker-compose -f docker-compose.prod.yml up -d postgres redis

# Wait for health checks
docker-compose -f docker-compose.prod.yml ps

# Start remaining services
docker-compose -f docker-compose.prod.yml up -d
```

**5. Initialize Database:**
```bash
# Run migrations
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate

# Collect static files
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --no-input

# Create superuser
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# Initialize system (if needed)
docker-compose -f docker-compose.prod.yml exec web python manage.py init_intelliwiz default
```

**6. Verify Deployment:**
```bash
# Check all containers are healthy
docker-compose -f docker-compose.prod.yml ps

# Test health endpoints
curl http://localhost/health/
curl http://localhost/readiness/

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### SSL/HTTPS Configuration

**Option 1: Let's Encrypt (Recommended)**

```bash
# Install certbot
sudo apt-get install certbot

# Generate certificate
sudo certbot certonly --standalone -d yourdomain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/key.pem

# Update nginx config (uncomment SSL lines in nginx/conf.d/intelliwiz.conf)
# Restart nginx
docker-compose -f docker-compose.prod.yml restart nginx

# Auto-renewal (add to crontab)
0 0 1 * * certbot renew --quiet && docker-compose -f /opt/intelliwiz/docker-compose.prod.yml restart nginx
```

**Option 2: Self-Signed (Development/Testing)**

```bash
cd nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout key.pem -out cert.pem \
    -subj "/C=US/ST=State/L=City/O=Org/CN=localhost"
```

### Updates & Deployments

**Standard Update:**
```bash
# Pull latest code
cd /opt/intelliwiz
git pull

# Rebuild images
docker-compose -f docker-compose.prod.yml build

# Restart services
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
```

**Zero-Downtime Deployment:**
```bash
# Start new instances
docker-compose -f docker-compose.prod.yml up -d --scale web=2 --no-recreate

# Wait for new instance health check
sleep 30

# Remove old instance
docker-compose -f docker-compose.prod.yml up -d --scale web=1

# Verify
docker-compose -f docker-compose.prod.yml ps
```

### Rollback

```bash
# Tag current version before deployment
docker tag intelliwiz:latest intelliwiz:v1.2.3

# If deployment fails, rollback
docker-compose -f docker-compose.prod.yml down
docker tag intelliwiz:v1.2.2 intelliwiz:latest
docker-compose -f docker-compose.prod.yml up -d
```

---

## Configuration

### Resource Limits

Edit `docker-compose.prod.yml` to adjust resource limits:

```yaml
services:
  web:
    deploy:
      resources:
        limits:
          cpus: '2.0'      # Max 2 CPU cores
          memory: 2G       # Max 2GB RAM
        reservations:
          cpus: '0.5'      # Guaranteed 0.5 cores
          memory: 512M     # Guaranteed 512MB
```

### Scaling Services

```bash
# Scale web instances
docker-compose -f docker-compose.prod.yml up -d --scale web=3

# Scale Celery workers
docker-compose -f docker-compose.prod.yml up -d --scale celery-default=4
```

### Network Configuration

Networks are pre-configured in `docker-compose.prod.yml`:
- **frontend**: Nginx, web, daphne, flower (accessible from outside)
- **backend**: Postgres, Redis, Celery workers (internal only)

---

## Backup & Restore

### Automated Backups

```bash
# Manual backup
./scripts/docker-backup.sh

# Schedule daily backups (crontab)
0 2 * * * cd /opt/intelliwiz && ./scripts/docker-backup.sh >> /var/log/intelliwiz-backup.log 2>&1
```

Backups are stored in:
- `backups/postgres/` - Database dumps
- `backups/media/` - Media files
- `backups/volumes/` - Docker volumes

### Restore from Backup

```bash
# Interactive restore
./scripts/docker-restore.sh

# Command-line restore
./scripts/docker-restore.sh --database backups/postgres/backup_20250104_120000.sql.gz
./scripts/docker-restore.sh --media backups/media/media_20250104_120000.tar.gz
```

---

## Monitoring

### Health Checks

```bash
# Application health
curl http://localhost/health/

# Readiness (for load balancers)
curl http://localhost/readiness/

# Liveness (for container orchestration)
curl http://localhost/liveness/
```

### Container Monitoring

```bash
# View resource usage
docker stats

# View logs
docker-compose -f docker-compose.prod.yml logs -f --tail=100

# Specific service
docker-compose -f docker-compose.prod.yml logs -f web
```

### Celery Monitoring

Access Flower dashboard:
- URL: http://your-domain/flower/
- Default credentials: admin/admin (change in .env.prod)

---

## Troubleshooting

See [DOCKER_TROUBLESHOOTING.md](DOCKER_TROUBLESHOOTING.md) for detailed troubleshooting guide.

**Quick fixes:**

```bash
# Container won't start
docker-compose -f docker-compose.prod.yml logs <service-name>

# Database connection errors
docker-compose -f docker-compose.prod.yml exec postgres pg_isready

# Clear and rebuild
docker-compose -f docker-compose.prod.yml down -v
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d

# Reset everything (DESTRUCTIVE)
docker-compose -f docker-compose.prod.yml down -v --remove-orphans
docker volume prune -f
docker system prune -af
```

---

## Additional Resources

- [Docker Troubleshooting Guide](DOCKER_TROUBLESHOOTING.md)
- [Docker Backup & Restore Guide](DOCKER_BACKUP_RESTORE.md)
- [Docker Operations Runbook](DOCKER_OPERATIONS_RUNBOOK.md)
- [Main CLAUDE.md](../../CLAUDE.md)

---

**Last Updated:** November 4, 2025
**Version:** 1.0.0
**Maintainer:** Development Team
