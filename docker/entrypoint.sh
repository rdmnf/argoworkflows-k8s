#!/bin/sh
set -e

cd /app

if [ ! -d .venv ] || [ ! -f .venv/pyvenv.cfg ]; then
  echo "Creating Python environment..."
  uv sync --frozen --no-dev
fi

echo "Waiting for Keycloak at ${KEYCLOAK_INTERNAL_URL:-$KEYCLOAK_URL}..."
until curl -sf "${KEYCLOAK_INTERNAL_URL:-$KEYCLOAK_URL}/realms/${KEYCLOAK_REALM:-awf}" >/dev/null 2>&1; do
  sleep 2
done

echo "Running database migrations..."
uv run python manage.py migrate --noinput

if [ "$1" = "runserver" ]; then
  shift
  echo "Starting Django development server..."
  exec uv run python manage.py runserver 0.0.0.0:8000 "$@"
fi

exec "$@"
