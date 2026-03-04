#!/bin/sh
set -e

mkdir -p /code/static_files /code/static_media/tmp

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
