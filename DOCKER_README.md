# Docker Deployment for IntelliWiz

Production-ready Docker containerization for the IntelliWiz enterprise facility management platform.

## 🚀 Quick Start

### Development (5 minutes)

```bash
# 1. Copy environment configuration
cp .env.dev .env

# 2. Start all services
docker-compose -f docker-compose.dev.yml up --build

# 3. Access the application
# Django: http://localhost:8000
# Flower (Celery monitoring): http://localhost:5555
# Database: localhost:5432 (postgres/postgres)
```

### Production (Local/On-Premises)

```bash
# 1. Configure production environment
cp .env.template .env.prod
nano .env.prod  # Edit with your production values

# 2. Build and start services
docker-compose -f docker-compose.prod.yml up -d --build

# 3. Run initial setup
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --no-input
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### Hostinger VPS Deployment (Complete Guide)

**For deploying to Hostinger VPS with Ubuntu + SSL:**

📖 **[Complete Hostinger VPS Deployment Guide](docs/deployment/HOSTINGER_VPS_DEPLOYMENT_GUIDE.md)**

**Quick Steps:**
```bash
# 1. SSH to your VPS
ssh root@your-vps-ip

# 2. Install Docker (one command)
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin

# 3. Clone your repository
cd /opt
git clone your-repo-url intelliwiz
cd intelliwiz

# 4. Configure environment
cp .env.template .env.prod
nano .env.prod  # Add your secrets

# 5. Setup SSL (Let's Encrypt)
apt install -y certbot
certbot certonly --standalone -d yourdomain.com

# 6. Deploy
docker-compose -f docker-compose.prod.yml up -d --build
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

**Access:** https://yourdomain.com

**See also:**
- [Hostinger Quick Reference](docs/deployment/HOSTINGER_VPS_QUICK_REFERENCE.md) - Command cheatsheet

## 📦 What's Included

### 13 Orchestrated Services

**Infrastructure:**
- PostgreSQL 14.2 with PostGIS
- Redis 7.x (caching & message broker)

**Application:**
- Django Web (Gunicorn, 4 workers)
- Daphne ASGI (WebSocket support)

**Background Processing:**
- 8 specialized Celery workers (default, email, reports, onboarding, ml, priority, scheduled, gcs)
- Celery Beat (periodic task scheduler)

**Supporting:**
- Flower (Celery monitoring)
- Nginx (reverse proxy & static files)
- Automated PostgreSQL backups

## 📁 Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Production multi-stage build (optimized) |
| `Dockerfile.dev` | Development with hot-reload |
| `docker-compose.dev.yml` | Development environment (6 services) |
| `docker-compose.prod.yml` | Production environment (13 services) |
| `.env.template` | Environment configuration template |
| `.env.dev` | Development configuration (committed) |
| `.env.prod` | Production configuration (gitignored) |
| `docker/entrypoint.sh` | Container startup script |
| `nginx/nginx.conf` | Nginx configuration |
| `scripts/docker-backup.sh` | Automated backup script |
| `scripts/docker-restore.sh` | Restore from backup script |

## 🛠️ Common Operations

### Development

```bash
# Start services
docker-compose -f docker-compose.dev.yml up

# Start in background
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Run migrations
docker-compose -f docker-compose.dev.yml exec web python manage.py migrate

# Run tests
docker-compose -f docker-compose.dev.yml exec web python -m pytest

# Stop services
docker-compose -f docker-compose.dev.yml down
```

### Production

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart specific service
docker-compose -f docker-compose.prod.yml restart web

# Scale service
docker-compose -f docker-compose.prod.yml up -d --scale web=3

# Health check
curl http://localhost/health/

# Backup
./scripts/docker-backup.sh

# Restore
./scripts/docker-restore.sh
```

## 🔒 Security Features

- ✅ **Non-root containers** - All services run as UID 1000
- ✅ **Network isolation** - Backend network internal-only
- ✅ **Resource limits** - CPU/memory constraints enforced
- ✅ **Read-only filesystems** - Prevents malware persistence
- ✅ **Health checks** - Auto-recovery from failures
- ✅ **Secrets management** - Environment-based configuration
- ✅ **SSL/TLS support** - Nginx with Let's Encrypt

## 📊 Monitoring

### Health Endpoints

```bash
# Application health
curl http://localhost/health/

