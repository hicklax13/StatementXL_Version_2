#!/bin/bash
# StatementXL Database Backup Script
# Usage: ./backup.sh [output_dir]

set -e

# Configuration
BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="statementxl_backup_${TIMESTAMP}.sql.gz"

# Database connection (from environment or defaults)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-statementxl}"
DB_USER="${DB_USER:-statementxl}"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "Starting database backup..."
echo "  Database: $DB_NAME"
echo "  Host: $DB_HOST:$DB_PORT"
echo "  Output: $BACKUP_DIR/$BACKUP_FILE"

# Run pg_dump with compression
PGPASSWORD="${DB_PASSWORD:-statementxl}" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=custom \
    --compress=9 \
    --file="$BACKUP_DIR/$BACKUP_FILE"

# Verify backup
if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
    echo "Backup completed successfully!"
    echo "  File: $BACKUP_DIR/$BACKUP_FILE"
    echo "  Size: $SIZE"
    
    # Keep only last 7 daily backups
    cd "$BACKUP_DIR"
    ls -t statementxl_backup_*.sql.gz | tail -n +8 | xargs -r rm -f
    echo "Cleaned up old backups (keeping last 7)"
else
    echo "ERROR: Backup failed!"
    exit 1
fi
