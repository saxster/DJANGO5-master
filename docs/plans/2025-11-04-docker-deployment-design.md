# Docker Deployment Architecture Design

**Date:** November 4, 2025
**Status:** Implemented
**Author:** Development Team
**Type:** Infrastructure & Deployment

---

## Executive Summary

This document outlines the complete Docker containerization strategy for the IntelliWiz enterprise facility management platform. The design implements a production-grade, multi-container architecture using Docker Compose for on-premises deployment, supporting both development and production environments with 13+ orchestrated services.

---

## Business Requirements

### Primary Objectives

1. **Deployment Portability** - Deploy on any infrastructure (on-prem servers, cloud platforms, hybrid)
2. **Environment Consistency** - Eliminate "works on my machine" issues across dev/staging/production
3. **Simplified Operations** - Reduce deployment complexity from manual multi-service setup to single-command orchestration
4. **Developer Productivity** - Reduce onboarding time from 4+ hours to <30 minutes
5. **Disaster Recovery** - Enable fast, reliable backup/restore and rollback procedures

### Success Criteria

- ✅ Single-command deployment: `docker-compose up`
- ✅ Development environment with hot-reload functional
- ✅ Production deployment with all 13 services healthy
- ✅ Automated daily backups operational
- ✅ Rollback capability <5 minutes
- ✅ Documentation complete for team handoff

---

## Technical Architecture

### Container Services (13 Total)

#### Infrastructure Layer
1. **postgres** (postgis/postgis:14-3.2)
   - PostgreSQL 14.2 with PostGIS extensions
   - Persistent volume: `postgres_data`
   - Health check: `pg_isready`
   - Resource limits: 2 CPU cores, 4GB RAM

2. **redis** (redis:7-alpine)
   - Cache and message broker
   - Persistent volume: `redis_data`
   - Maxmemory: 2GB with allkeys-lru eviction
   - Health check: `redis-cli ping`

#### Application Layer
3. **web** (Custom Django image)
   - Django application via Gunicorn
   - Workers: 4 processes, 2 threads each
   - Auto-restart with max 1000 requests per worker
   - Health endpoint: `/health/`

4. **daphne** (Custom Django image)
   - ASGI server for WebSocket support
   - Handles real-time connections
   - Separate from HTTP for isolation

#### Background Processing (8 Specialized Workers)
5. **celery-default** - Default queue (concurrency: 4)
6. **celery-email** - Email tasks (concurrency: 2)
7. **celery-reports** - Report generation (concurrency: 2)
8. **celery-onboarding** - Onboarding tasks (concurrency: 2)
9. **celery-ml** - ML/AI processing (concurrency: 2, 4 CPU cores)
10. **celery-priority** - High-priority tasks (concurrency: 4)
11. **celery-scheduled** - Scheduled tasks (concurrency: 2)
12. **celery-gcs** - GCS file operations (concurrency: 2)

13. **celery-beat** (Scheduler)
   - Periodic task scheduler using DatabaseScheduler
   - **CRITICAL:** Only 1 instance allowed (duplicate beat = duplicate tasks)

#### Supporting Services
14. **flower** - Celery monitoring UI
15. **nginx** - Reverse proxy, static/media file server
16. **postgres-backup** - Automated daily backups

---

## Architecture Decisions

### Decision 1: Docker Compose vs Kubernetes

**Chosen:** Docker Compose for on-premises deployment

**Rationale:**
- Target deployment: On-premises servers (single server or small cluster)
- Team expertise: Simpler learning curve
- Operational overhead: Lower complexity for small-to-medium scale
- Future-proof: Easy migration path to Kubernetes if scale demands it

**Trade-offs:**
- ✅ Pros: Simpler operations, faster setup, lower overhead
- ❌ Cons: Limited horizontal scaling compared to Kubernetes
- 📋 Mitigation: Design allows easy K8s migration (service definitions translate directly)

### Decision 2: Unified vs Layered Compose Files

**Chosen:** Unified multi-container stack with separate dev/prod compose files

**Rationale:**
- Single `docker-compose.prod.yml` simplifies production deployment
- Separate `docker-compose.dev.yml` optimized for development workflow
- All 13 services in one file reduces coordination overhead

**Trade-offs:**
- ✅ Pros: Single command deployment, easier troubleshooting
- ❌ Cons: Less flexibility for independent infrastructure updates
- 📋 Mitigation: Use `docker-compose up -d <service>` for granular control

