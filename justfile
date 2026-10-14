python := if os() == "windows" { ".venv/Scripts/python.exe" } else { ".venv/bin/python" }

# run Django's system checks
check:
    {{python}} woc-app/manage.py check

# fail if models have changes not yet captured in a migration
check-migrations:
    {{python}} woc-app/manage.py makemigrations --check --dry-run

# run the test suite
test:
    {{python}} woc-app/manage.py test src --verbosity 2

# build and start the stack in the background
up:
    #!{{python}}
    import pathlib, shutil, subprocess, sys

    if not pathlib.Path(".env").exists():
        shutil.copy(".env.template", ".env")
        print(".env not found — copied from .env.template. Fill in real values, then re-run.")
        sys.exit(1)

    subprocess.run(["docker", "compose", "up", "--build", "-d"], check=True)

# stop and remove the stack's containers
down:
    docker compose down

# rebuild the app image from scratch (no layer cache) and restart
rebuild:
    docker compose build --no-cache app
    docker compose up -d

# follow logs from the app container
logs:
    docker compose logs -f app

# run the Django dev server locally (outside docker)
runserver:
    {{python}} woc-app/manage.py runserver

# apply database migrations locally
migrate:
    {{python}} woc-app/manage.py migrate

# run the edge-finding algorithm against current Underdog markets
find-edges:
    {{python}} woc-app/manage.py find_edges

# install/update the tailwind toolchain (node deps)
tailwind-install:
    {{python}} woc-app/manage.py tailwind install

# watch and rebuild tailwind css on change (dev)
tailwind-start:
    {{python}} woc-app/manage.py tailwind start

# rebuild tailwind css once (matches the Dockerfile build step)
tailwind-build:
    {{python}} woc-app/manage.py tailwind build
