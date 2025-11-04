# Hostinger VPS Quick Reference - IntelliWiz

**One-Page Command Cheatsheet**

---

## 🔗 Connect to VPS

```bash
ssh root@YOUR_VPS_IP
```

---

## 📂 Navigate to Application

```bash
cd /opt/intelliwiz
```

---

## 🚀 Common Operations

### Start All Services
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Stop All Services
```bash
docker-compose -f docker-compose.prod.yml down
```

### Restart All Services
```bash
docker-compose -f docker-compose.prod.yml restart
```

### Restart Specific Service
```bash
docker-compose -f docker-compose.prod.yml restart web
docker-compose -f docker-compose.prod.yml restart nginx
docker-compose -f docker-compose.prod.yml restart celery-default
```

---

## 📊 Monitoring

### Check Status
```bash
docker-compose -f docker-compose.prod.yml ps
```

### View Logs (All Services)
```bash
docker-compose -f docker-compose.prod.yml logs -f
```

### View Logs (Specific Service)
```bash
docker-compose -f docker-compose.prod.yml logs -f web
docker-compose -f docker-compose.prod.yml logs -f postgres
docker-compose -f docker-compose.prod.yml logs -f nginx
```

### Resource Usage
```bash
docker stats
```

### Health Check
```bash
curl http://localhost/health/
```

---

## 🔄 Update Application

```bash
cd /opt/intelliwiz
git pull
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --no-input
```

---

## 🗄️ Database Operations

### Run Migrations
```bash
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### Django Shell
```bash
docker-compose -f docker-compose.prod.yml exec web python manage.py shell
```

### Database Shell
```bash
docker-compose -f docker-compose.prod.yml exec postgres psql -U intelliwiz_user -d intelliwiz_prod
```

### Create Superuser
```bash
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

---

## 💾 Backup & Restore

### Manual Backup
```bash
cd /opt/intelliwiz
./scripts/docker-backup.sh
```

### Restore
```bash
cd /opt/intelliwiz
./scripts/docker-restore.sh
```

### View Backups
```bash
ls -lh /opt/intelliwiz/backups/postgres/
ls -lh /opt/intelliwiz/backups/media/
```

---

## 🔧 Troubleshooting

### Container Won't Start
```bash
docker-compose -f docker-compose.prod.yml logs <service-name>
docker-compose -f docker-compose.prod.yml restart <service-name>
```

### Check Database Connection
```bash
docker-compose -f docker-compose.prod.yml exec postgres pg_isready
```

### Full Restart (Nuclear Option)
```bash
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

### Out of Disk Space
```bash
df -h
docker system prune -a  # WARNING: Removes all unused containers/images
```

---

## 🔒 SSL Certificate

### Renew Certificate Manually
```bash
certbot renew
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/intelliwiz/nginx/ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/intelliwiz/nginx/ssl/key.pem
docker-compose -f docker-compose.prod.yml restart nginx
```

### Check Certificate Expiry
```bash
certbot certificates
```

---

## 🛡️ Security

### Check Firewall Status
```bash
ufw status
```

### Check fail2ban
```bash
fail2ban-client status sshd
```

### System Updates
```bash
apt update && apt upgrade -y
```

---

## 📱 Access Points

- **Main App:** https://yourdomain.com
- **Admin:** https://yourdomain.com/admin/
- **Flower (Celery):** https://yourdomain.com/flower/
- **Health Check:** https://yourdomain.com/health/

---

## 🆘 Emergency Commands

### Full System Restart
```bash
docker-compose -f docker-compose.prod.yml down
docker system prune -f
docker-compose -f docker-compose.prod.yml up -d --build
```

### Check Disk Usage by Container
```bash
docker system df
```

### Remove All Stopped Containers
```bash
docker container prune
```

### Remove Unused Images
```bash
docker image prune -a
```

---

## 📋 Pre-Deployment Checklist

Before deploying updates:

- [ ] Backup database: `./scripts/docker-backup.sh`
- [ ] Test locally: `docker-compose -f docker-compose.dev.yml up`
- [ ] Pull code: `git pull`
- [ ] Build: `docker-compose -f docker-compose.prod.yml build`
- [ ] Deploy: `docker-compose -f docker-compose.prod.yml up -d`
- [ ] Migrate: `docker-compose exec web python manage.py migrate`
- [ ] Health check: `curl http://localhost/health/`
- [ ] Test in browser: https://yourdomain.com

---

## 🔍 Log Locations

### Docker Logs
```bash
docker-compose -f docker-compose.prod.yml logs -f
```

### Nginx Logs
```bash
docker-compose -f docker-compose.prod.yml exec nginx tail -f /var/log/nginx/access.log
docker-compose -f docker-compose.prod.yml exec nginx tail -f /var/log/nginx/error.log
```

### System Logs
```bash
tail -f /var/log/syslog
tail -f /var/log/auth.log  # SSH attempts
```

---

## 💡 Pro Tips

### Alias for Convenience
Add to `~/.bashrc`:
```bash
alias dcprod='docker-compose -f /opt/intelliwiz/docker-compose.prod.yml'
alias cdapp='cd /opt/intelliwiz'
```

Then reload:
```bash
source ~/.bashrc
```

Now you can use:
```bash
dcprod ps
dcprod logs -f web
cdapp
```

### Watch Container Status
```bash
watch -n 2 'docker-compose -f /opt/intelliwiz/docker-compose.prod.yml ps'
```

### Monitor Logs in Real-Time
```bash
# Multiple terminals with tmux/screen
docker-compose -f docker-compose.prod.yml logs -f web &
docker-compose -f docker-compose.prod.yml logs -f celery-default &
docker-compose -f docker-compose.prod.yml logs -f nginx &
```

---

**Quick Help:** For detailed instructions, see [HOSTINGER_VPS_DEPLOYMENT_GUIDE.md](HOSTINGER_VPS_DEPLOYMENT_GUIDE.md)
