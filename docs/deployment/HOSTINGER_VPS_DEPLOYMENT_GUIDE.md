# Hostinger VPS Deployment Guide - IntelliWiz Docker

**Complete Beginner-Friendly Guide**

Deploy your IntelliWiz Django application to Hostinger VPS with Docker, SSL, and production best practices.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: Connect to Your VPS](#step-1-connect-to-your-vps)
3. [Step 2: Prepare the Server](#step-2-prepare-the-server)
4. [Step 3: Install Docker](#step-3-install-docker)
5. [Step 4: Security Setup](#step-4-security-setup)
6. [Step 5: Deploy Your Code](#step-5-deploy-your-code)
7. [Step 6: Configure Production Environment](#step-6-configure-production-environment)
8. [Step 7: SSL Certificate Setup](#step-7-ssl-certificate-setup)
9. [Step 8: Start the Application](#step-8-start-the-application)
10. [Step 9: Verify Deployment](#step-9-verify-deployment)
11. [Step 10: Set Up Automated Backups](#step-10-set-up-automated-backups)
12. [Troubleshooting](#troubleshooting)
13. [Updating Your Application](#updating-your-application)

---

## Prerequisites

### What You Need

✅ **Hostinger VPS Account** with Ubuntu 20.04 or 22.04
✅ **Domain name** pointed to your VPS IP address
✅ **SSH access** to your VPS (you mentioned you have this)
✅ **Your code** on GitHub/GitLab or local repository

### Information to Gather

Before starting, have these ready:

1. **VPS IP Address** - Find in Hostinger control panel
2. **SSH Credentials** - Username (usually `root`) and password
3. **Domain name** - Example: `yourdomain.com`
4. **Repository URL** - Your Git repository (or plan to upload via SCP)

### On Your Local Machine

You need a terminal application:
- **Mac/Linux:** Built-in Terminal app
- **Windows:** PowerShell, or install [PuTTY](https://www.putty.org/)

---

## Step 1: Connect to Your VPS

### 1.1 Open Terminal

**Mac/Linux:**
- Press `Cmd + Space`, type "Terminal", press Enter

**Windows:**
- Press `Win + X`, select "Windows PowerShell"

### 1.2 Connect via SSH

```bash
ssh root@YOUR_VPS_IP_ADDRESS
```

**Example:**
```bash
ssh root@185.123.45.67
```

**What happens:**
1. It will ask "Are you sure you want to continue connecting?" → Type `yes` and press Enter
2. Enter your password (you won't see characters as you type - this is normal)
3. You should see something like: `root@vps-12345:~#`

**✅ Success:** You're now connected to your VPS!

---

## Step 2: Prepare the Server

### 2.1 Update System Packages

```bash
apt update && apt upgrade -y
```

**What this does:** Downloads latest security updates and software versions

**Time:** 2-5 minutes

**Expected output:**
```
Reading package lists... Done
Building dependency tree... Done
...
0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.
```

### 2.2 Install Required Tools

```bash
apt install -y curl wget git nano ufw fail2ban
```

**What each tool does:**
- `curl` & `wget` - Download files from internet
- `git` - Download your code from repository
- `nano` - Simple text editor for config files
- `ufw` - Firewall (security)
- `fail2ban` - Blocks hackers trying to guess passwords

**Time:** 1-2 minutes

---

## Step 3: Install Docker

### 3.1 Install Docker Engine

Run this command (it's long, copy the whole thing):

```bash
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
```

**What this does:** Downloads and installs Docker automatically

**Time:** 2-3 minutes

**Expected output:**
```
# Executing docker install script...
...
Docker version 24.0.7, build afdd53b
```

### 3.2 Install Docker Compose

```bash
apt install -y docker-compose-plugin
```

**Verify installation:**
```bash
docker --version
docker compose version
```

**Expected output:**
```
Docker version 24.0.7, build afdd53b
Docker Compose version v2.21.0
```

**✅ Success:** Docker is installed!

### 3.3 Start Docker

```bash
systemctl enable docker
systemctl start docker
systemctl status docker
```

**Expected:** You should see "active (running)" in green

Press `q` to exit the status view

---

## Step 4: Security Setup

### 4.1 Configure Firewall

**Allow SSH (port 22) - IMPORTANT: Do this first!**
```bash
ufw allow 22/tcp
```

**Allow HTTP (port 80) and HTTPS (port 443):**
```bash
ufw allow 80/tcp
ufw allow 443/tcp
```

**Enable firewall:**
```bash
ufw enable
```

Type `y` and press Enter when asked

**Verify:**
```bash
ufw status
```

**Expected output:**
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
```

### 4.2 Configure fail2ban (SSH Protection)

```bash
systemctl enable fail2ban
systemctl start fail2ban
```

**What this does:** Automatically blocks IPs that try to brute-force your SSH password

### 4.3 Create Deployment Directory

```bash
mkdir -p /opt/intelliwiz
cd /opt/intelliwiz
```

**What this does:**
- Creates `/opt/intelliwiz` folder (where your app will live)
- Changes to that directory

---

## Step 5: Deploy Your Code

### Option A: From Git Repository (Recommended)

**If your code is on GitHub/GitLab:**

```bash
cd /opt
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git intelliwiz
cd intelliwiz
```

**Replace** `YOUR_USERNAME/YOUR_REPO` with your actual repository

**Example:**
```bash
git clone https://github.com/mycompany/intelliwiz-app.git intelliwiz
```

### Option B: Upload from Local Machine

**If your code is on your computer:**

**On your local machine** (new terminal window):
```bash
# Compress your code
cd /path/to/DJANGO5-master
tar czf intelliwiz.tar.gz .

# Upload to VPS
scp intelliwiz.tar.gz root@YOUR_VPS_IP:/opt/

# Back on VPS terminal
cd /opt
tar xzf intelliwiz.tar.gz -C intelliwiz
cd intelliwiz
```

**✅ Checkpoint:** Run `ls` and you should see files like `manage.py`, `docker-compose.prod.yml`, etc.

---

## Step 6: Configure Production Environment

### 6.1 Create Production Environment File

```bash
cp .env.template .env.prod
nano .env.prod
```

**This opens a text editor.** Edit these critical values:

```bash
# Django Core
SECRET_KEY=<GENERATE_A_RANDOM_50_CHARACTER_STRING>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
ENVIRONMENT=production

# Database
DB_NAME=intelliwiz_prod
DB_USER=intelliwiz_user
DB_PASSWORD=<STRONG_PASSWORD_HERE>

# Redis
REDIS_PASSWORD=<ANOTHER_STRONG_PASSWORD>

# Email (if using Gmail)
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=<GMAIL_APP_PASSWORD>
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

### 6.2 Generate SECRET_KEY

**Easy way to generate:**
```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Copy the output and paste it as your `SECRET_KEY` value

### 6.3 Save the File

**In nano editor:**
1. Press `Ctrl + X` to exit
2. Press `Y` to save
3. Press `Enter` to confirm filename

### 6.4 Secure the Environment File

```bash
chmod 600 .env.prod
```

**What this does:** Makes the file readable only by root (security)

---

## Step 7: SSL Certificate Setup

### 7.1 Install Certbot (Let's Encrypt)

```bash
apt install -y certbot python3-certbot-nginx
```

### 7.2 Generate SSL Certificate

**Stop nginx if running:**
```bash
docker-compose -f docker-compose.prod.yml stop nginx 2>/dev/null || true
```

**Generate certificate:**
```bash
certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
```

**Replace `yourdomain.com` with your actual domain**

**You'll be asked:**
1. Email address → Enter your email
2. Agree to Terms of Service → Type `A` and press Enter
3. Share email with EFF → Type `N` (optional)

**Expected output:**
```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/yourdomain.com/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

### 7.3 Copy Certificates to Nginx

```bash
mkdir -p /opt/intelliwiz/nginx/ssl
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/intelliwiz/nginx/ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/intelliwiz/nginx/ssl/key.pem
```

### 7.4 Update Nginx Configuration

```bash
nano /opt/intelliwiz/nginx/conf.d/intelliwiz.conf
```

**Find these lines (around line 90-95) and uncomment them:**

**Before:**
```nginx
# ssl_certificate /etc/nginx/ssl/cert.pem;
# ssl_certificate_key /etc/nginx/ssl/key.pem;
```

**After (remove the # symbols):**
```nginx
ssl_certificate /etc/nginx/ssl/cert.pem;
ssl_certificate_key /etc/nginx/ssl/key.pem;
```

**Also find (around line 25) and uncomment:**
```nginx
# return 301 https://$host$request_uri;
```

**Save:** `Ctrl + X`, then `Y`, then `Enter`

### 7.5 Set Up Auto-Renewal

```bash
crontab -e
```

**Choose editor:** Select `1` for nano (if asked)

**Add this line at the end:**
```bash
0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/intelliwiz/nginx/ssl/cert.pem && cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/intelliwiz/nginx/ssl/key.pem && cd /opt/intelliwiz && docker-compose -f docker-compose.prod.yml restart nginx
```

**Replace `yourdomain.com` with your domain**

**Save:** `Ctrl + X`, then `Y`, then `Enter`

**What this does:** Automatically renews your SSL certificate on the 1st of every month

---

## Step 8: Start the Application

### 8.1 Build Docker Images

```bash
cd /opt/intelliwiz
docker-compose -f docker-compose.prod.yml build --no-cache
```

**Time:** 10-15 minutes (first time only)

**What this does:** Creates Docker images with your application code

**Expected:** You'll see lots of output as it builds. Wait for "Successfully built..."

### 8.2 Start Infrastructure Services

**Start database and Redis first:**
```bash
docker-compose -f docker-compose.prod.yml up -d postgres redis
```

**Wait 30 seconds for database to initialize:**
```bash
sleep 30
```

**Check they're running:**
```bash
docker-compose -f docker-compose.prod.yml ps postgres redis
```

**Expected:** Both should show "Up (healthy)"

### 8.3 Run Database Migrations

```bash
docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate
```

**Expected output:**
```
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  ...
```

### 8.4 Create Superuser

```bash
docker-compose -f docker-compose.prod.yml run --rm web python manage.py createsuperuser
```

**You'll be asked for:**
- Username → Choose admin username
- Email → Your email
- Password → Strong password (you won't see it as you type)

### 8.5 Collect Static Files

```bash
docker-compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --no-input
```

**Expected:**
```
123 static files copied to '/app/staticfiles'.
```

### 8.6 Start All Services

```bash
docker-compose -f docker-compose.prod.yml up -d
```

**This starts all 13 containers:**
- postgres
- redis
- web (Django)
- daphne (WebSockets)
- 8 Celery workers
- celery-beat
- flower
- nginx
- postgres-backup

**Time:** 30-60 seconds

### 8.7 Verify All Services Running

```bash
docker-compose -f docker-compose.prod.yml ps
```

**Expected:** All services should show "Up" or "Up (healthy)"

**If any show "Restarting" or "Exit":**
```bash
docker-compose -f docker-compose.prod.yml logs <service-name>
```

---

## Step 9: Verify Deployment

### 9.1 Test Health Endpoint

```bash
curl http://localhost/health/
```

**Expected output:**
```json
{"status":"healthy","checks":{"database":"ok","cache":"ok","application":"ok"}}
```

**If you see "unhealthy":**
```bash
docker-compose -f docker-compose.prod.yml logs web
```

### 9.2 Test Your Domain

**On your computer**, open a web browser and go to:
```
https://yourdomain.com
```

**Expected:** You should see your Django application's login page with a green padlock (SSL working)

### 9.3 Test Admin Panel

```
https://yourdomain.com/admin/
```

Log in with the superuser you created

**Expected:** Django admin interface loads

### 9.4 Check Celery Workers

**Access Flower (Celery monitoring):**
```
https://yourdomain.com/flower/
```

**Default credentials:** admin / admin (change in .env.prod)

**Expected:** You should see 8 active workers

---

## Step 10: Set Up Automated Backups

### 10.1 Make Backup Script Executable

```bash
chmod +x /opt/intelliwiz/scripts/docker-backup.sh
```

### 10.2 Test Backup

```bash
/opt/intelliwiz/scripts/docker-backup.sh
```

**Expected:** Creates backups in `/opt/intelliwiz/backups/`

### 10.3 Schedule Daily Backups

```bash
crontab -e
```

**Add this line:**
```bash
0 2 * * * cd /opt/intelliwiz && ./scripts/docker-backup.sh >> /var/log/intelliwiz-backup.log 2>&1
```

**What this does:** Runs backup every day at 2 AM

**Save:** `Ctrl + X`, then `Y`, then `Enter`

### 10.4 Create Log File

```bash
touch /var/log/intelliwiz-backup.log
```

---

## 🎉 Deployment Complete!

Your IntelliWiz application is now running on Hostinger VPS with:

✅ **13 Docker containers** orchestrated and running
✅ **SSL/HTTPS** with Let's Encrypt (auto-renewing)
✅ **Firewall** protecting your server
✅ **Automated backups** daily at 2 AM
✅ **Production-ready** configuration

### Access Your Application

- **Main app:** https://yourdomain.com
- **Admin:** https://yourdomain.com/admin/
- **Celery monitoring:** https://yourdomain.com/flower/
- **API (if applicable):** https://yourdomain.com/api/v1/

---

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
docker-compose -f docker-compose.prod.yml logs <service-name>
```

**Common fixes:**
```bash
# Restart specific service
docker-compose -f docker-compose.prod.yml restart web

# Restart all
docker-compose -f docker-compose.prod.yml restart
```

### Database Connection Errors

**Check postgres is running:**
```bash
docker-compose -f docker-compose.prod.yml exec postgres pg_isready
```

**Verify environment variables:**
```bash
docker-compose -f docker-compose.prod.yml exec web env | grep DB_
```

### SSL Certificate Not Working

**Check certificate files exist:**
```bash
ls -la /opt/intelliwiz/nginx/ssl/
```

**Check nginx logs:**
```bash
docker-compose -f docker-compose.prod.yml logs nginx
```

### Out of Disk Space

**Check disk usage:**
```bash
df -h
```

**Clean up Docker:**
```bash
docker system prune -a
```

**Type `y` when asked**

### Can't Access via Domain

**Check DNS:**
```bash
ping yourdomain.com
```

**Should show your VPS IP address**

**Check firewall:**
```bash
ufw status
```

**Ports 80 and 443 should be allowed**

### 502 Bad Gateway Error

**Check web container:**
```bash
docker-compose -f docker-compose.prod.yml ps web
docker-compose -f docker-compose.prod.yml logs web
```

**Restart web:**
```bash
docker-compose -f docker-compose.prod.yml restart web
```

---

## Updating Your Application

### When You Make Code Changes

**On VPS:**

```bash
# 1. Go to application directory
cd /opt/intelliwiz

# 2. Pull latest code (if using Git)
git pull

# 3. Rebuild Docker images
docker-compose -f docker-compose.prod.yml build

# 4. Restart services
docker-compose -f docker-compose.prod.yml up -d

# 5. Run any new migrations
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate

# 6. Collect static files
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --no-input

# 7. Verify
curl http://localhost/health/
```

**Total time:** 5-10 minutes

---

## Useful Commands Reference

### Check Status
```bash
docker-compose -f docker-compose.prod.yml ps
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f web

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100
```

### Restart Services
```bash
# All
docker-compose -f docker-compose.prod.yml restart

# Specific
docker-compose -f docker-compose.prod.yml restart web
```

### Stop/Start
```bash
# Stop all
docker-compose -f docker-compose.prod.yml down

# Start all
docker-compose -f docker-compose.prod.yml up -d
```

### Run Django Commands
```bash
# Shell
docker-compose -f docker-compose.prod.yml exec web python manage.py shell

# Create superuser
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# Migrations
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### Check Resource Usage
```bash
docker stats
```

### Clean Up
```bash
# Remove old images
docker image prune -a

# Remove old containers
docker container prune

# Full cleanup (CAREFUL - removes everything not running)
docker system prune -a
```

---

## Backup & Restore

### Manual Backup
```bash
cd /opt/intelliwiz
./scripts/docker-backup.sh
```

### Restore from Backup
```bash
cd /opt/intelliwiz
./scripts/docker-restore.sh
```

**Follow interactive prompts**

### View Backups
```bash
ls -lh /opt/intelliwiz/backups/postgres/
ls -lh /opt/intelliwiz/backups/media/
```

---

## Security Best Practices

### Change Default Passwords

**In .env.prod, change:**
- `DB_PASSWORD`
- `REDIS_PASSWORD`
- `FLOWER_USER` and `FLOWER_PASSWORD`

### Regular Updates

**Monthly:**
```bash
apt update && apt upgrade -y
```

### Monitor Logs

**Check fail2ban:**
```bash
fail2ban-client status sshd
```

### SSH Key Authentication (Recommended)

**On your local machine:**
```bash
ssh-keygen -t rsa -b 4096
ssh-copy-id root@YOUR_VPS_IP
```

**On VPS, disable password auth:**
```bash
nano /etc/ssh/sshd_config
```

**Find and change:**
```
PasswordAuthentication no
```

**Restart SSH:**
```bash
systemctl restart sshd
```

---

## Getting Help

### Check Documentation
- [Main Docker Guide](DOCKER_DEPLOYMENT_GUIDE.md)
- [Quick Reference](HOSTINGER_VPS_QUICK_REFERENCE.md)
- [Project README](../../CLAUDE.md)

### Common Issues
- Database won't start → Check `docker-compose logs postgres`
- SSL not working → Verify domain DNS points to VPS IP
- Out of memory → Upgrade VPS plan or reduce worker concurrency
- Slow performance → Check `docker stats` for resource usage

---

**Congratulations! Your application is now live on Hostinger VPS! 🎊**

**Last Updated:** November 4, 2025
**Version:** 1.0
**Platform:** Hostinger VPS (Ubuntu 20.04/22.04)