# Readiness (for load balancers)
curl http://localhost/readiness/

# Liveness (for orchestration)
curl http://localhost/liveness/
```

### Celery Monitoring

Access Flower dashboard:
- **URL:** http://localhost:5555
- **Default credentials:** admin/admin (change in .env.prod)

### Container Metrics

```bash
# Resource usage
docker stats

# Logs
docker-compose -f docker-compose.prod.yml logs -f --tail=100
```

## 💾 Backup & Restore

### Automated Backups

```bash
# Manual backup
./scripts/docker-backup.sh

# Schedule daily backups (add to crontab)
0 2 * * * cd /opt/intelliwiz && ./scripts/docker-backup.sh
```

Backups include:
- PostgreSQL database (compressed SQL dump)
- Media files (tar.gz)
- Docker volumes (postgres_data, redis_data)

Retention: 7 days (daily), 4 weeks (weekly), 6 months (monthly)

### Restore from Backup

```bash
# Interactive restore
./scripts/docker-restore.sh

# Command-line restore
./scripts/docker-restore.sh --database backups/postgres/backup_20250104.sql.gz
./scripts/docker-restore.sh --media backups/media/media_20250104.tar.gz
```

## 🚨 Troubleshooting

### Container won't start

```bash
# View logs
docker-compose -f docker-compose.prod.yml logs <service-name>

# Check health
docker-compose -f docker-compose.prod.yml ps
```

### Database connection errors

```bash
# Check postgres is ready
docker-compose -f docker-compose.prod.yml exec postgres pg_isready
```

### Full reset (DESTRUCTIVE - deletes all data)

```bash
docker-compose -f docker-compose.prod.yml down -v
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

## 📚 Documentation

- **[Docker Deployment Guide](docs/deployment/DOCKER_DEPLOYMENT_GUIDE.md)** - Complete setup and operations guide
- **[Docker Design Document](docs/plans/2025-11-04-docker-deployment-design.md)** - Architecture and design decisions
- **[Main CLAUDE.md](CLAUDE.md)** - Project overview and standards

## 🎯 Benefits

| Benefit | Description |
|---------|-------------|
| **Portability** | Deploy on any infrastructure (on-prem, cloud, hybrid) |
| **Consistency** | Identical dev/staging/production environments |
| **Fast Setup** | New developers productive in <30 minutes |
| **Easy Rollback** | Version-tagged images, instant rollback |
| **Isolation** | Service failures contained, resource limits enforced |
| **Scalability** | Scale individual services independently |

## 🔧 System Requirements

### Minimum (Development)
- CPU: 4 cores
- RAM: 8 GB
- Disk: 50 GB
- Docker: 24.0+
- Docker Compose: 2.20+

### Recommended (Production)
- CPU: 8+ cores
- RAM: 16+ GB
- Disk: 200+ GB SSD
- Docker: 24.0+
- Docker Compose: 2.20+

## 📝 Environment Variables

See `.env.template` for complete list. Critical variables:

```bash
# Django
SECRET_KEY=<generate-50-char-random-string>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com

# Database
DB_NAME=intelliwiz_prod
DB_USER=intelliwiz_user
DB_PASSWORD=<strong-password>

# Redis
REDIS_PASSWORD=<redis-password>

# Email
EMAIL_HOST_USER=<your-email>
EMAIL_HOST_PASSWORD=<app-password>
```

## 🚀 Production Checklist

Before deploying to production:

- [ ] Configure `.env.prod` with production values
- [ ] Generate strong `SECRET_KEY` (50+ random characters)
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS` with your domain
- [ ] Set up SSL certificates (Let's Encrypt recommended)
- [ ] Configure email settings
- [ ] Set up automated backups (cron job)
- [ ] Configure firewall (allow ports 80, 443 only)
- [ ] Set strong passwords for database and Redis
- [ ] Test backup/restore procedure
- [ ] Configure monitoring/alerting

## 🤝 Support

For issues or questions:
1. Check [DOCKER_DEPLOYMENT_GUIDE.md](docs/deployment/DOCKER_DEPLOYMENT_GUIDE.md)
2. Review [CLAUDE.md](CLAUDE.md) for project standards
3. Contact development team

---

**Version:** 1.0.0
**Last Updated:** November 4, 2025
**Status:** Production Ready
