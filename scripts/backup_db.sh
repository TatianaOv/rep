#!/usr/bin/env bash
set -euo pipefail

# Safe hot-backup of the bot's SQLite database (uses `sqlite3 .backup`,
# so it's consistent even while the bot is writing to it).
#
# Defaults assume this script lives in <repo>/scripts/ and the compose
# setup mounts ./data:/app/data, i.e. the db is at <repo>/data/bot.db.
# Override via env vars if your layout differs.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_PATH="${DB_PATH:-$SCRIPT_DIR/../data/bot.db}"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/../backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"

if [ ! -f "$DB_PATH" ]; then
    echo "backup_db.sh: database not found at $DB_PATH" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

timestamp="$(date +%Y-%m-%d_%H-%M-%S)"
dest="$BACKUP_DIR/bot_$timestamp.db"

sqlite3 "$DB_PATH" ".backup '$dest'"
gzip "$dest"

echo "backup_db.sh: saved $dest.gz"

find "$BACKUP_DIR" -name 'bot_*.db.gz' -mtime "+$KEEP_DAYS" -print -delete