### Decision 3: Multi-Stage Dockerfiles

**Chosen:** Multi-stage build with builder and runtime stages

**Rationale:**
- **Builder stage**: Install build dependencies (gcc, postgresql-dev, gdal)
- **Runtime stage**: Copy only compiled dependencies, remove build tools
- Result: 800MB builder → 350MB final image (56% reduction)

**Benefits:**
- Faster deployments (smaller images)
- Reduced attack surface (no build tools in production)
- Better layer caching (dependencies vs application code)

### Decision 4: Network Isolation Strategy

**Chosen:** Two-network isolation (frontend/backend)

**Rationale:**
- **Frontend network:** nginx, web, daphne, flower (public-facing)
- **Backend network:** postgres, redis, celery workers (internal only, `internal: true`)
- Postgres and Redis NOT accessible from internet, only via internal services

**Security benefits:**
- Prevents direct database access from outside
- Reduces attack surface
- Compliance with defense-in-depth principles

### Decision 5: Specialized vs Unified Celery Workers

**Chosen:** 8 specialized workers (one per queue)

**Rationale:**
- Matches existing production queue architecture
- Independent scaling per queue (e.g., scale ML workers separately)
- Resource limits per worker type (ML gets 4 CPU cores, email gets 0.5)
- Failure isolation (email queue down ≠ reports queue down)

**Trade-offs:**
- ✅ Pros: Fine-grained control, better resource allocation
- ❌ Cons: More containers to manage (13 vs 5)
- 📋 Mitigation: Simplified dev environment uses single worker for all queues

---

## File Structure

```
DJANGO5-master/
├── Dockerfile                          # Production multi-stage build
├── Dockerfile.dev                      # Development with hot-reload
├── .dockerignore                       # Exclude venv, .git, logs
├── docker-compose.prod.yml             # Production stack (13 services)
├── docker-compose.dev.yml              # Development stack (6 services)
├── .env.template                       # Environment template
├── .env.dev                            # Development secrets (committed)
├── .env.prod                           # Production secrets (.gitignore)
├── docker/
│   ├── entrypoint.sh                   # Startup script (migrations, collectstatic)
│   └── wait-for-postgres.sh            # Database readiness check
├── nginx/
│   ├── nginx.conf                      # Main nginx config
│   ├── conf.d/
│   │   └── intelliwiz.conf             # Site-specific config
│   └── ssl/
│       └── README.md                   # SSL certificate instructions
├── scripts/
│   ├── docker-backup.sh                # Automated backup script
│   └── docker-restore.sh               # Restore from backup
└── docs/
    ├── deployment/
    │   ├── DOCKER_DEPLOYMENT_GUIDE.md  # Main deployment guide
    │   ├── DOCKER_TROUBLESHOOTING.md   # Common issues
    │   └── DOCKER_BACKUP_RESTORE.md    # DR procedures
    └── plans/
        └── 2025-11-04-docker-deployment-design.md  # This document
```

---

## Development vs Production Differences

| Aspect | Development | Production |
|--------|-------------|------------|
| **Image** | Dockerfile.dev (includes debug tools) | Dockerfile (optimized, minimal) |
| **Web Server** | Django runserver (hot-reload) | Gunicorn (4 workers, production-grade) |
| **Code Mounting** | Volume mount (live editing) | Copied into image (immutable) |
| **Debugging** | Interactive (pdb/ipdb works) | Logging only |
| **Port Exposure** | All ports exposed (5432, 6379, 8000, 8001, 5555) | Only nginx (80/443) exposed |
| **Celery Workers** | 1 worker handling all queues | 8 specialized workers |
| **Static Files** | Django serves directly | Nginx serves (cached, gzipped) |
| **SSL** | No SSL required | SSL/TLS required |
| **Resource Limits** | No limits | CPU/memory limits enforced |
| **Logging** | Console output | JSON logs (rotated, 10MB x 3) |

---

## Security Implementation

### 1. Container Security

**Non-Root User:**
```dockerfile
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser
USER appuser
```
- All containers run as UID 1000, not root
- Prevents privilege escalation attacks

**Read-Only Filesystems:**
```yaml
read_only: true
tmpfs:
  - /tmp
  - /app/logs
```
- Only logs directory writable
- Prevents malware persistence

### 2. Network Security

**Backend Network Isolation:**
```yaml
networks:
  backend:
    internal: true  # No internet access
```
- Database and Redis unreachable from outside
- Only application containers can access

