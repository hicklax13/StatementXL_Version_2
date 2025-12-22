#!/bin/bash
# StatementXL Database Restore Script
# Usage: ./restore.sh <backup_file>

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 ./backups/statementxl_backup_20241222_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

# Database connection
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-statementxl}"
DB_USER="${DB_USER:-statementxl}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will restore the database from backup."
echo "  Backup: $BACKUP_FILE"
echo "  Database: $DB_NAME @ $DB_HOST:$DB_PORT"
echo ""
read -p "Are you sure? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo "Starting database restore..."

# Restore from backup
PGPASSWORD="${DB_PASSWORD:-statementxl}" pg_restore \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --clean \
    --if-exists \
    "$BACKUP_FILE"

echo "Restore completed successfully!"
