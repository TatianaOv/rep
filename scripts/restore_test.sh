#!/usr/bin/env bash
set -euo pipefail

# One-off sanity check for the backup pipeline: restores the most recent
# backups/*.gz into a scratch copy and serves the web panel against it
# in a throwaway container, so you can actually look at it in a browser
# instead of just trusting that ".gz file exists" means "backup works".
#
# Does NOT touch the running bot or its real database — only reads a
# copy of the backup file, and mounts that copy read-write for a
# separate container on a separate port.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$REPO_DIR/backups}"
RESTORE_DIR="${RESTORE_DIR:-$REPO_DIR/restore_test}"
PORT="${PORT:-8001}"
IMAGE="${IMAGE:-bot-bot:latest}"

latest="$(ls -t "$BACKUP_DIR"/bot_*.db.gz 2>/dev/null | head -1)"
if [ -z "$latest" ]; then
    echo "restore_test.sh: no backups found in $BACKUP_DIR" >&2
    exit 1
fi

echo "Восстанавливаю из: $latest"
rm -rf "$RESTORE_DIR"
mkdir -p "$RESTORE_DIR"
gunzip -c "$latest" > "$RESTORE_DIR/bot.db"

docker rm -f restore-test >/dev/null 2>&1 || true

docker run --rm -d \
    --name restore-test \
    --env-file "$REPO_DIR/.env" \
    -e DATABASE_URL="sqlite+aiosqlite:////app/data/bot.db" \
    -v "$RESTORE_DIR:/app/data" \
    -p "127.0.0.1:$PORT:8000" \
    "$IMAGE" \
    uvicorn app.web.server:create_app --factory --host 0.0.0.0 --port 8000 >/dev/null

echo
echo "Готово. Тестовая панель (с восстановленными данными) запущена на порту $PORT."
echo "Логин и пароль — те же, что в вашем .env."
echo
echo "Если вы на сервере по SSH — откройте туннель с компьютера:"
echo "    ssh -L $PORT:localhost:$PORT root@<IP сервера>"
echo "и зайдите на http://localhost:$PORT — проверьте, что расписание и ДЗ на месте."
echo
echo "Когда закончите проверку:"
echo "    docker stop restore-test"
echo "    rm -rf '$RESTORE_DIR'"