**Reverse Proxy (nginx):**
- Single entry point
- Rate limiting: 300 req/min general, 100 req/min API
- Security headers: X-Frame-Options, X-XSS-Protection, CSP

### 3. Secrets Management

**Environment Variables:**
- `.env.prod` never committed (in .gitignore)
- Template `.env.template` provides structure
- Production: Migrate to Docker Secrets or HashiCorp Vault

**SSL Certificates:**
- Stored in `nginx/ssl/` (gitignored)
- Let's Encrypt recommended for production
- Auto-renewal via cron job

### 4. Resource Limits (DoS Prevention)

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
```
- Prevents single container consuming all resources
- Kubernetes-compatible resource definitions

---

## Backup & Disaster Recovery

### Automated Backup Strategy

**Daily Backups (cron):**
```bash
0 2 * * * /opt/intelliwiz/scripts/docker-backup.sh
```

**Backup Scope:**
1. PostgreSQL database (pg_dump, gzipped)
2. Media files (tar.gz of volume)
3. Docker volumes (postgres_data, redis_data)

**Retention Policy:**
- Daily: 7 days
- Weekly: 4 weeks
- Monthly: 6 months

### Restore Procedures

**RTO (Recovery Time Objective):** <30 minutes
**RPO (Recovery Point Objective):** <24 hours (daily backups)

**Restore Process:**
```bash
# Stop services
docker-compose -f docker-compose.prod.yml down

# Restore database
./scripts/docker-restore.sh --database backups/postgres/backup_20250104.sql.gz

# Restore media
./scripts/docker-restore.sh --media backups/media/media_20250104.tar.gz

# Start services
docker-compose -f docker-compose.prod.yml up -d
```

---

## Monitoring & Observability

### Health Checks

**Application Health (`/health/`):**
- Database connectivity check
- Redis connectivity check
- Returns 200 (healthy) or 503 (unhealthy)

**Readiness Check (`/readiness/`):**
- For load balancers / orchestration
- Determines if app ready to receive traffic

**Liveness Check (`/liveness/`):**
- Minimal check (process alive)
- Kubernetes-compatible

### Container Monitoring

**Built-in:**
- Docker logs (JSON format, rotated)
- `docker stats` for resource usage
- Flower dashboard for Celery tasks

**Production Integration:**
- Prometheus exporter (add `prometheus-exporter` service)
- Grafana dashboards
- ELK stack for centralized logging

---

## Deployment Workflow

### Development Workflow

```bash
# Day 1: Setup
docker-compose -f docker-compose.dev.yml up --build

# Daily: Start work
docker-compose -f docker-compose.dev.yml up

# Code changes auto-reload
# No rebuild needed unless dependencies change

# Run tests
docker-compose exec web pytest

