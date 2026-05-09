#!/bin/sh
set -e

mkdir -p logs

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Running migrations..."
python manage.py migrate --no-input

echo "Configuring site domain..."
python manage.py configure_site

echo "Creating cache table..."
python manage.py createcachetable

echo "Starting gunicorn..."
# GUNICORN_WORKERS: recommended formula is (2 × CPU cores) + 1.
# Default of 2 is safe for a single-core or memory-constrained host.
# GUNICORN_THREADS: gthread worker multiplies capacity without extra processes.
exec gunicorn config.wsgi \
    --workers "${GUNICORN_WORKERS:-2}" \
    --worker-class gthread \
    --threads "${GUNICORN_THREADS:-2}" \
    --bind "0.0.0.0:${PORT:-8000}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
