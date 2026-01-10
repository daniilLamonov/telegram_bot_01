#!/bin/bash
set -e

echo "Waiting for database to be ready..."
sleep 3

echo "Running database migrations..."
alembic upgrade head

echo "Migrations completed successfully!"
echo "Current migration version:"
alembic current

echo "Starting application..."
exec "$@"
