FROM python:3.13.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
# These are inherited/tooling packages reported by the container vulnerability
# scan. Install fixed versions explicitly before the application dependencies so
# the final runtime image cannot retain the vulnerable releases from a base or
# cached layer.
RUN python -m pip install --no-cache-dir --upgrade \
        "setuptools>=78.1.1" \
        "msgpack>=1.2.1" \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check

COPY woc-app/ .

RUN python manage.py tailwind build
RUN python manage.py collectstatic --noinput

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
