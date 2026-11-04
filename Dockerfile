FROM python:3.13.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Pick up patched packages (e.g. util-linux CVE fixes) already published for
# the base image's Debian release before installing anything else.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# pip is build-only. Removing it also removes its stale vendored SBOM,
# which otherwise reports vulnerabilities not present in the app packages.
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check \
    && rm -rf /usr/local/lib/python3.13/site-packages/pip \
        /usr/local/lib/python3.13/site-packages/pip-*.dist-info \
    && rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.13

COPY woc-app/ .

RUN python manage.py tailwind build
RUN python manage.py collectstatic --noinput

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Migrate (and optionally seed) at startup, since the database is only
# reachable at runtime, not during the build.
CMD ["sh", "-c", "python manage.py migrate --noinput && if [ \"$LOAD_TEST_DATA\" = \"true\" ]; then python manage.py seed_test_data; fi && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
