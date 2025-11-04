#!/bin/bash
set -e

# Wait for PostgreSQL to be ready before starting Django
# Prevents race conditions during container startup

host="${DB_HOST:-postgres}"
port="${DB_PORT:-5432}"
max_retries="${DB_MAX_RETRIES:-30}"
retry_interval="${DB_RETRY_INTERVAL:-2}"

echo "Waiting for PostgreSQL at $host:$port..."

retry_count=0
until nc -z "$host" "$port" || [ $retry_count -eq $max_retries ]; do
    retry_count=$((retry_count + 1))
    echo "PostgreSQL is unavailable (attempt $retry_count/$max_retries) - sleeping for $retry_interval seconds..."
    sleep $retry_interval
done

if [ $retry_count -eq $max_retries ]; then
    echo "ERROR: PostgreSQL did not become ready in time!"
    exit 1
fi

echo "PostgreSQL is up and accepting connections!"

# Additional check: try to connect with psql (if available)
if command -v pg_isready &> /dev/null; then
    retry_count=0
    until pg_isready -h "$host" -p "$port" -U "${DB_USER:-postgres}" || [ $retry_count -eq 10 ]; do
        retry_count=$((retry_count + 1))
        echo "Waiting for PostgreSQL to be ready (pg_isready check $retry_count/10)..."
        sleep 1
    done

    if [ $retry_count -eq 10 ]; then
        echo "WARNING: pg_isready checks failed, but proceeding anyway..."
    else
        echo "PostgreSQL is ready (verified with pg_isready)!"
    fi
fi

exit 0
