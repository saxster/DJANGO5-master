# Production Deployment Guide

## System Requirements & Installation

### Core Dependencies
Install the following system components:

- **Python 3.10** - Primary runtime environment
- **Redis 7.2.5** - Caching and message broker
- **Mosquitto Broker 2.0.11** - MQTT messaging
- **Supervisor** - Process management
- **PostgreSQL 14.2** - Primary database
- **PostGIS 3.2.2** - Spatial database extension
- **Nginx** - Web server and reverse proxy
- **Gunicorn** - Python WSGI HTTP server

## PostgreSQL Installation & Configuration

### Installation (Ubuntu 20.04)
Follow the PostgreSQL Ubuntu 20.04 Quick Start Guide:

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Database Setup

1. Switch to postgres user and create database:

```sql
sudo -u postgres psql
CREATE DATABASE youtility4db;
CREATE USER youtilitydba WITH ENCRYPTED PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE youtility4db TO youtilitydba;
\q
```

2. Install PostGIS extension:

```bash
sudo apt install postgresql-14-postgis-3
sudo -u postgres psql -d youtility4db
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;
\q
```

## Django Application Setup

### Environment Configuration

1. Create and activate Python virtual environment:

```bash
python3.10 -m venv /home/redmine/envs/youtility4
source /home/redmine/envs/youtility4/bin/activate
```

2. Install project dependencies:

```bash
pip install -r requirements.txt
```

3. Copy codebase to production server

4. Ensure default data files are current:
   - typeassist.xlsx
   - caps.xlsx

### Production Settings

1. Verify .env file path configuration in settings.py

2. Update environment variables for production:

```bash
# Database configuration
DATABASE_URL=postgresql://youtilitydba:your_password@localhost:5432/youtility4db
DEBUG=False
ALLOWED_HOSTS=your_domain.com,your_server_ip
```

### Directory Structure
Create required directories based on environment variables:

```bash
sudo mkdir -p /var/www/youtility4/static
sudo mkdir -p /var/www/youtility4/media
sudo mkdir -p /var/log/youtility4
sudo chown -R redmine:redmine /var/www/youtility4
sudo chown -R redmine:redmine /var/log/youtility4
```

### Static Files & Database

1. Collect static files:

```bash
python manage.py collectstatic --no-input
```

2. Reset migrations:

```bash
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete
```

3. Run database migrations:

```bash
python manage.py makemigrations
python manage.py migrate peoples
python manage.py migrate
```

4. Initialize application:

```bash
python manage.py init_intelliwiz default
```

## Web Server Configuration

### Gunicorn Setup
Follow the Django with Postgres, Nginx and Gunicorn Guide:

1. Create Gunicorn socket file `/etc/systemd/system/gunicorn.socket`:

```ini
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock

[Install]
WantedBy=sockets.target
```

2. Create Gunicorn service file `/etc/systemd/system/gunicorn.service`:

```ini
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=redmine
Group=www-data
WorkingDirectory=/home/redmine/youtility4_icici
ExecStart=/home/redmine/envs/youtility4/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          intelliwiz_config.wsgi:application

[Install]
WantedBy=multi-user.target
```

3. Enable and start Gunicorn:

```bash
sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.socket
```

### Nginx Configuration

1. Create Nginx server block `/etc/nginx/sites-available/youtility4`:

```nginx
server {
    listen 80;
    server_name your_domain.com your_server_ip;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        root /var/www/youtility4;
    }

    location /media/ {
        root /var/www/youtility4;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
```

2. Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/youtility4 /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Process Management with Supervisor

### Supervisor Installation

```bash
sudo apt-get update -y
sudo apt-get install supervisor -y
sudo service supervisor start
sudo systemctl enable supervisor
```

### Celery Configuration
Create `/etc/supervisor/conf.d/youtility-celery.conf`:

```ini
[program:y4_celery_w]
user=redmine
directory=/home/redmine/youtility4_icici/
command=/home/redmine/envs/youtility4/bin/celery -A intelliwiz_config worker -l info
autostart=true
autorestart=true
stdout_logfile=/var/log/youtility4/celery.log
stderr_logfile=/var/log/youtility4/celery.err.log

[program:y4_celery_b]
user=redmine
directory=/home/redmine/youtility4_icici/
command=/home/redmine/envs/youtility4/bin/celery -A intelliwiz_config beat -l info
autostart=true
autorestart=true
stdout_logfile=/var/log/youtility4/celery_b.log
stderr_logfile=/var/log/youtility4/celery_b.err.log

[group:y4_celery]
programs=y4_celery_w,y4_celery_b
```

### MQTT Configuration
Create `/etc/supervisor/conf.d/mqtt.conf`:

```ini
[program:mqtt]
command=/home/redmine/envs/youtility4/bin/python paho_client.py
directory=/home/redmine/youtility4_icici
user=redmine
autostart=true
autorestart=true
stderr_logfile=/var/log/mqtt.err.log
stdout_logfile=/var/log/mqtt.out.log
```

### Supervisor Management

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart all
```

## Redis Installation & Configuration

```bash
sudo add-apt-repository ppa:redislabs/redis
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

Configure Redis for production in `/etc/redis/redis.conf`:

```conf
supervised systemd
maxmemory 256mb
maxmemory-policy allkeys-lru
```

Verify Redis installation:

```bash
redis-cli ping  # Should return "PONG"
```

## Service Status Monitoring

Monitor all critical services:

```bash
# Supervisor processes
sudo supervisorctl status all

# Web server services
sudo systemctl status gunicorn.socket
sudo systemctl status gunicorn.service
sudo systemctl status nginx.service

# Database and cache
sudo systemctl status postgresql
sudo systemctl status redis-server
```

## Security Considerations

### Firewall Configuration

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw enable
```

### SSL/TLS Setup
Configure SSL certificates using Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

### Database Security
- Restrict PostgreSQL connections in pg_hba.conf
- Use strong passwords for database users
- Regular security updates

## Maintenance Commands

```bash
# Application updates
source /home/redmine/envs/youtility4/bin/activate
git pull origin main
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
sudo systemctl restart gunicorn
sudo supervisorctl restart all

# Log monitoring
tail -f /var/log/youtility4/celery.log
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```