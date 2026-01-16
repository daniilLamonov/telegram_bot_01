#!/bin/bash
set -e

alembic upgrade head
echo "Migrations completed successfully!"

python -u main.py