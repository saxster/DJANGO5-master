#!/bin/bash
set -e

# Entrypoint script for Django Docker container
# Handles initialization tasks before starting the application

echo "==> Starting Django entrypoint script..."

# Wait for PostgreSQL to be ready
echo "==> Waiting for PostgreSQL..."
/usr/local/bin/wait-for-postgres.sh

# Run database migrations
if [ "$RUN_MIGRATIONS" = "true" ] || [ "$DJANGO_SETTINGS_MODULE" = "intelliwiz_config.settings.production" ]; then
    echo "==> Running database migrations..."
    python manage.py migrate --no-input
fi

# Collect static files (production only)
if [ "$DJANGO_SETTINGS_MODULE" = "intelliwiz_config.settings.production" ]; then
    echo "==> Collecting static files..."
    python manage.py collectstatic --no-input --clear
fi

# Create cache table if it doesn't exist
if [ "$DJANGO_SETTINGS_MODULE" = "intelliwiz_config.settings.production" ]; then
    echo "==> Ensuring cache tables exist..."
    python manage.py createcachetable || true
fi

# Initialize database (if needed)
if [ "$INITIALIZE_DB" = "true" ]; then
    echo "==> Initializing database..."
    python manage.py init_intelliwiz default || true
fi

echo "==> Entrypoint script completed successfully"
echo "==> Starting application: $@"

# Execute the main command (passed as arguments)
exec "$@"
