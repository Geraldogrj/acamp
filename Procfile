web: python manage.py migrate --noinput && (python manage.py createsuperuser --noinput || true) && gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8080}
