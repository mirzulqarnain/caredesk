#!/bin/sh
set -e
# Wait for PostgreSQL, then prepare the app
python - <<'PY'
import os, time, psycopg2
for i in range(30):
    try:
        psycopg2.connect(host=os.environ["DB_HOST"], port=os.environ.get("DB_PORT", "5432"),
                         dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
                         password=os.environ["DB_PASSWORD"]).close()
        break
    except Exception as e:
        print("waiting for database...", e); time.sleep(2)
PY
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py bootstrap
exec "$@"
