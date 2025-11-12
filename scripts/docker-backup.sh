#!/bin/bash
# Docker Backup Script for IntelliWiz
# Backs up PostgreSQL database and media files

set -e  # Exit on error

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}==> IntelliWiz Docker Backup Script${NC}"
echo -e "${GREEN}==> Timestamp: $TIMESTAMP${NC}"
echo ""

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR/postgres"
mkdir -p "$BACKUP_DIR/media"
mkdir -p "$BACKUP_DIR/volumes"

# Function to backup PostgreSQL database
backup_database() {
    echo -e "${YELLOW}==> Backing up PostgreSQL database...${NC}"

    # Get database credentials from .env.prod
    if [ -f .env.prod ]; then
        export $(cat .env.prod | grep -v '^#' | xargs)
    else
        echo -e "${RED}ERROR: .env.prod file not found!${NC}"
        exit 1
    fi

    BACKUP_FILE="$BACKUP_DIR/postgres/backup_${TIMESTAMP}.sql"

    # Create backup using pg_dump inside postgres container
    docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_dump \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --verbose \
        > "$BACKUP_FILE"

    # Compress the backup
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"

    # Get file size
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}✓ Database backup completed: $BACKUP_FILE ($SIZE)${NC}"
}

# Function to backup media files
backup_media() {
    echo -e "${YELLOW}==> Backing up media files...${NC}"

    MEDIA_BACKUP="$BACKUP_DIR/media/media_${TIMESTAMP}.tar.gz"

    # Backup media volume
    docker run --rm \
        -v intelliwiz_media:/data:ro \
        -v "$(pwd)/$BACKUP_DIR/media":/backup \
        alpine \
        tar czf "/backup/media_${TIMESTAMP}.tar.gz" -C /data .

    # Get file size
    SIZE=$(du -h "$MEDIA_BACKUP" | cut -f1)
    echo -e "${GREEN}✓ Media backup completed: $MEDIA_BACKUP ($SIZE)${NC}"
}

# Function to backup all Docker volumes
backup_volumes() {
    echo -e "${YELLOW}==> Backing up all Docker volumes...${NC}"

    VOLUMES=("intelliwiz_postgres_data" "intelliwiz_redis_data")

    for VOLUME in "${VOLUMES[@]}"; do
        echo -e "${YELLOW}  -> Backing up $VOLUME...${NC}"
        VOLUME_BACKUP="$BACKUP_DIR/volumes/${VOLUME}_${TIMESTAMP}.tar.gz"

        docker run --rm \
            -v "$VOLUME":/data:ro \
            -v "$(pwd)/$BACKUP_DIR/volumes":/backup \
            alpine \
            tar czf "/backup/$(basename $VOLUME)_${TIMESTAMP}.tar.gz" -C /data .

        SIZE=$(du -h "$VOLUME_BACKUP" | cut -f1)
        echo -e "${GREEN}  ✓ $VOLUME backed up ($SIZE)${NC}"
    done
}

# Function to create backup manifest
create_manifest() {
    echo -e "${YELLOW}==> Creating backup manifest...${NC}"

    MANIFEST_FILE="$BACKUP_DIR/manifest_${TIMESTAMP}.txt"

    cat > "$MANIFEST_FILE" <<EOF
IntelliWiz Docker Backup Manifest
Backup Date: $(date)
Timestamp: $TIMESTAMP

Environment: ${ENVIRONMENT:-production}
Docker Compose File: $COMPOSE_FILE

Database Backup:
- File: backups/postgres/backup_${TIMESTAMP}.sql.gz
- Database: $DB_NAME
- User: $DB_USER

Media Backup:
- File: backups/media/media_${TIMESTAMP}.tar.gz

Volume Backups:
- postgres_data: backups/volumes/intelliwiz_postgres_data_${TIMESTAMP}.tar.gz
- redis_data: backups/volumes/intelliwiz_redis_data_${TIMESTAMP}.tar.gz

Backup completed at: $(date)
EOF

    echo -e "${GREEN}✓ Manifest created: $MANIFEST_FILE${NC}"
}

# Function to cleanup old backups (keep last 7 days)
cleanup_old_backups() {
    echo -e "${YELLOW}==> Cleaning up old backups (keeping last 7 days)...${NC}"

    find "$BACKUP_DIR/postgres" -name "*.sql.gz" -type f -mtime +7 -delete || true
    find "$BACKUP_DIR/media" -name "*.tar.gz" -type f -mtime +7 -delete || true
    find "$BACKUP_DIR/volumes" -name "*.tar.gz" -type f -mtime +7 -delete || true
    find "$BACKUP_DIR" -name "manifest_*.txt" -type f -mtime +7 -delete || true

    echo -e "${GREEN}✓ Old backups cleaned up${NC}"
}

# Main execution
main() {
    echo -e "${YELLOW}==> Starting backup process...${NC}"
    echo ""

    # Perform backups
    backup_database
    echo ""
    backup_media
    echo ""
    backup_volumes
    echo ""
    create_manifest
    echo ""
    cleanup_old_backups
    echo ""

    echo -e "${GREEN}===========================================================${NC}"
    echo -e "${GREEN}Backup completed successfully!${NC}"
    echo -e "${GREEN}Backup timestamp: $TIMESTAMP${NC}"
    echo -e "${GREEN}Backup location: $BACKUP_DIR${NC}"
    echo -e "${GREEN}===========================================================${NC}"
}

# Run main function
main
