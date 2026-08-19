# Production process roles

- **web:** `gunicorn -c gunicorn.conf.py build360.wsgi:application`
- **worker:** `celery -A build360 worker --loglevel=INFO`
- **scheduler:** `celery -A build360 beat --loglevel=INFO`
- **migration:** `python manage.py migrate --noinput`

Run exactly one scheduler. Scale web and worker processes independently. Local no-Docker
mode remains a developer convenience and is not a production topology.
