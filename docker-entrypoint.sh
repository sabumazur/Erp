#!/bin/sh
set -e

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Running migrations..."
python manage.py migrate --no-input

echo "Configuring site domain..."
python manage.py configure_site

echo "Starting gunicorn..."
exec gunicorn config.wsgi \
    --workers "${GUNICORN_WORKERS:-2}" \
    --bind "0.0.0.0:${PORT:-8000}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
