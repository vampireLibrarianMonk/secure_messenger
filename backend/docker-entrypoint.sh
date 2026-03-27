#!/bin/sh
set -eu

echo "[entrypoint] Applying database migrations..."
python manage.py migrate --noinput

if [ "${BOOTSTRAP_ADMIN_ENABLED:-0}" = "1" ]; then
  echo "[entrypoint] Running admin bootstrap..."
  python manage.py bootstrap_admin
else
  :
fi

echo "[entrypoint] Starting application: $*"
exec "$@"
