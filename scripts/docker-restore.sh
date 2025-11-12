#!/bin/bash
# Docker Restore Script for IntelliWiz
# Restores PostgreSQL database and media files from backups

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BACKUP_DIR="./backups"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

echo -e "${GREEN}==> IntelliWiz Docker Restore Script${NC}"
echo ""

# Function to list available backups
list_backups() {
    echo -e "${YELLOW}==> Available database backups:${NC}"
    echo ""

    if [ ! -d "$BACKUP_DIR/postgres" ] || [ -z "$(ls -A $BACKUP_DIR/postgres)" ]; then
        echo -e "${RED}No backups found in $BACKUP_DIR/postgres${NC}"
        exit 1
    fi

    ls -lh "$BACKUP_DIR/postgres"/*.sql.gz 2>/dev/null || {
        echo -e "${RED}No .sql.gz backup files found${NC}"
        exit 1
    }
    echo ""
}

# Function to restore database
restore_database() {
    local BACKUP_FILE=$1

    if [ ! -f "$BACKUP_FILE" ]; then
        echo -e "${RED}ERROR: Backup file not found: $BACKUP_FILE${NC}"
        exit 1
    fi

    echo -e "${YELLOW}==> Restoring database from: $BACKUP_FILE${NC}"
    echo -e "${RED}WARNING: This will REPLACE the current database!${NC}"
    echo -e "${RED}Press Ctrl+C within 10 seconds to cancel...${NC}"
    sleep 10

    # Get database credentials from .env.prod
    if [ -f .env.prod ]; then
        export $(cat .env.prod | grep -v '^#' | xargs)
    else
        echo -e "${RED}ERROR: .env.prod file not found!${NC}"
        exit 1
    fi

    # Check if database container is running
    if ! docker-compose -f "$COMPOSE_FILE" ps postgres | grep -q "Up"; then
        echo -e "${RED}ERROR: PostgreSQL container is not running!${NC}"
        echo "Start it with: docker-compose -f $COMPOSE_FILE up -d postgres"
        exit 1
    fi

    # Drop existing connections
    echo -e "${YELLOW}==> Terminating existing database connections...${NC}"
    docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$DB_USER" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" || true

    # Drop and recreate database
    echo -e "${YELLOW}==> Dropping and recreating database...${NC}"
    docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
    docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

    # Enable PostGIS extension
    echo -e "${YELLOW}==> Enabling PostGIS extension...${NC}"
    docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS postgis;"

    # Restore database
    echo -e "${YELLOW}==> Restoring database data...${NC}"
    gunzip -c "$BACKUP_FILE" | docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_restore \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --no-owner \
        --no-acl \
        --verbose

    echo -e "${GREEN}✓ Database restored successfully${NC}"
}

# Function to restore media files
restore_media() {
    local MEDIA_BACKUP=$1

    if [ ! -f "$MEDIA_BACKUP" ]; then
        echo -e "${RED}ERROR: Media backup file not found: $MEDIA_BACKUP${NC}"
        exit 1
    fi

    echo -e "${YELLOW}==> Restoring media files from: $MEDIA_BACKUP${NC}"
    echo -e "${RED}WARNING: This will REPLACE current media files!${NC}"
    echo -e "${RED}Press Ctrl+C within 5 seconds to cancel...${NC}"
    sleep 5

    # Restore media volume
    docker run --rm \
        -v intelliwiz_media:/data \
        -v "$(pwd)/$(dirname $MEDIA_BACKUP)":/backup \
        alpine \
        sh -c "rm -rf /data/* && tar xzf /backup/$(basename $MEDIA_BACKUP) -C /data"

    echo -e "${GREEN}✓ Media files restored successfully${NC}"
}

# Function to restore volume
restore_volume() {
    local VOLUME_NAME=$1
    local BACKUP_FILE=$2

    if [ ! -f "$BACKUP_FILE" ]; then
        echo -e "${RED}ERROR: Volume backup file not found: $BACKUP_FILE${NC}"
        exit 1
    fi

    echo -e "${YELLOW}==> Restoring volume $VOLUME_NAME from: $BACKUP_FILE${NC}"

    docker run --rm \
        -v "$VOLUME_NAME":/data \
        -v "$(pwd)/$(dirname $BACKUP_FILE)":/backup \
        alpine \
        sh -c "rm -rf /data/* && tar xzf /backup/$(basename $BACKUP_FILE) -C /data"

    echo -e "${GREEN}✓ Volume $VOLUME_NAME restored successfully${NC}"
}

# Interactive mode
interactive_restore() {
    echo -e "${GREEN}==> Interactive Restore Mode${NC}"
    echo ""

    # List backups
    list_backups

    echo ""
    echo -e "${YELLOW}Select restore option:${NC}"
    echo "1) Restore database only"
    echo "2) Restore media files only"
    echo "3) Restore database + media files"
    echo "4) Full restore (database + media + volumes)"
    echo "5) Cancel"
    echo ""
    read -p "Enter option (1-5): " OPTION

    case $OPTION in
        1)
            read -p "Enter database backup filename: " DB_FILE
            restore_database "$BACKUP_DIR/postgres/$DB_FILE"
            ;;
        2)
            read -p "Enter media backup filename: " MEDIA_FILE
            restore_media "$BACKUP_DIR/media/$MEDIA_FILE"
            ;;
        3)
            read -p "Enter database backup filename: " DB_FILE
            read -p "Enter media backup filename: " MEDIA_FILE
            restore_database "$BACKUP_DIR/postgres/$DB_FILE"
            restore_media "$BACKUP_DIR/media/$MEDIA_FILE"
            ;;
        4)
            read -p "Enter backup timestamp (YYYYMMDD_HHMMSS): " TIMESTAMP
            restore_database "$BACKUP_DIR/postgres/backup_${TIMESTAMP}.sql.gz"
            restore_media "$BACKUP_DIR/media/media_${TIMESTAMP}.tar.gz"
            restore_volume "intelliwiz_redis_data" "$BACKUP_DIR/volumes/intelliwiz_redis_data_${TIMESTAMP}.tar.gz"
            echo -e "${GREEN}✓ Full restore completed${NC}"
            ;;
        5)
            echo "Cancelled."
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            exit 1
            ;;
    esac

    echo ""
    echo -e "${GREEN}===========================================================${NC}"
    echo -e "${GREEN}Restore completed successfully!${NC}"
    echo -e "${GREEN}===========================================================${NC}"
}

# Command line mode
if [ $# -eq 0 ]; then
    interactive_restore
elif [ $# -eq 2 ]; then
    case $1 in
        --database|-d)
            restore_database "$2"
            ;;
        --media|-m)
            restore_media "$2"
            ;;
        *)
            echo "Usage: $0 [--database|-d backup.sql.gz] [--media|-m backup.tar.gz]"
            echo "Or run without arguments for interactive mode"
            exit 1
            ;;
    esac
else
    echo "Usage: $0 [--database|-d backup.sql.gz] [--media|-m backup.tar.gz]"
    echo "Or run without arguments for interactive mode"
    exit 1
fi