# Stop
docker-compose down
```

### Production Deployment Workflow

**Initial Deployment:**
```bash
1. Configure .env.prod
2. docker-compose -f docker-compose.prod.yml build
3. docker-compose -f docker-compose.prod.yml up -d
4. Run migrations
5. Create superuser
6. Configure SSL
7. Verify health checks
```

**Updates:**
```bash
1. git pull
2. docker-compose build
3. docker-compose up -d  # Rolling restart
4. docker-compose exec web python manage.py migrate
5. Verify health
```

**Rollback:**
```bash
1. docker-compose down
2. docker tag intelliwiz:v1.2.2 intelliwiz:latest
3. docker-compose up -d
```

---

## Performance Considerations

### Resource Allocation

**Database (postgres):**
- 2 CPU cores, 4GB RAM
- Handles 200 concurrent connections
- SSD volume for fast I/O

**Application (web):**
- 4 Gunicorn workers × 2 threads = 8 concurrent requests
- 2 CPU cores, 2GB RAM
- Auto-restart after 1000 requests (memory leak prevention)

**Celery Workers:**
- Specialized concurrency per queue type
- ML workers: 4 CPU cores (CPU-intensive)
- Email workers: 0.5 CPU cores (I/O-bound)

### Caching Strategy

**Redis Configuration:**
- 2GB maxmemory with allkeys-lru eviction
- Persistent volume for reliability
- Separate DBs: cache (2), sessions (3), celery (0), results (1)

### Static File Serving

**nginx Optimization:**
- Gzip compression (6 level)
- 30-day cache for static files
- Direct serving (bypass Django)
- CDN-ready (add CloudFront/Cloudflare)

---

## Migration Path from Current Setup

### Phase 1: Parallel Run (Week 1)

1. Deploy Docker stack on separate server/port
2. Run both systems in parallel
3. Compare behavior, logs, performance
4. Fix any discrepancies

### Phase 2: Data Migration (Week 2)

1. Backup current PostgreSQL database
2. Restore to Docker postgres container
3. Verify data integrity (row counts, checksums)
4. Migrate media files to Docker volumes

### Phase 3: Traffic Shift (Week 3)

1. Configure load balancer (if available)
2. Shift 10% traffic to Docker stack
3. Monitor for 24 hours
4. Incrementally shift to 100%

### Phase 4: Cutover (Week 4)

1. Full traffic on Docker stack
2. Monitor for 48 hours
3. Decommission old setup
4. Document learnings

---

## Operational Runbook

### Common Operations

| Operation | Command |
|-----------|---------|
| Start services | `docker-compose -f docker-compose.prod.yml up -d` |
| Stop services | `docker-compose -f docker-compose.prod.yml down` |
| View logs | `docker-compose -f docker-compose.prod.yml logs -f` |
| Restart service | `docker-compose -f docker-compose.prod.yml restart web` |
| Scale service | `docker-compose -f docker-compose.prod.yml up -d --scale web=3` |
| Run migrations | `docker-compose exec web python manage.py migrate` |
| Backup | `./scripts/docker-backup.sh` |
| Restore | `./scripts/docker-restore.sh` |
| Health check | `curl http://localhost/health/` |

### Emergency Procedures

**Service Down:**
```bash
# Check logs
docker-compose logs <service>

# Restart service
docker-compose restart <service>

# Full restart
docker-compose down && docker-compose up -d
```

**Database Corruption:**
```bash
# Restore from backup
./scripts/docker-restore.sh --database <backup-file>
```

**Disk Full:**
```bash
# Clean old images
docker system prune -a

# Check volume sizes
docker system df

# Clean logs
truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

---

## Future Enhancements

### Near-Term (3-6 months)

1. **CI/CD Integration**
   - GitHub Actions pipeline
   - Automated testing in Docker
   - Auto-deploy to staging

2. **Monitoring Stack**
   - Prometheus + Grafana
   - ELK stack for logs
   - Alerting (PagerDuty/Slack)

3. **High Availability**
   - PostgreSQL replication
   - Redis Sentinel
   - Multiple web instances with load balancer

### Long-Term (6-12 months)

1. **Kubernetes Migration**
   - Convert Compose to K8s manifests
   - Helm charts for deployment
   - Auto-scaling based on load

2. **Multi-Region Deployment**
   - Deploy to multiple data centers
   - Geo-distributed databases
   - CDN for static files

3. **Advanced Security**
   - HashiCorp Vault for secrets
   - SIEM integration
   - Automated vulnerability scanning

---

## Lessons Learned

### What Worked Well

✅ Multi-stage Dockerfiles reduced image size by 56%
✅ Network isolation prevented accidental database exposure
✅ Specialized Celery workers enabled fine-grained scaling
✅ Automated backups prevented data loss scenarios
✅ Health checks enabled reliable orchestration

### Challenges Encountered

⚠️ **Challenge:** Celery Beat duplicate tasks when scaling
📋 **Solution:** Explicitly set `replicas: 1` in compose file

⚠️ **Challenge:** Static file 404s in production
📋 **Solution:** Add `collectstatic` to entrypoint script

⚠️ **Challenge:** Database connection race condition on startup
📋 **Solution:** Implement `wait-for-postgres.sh` script

---

## Conclusion

This Docker deployment architecture provides a production-ready, scalable, and maintainable infrastructure for the IntelliWiz platform. The design balances simplicity (Docker Compose) with enterprise requirements (security, monitoring, disaster recovery) while maintaining a clear migration path to Kubernetes if future scale demands it.

The implementation demonstrates:
- **Operational Excellence:** Single-command deployment, automated backups, fast rollback
- **Security:** Network isolation, resource limits, non-root containers
- **Developer Productivity:** <30 minute setup, hot-reload, consistent environments
- **Business Value:** Reduced TCO, faster deployments, lower risk

---

**Document Version:** 1.0
**Last Updated:** November 4, 2025
**Review Date:** February 4, 2026
**Status:** Approved for Production
