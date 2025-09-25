#!/bin/bash

echo "Restarting Django5 services..."

# Stop the service first to avoid conflicts
echo "Stopping Gunicorn Django5 service..."
sudo systemctl stop gunicorn_django5.service

# Start socket first, then service (correct order)
echo "Starting Gunicorn Django5 socket..."
sudo systemctl start gunicorn_django5.socket

echo "Starting Gunicorn Django5 service..."
sudo systemctl start gunicorn_django5.service
echo "Restarting Django5 Supervisor services..."

sudo supervisorctl restart d5_celery_b d5_celery_w django5-mqtt

# Check both socket and service status
echo ""
echo "Checking Gunicorn socket status..."
sudo systemctl status gunicorn_django5.socket --no-pager
echo ""
echo "Checking Gunicorn service status..."
sudo systemctl status gunicorn_django5.service --no-pager

# Reload Nginx (safer than restart)
echo "Reloading Nginx..."
sudo systemctl reload nginx

echo ""
echo "Checking Django5 Supervisor services..."
sudo supervisorctl status d5_celery_b d5_celery_w django5-mqtt

# Test nginx configuration
echo "Testing Nginx configuration..."
sudo nginx -t

echo "Services restarted successfully!"
echo ""
echo "To clear browser cache and see the new UI:"
echo "1. Press Ctrl+Shift+Delete in your browser to clear all cache"
echo "2. Or use Ctrl+F5 for a hard refresh on the page"
echo "3. In Chrome DevTools: Right-click refresh button > 'Empty Cache and Hard Reload'"

