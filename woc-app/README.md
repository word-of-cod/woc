# The Word of COD

## Team Information
- Samarth Vohra
- Jack Rauch
- Connor Searcy (just happy to be here)

## `just` commands

We use [`just`](https://github.com/casey/just) as a cross-platform task runner (works the same on Mac and Windows — no more separate `run.sh`/`run.bat`).

Install it once:
- Mac: `brew install just`
- Windows: `winget install --id Casey.Just` (or `choco install just` / `scoop install just`)

Recipes (run from the repo root):

| Command | What it does |
|---|---|
| `just up` | Build (if needed) and start the full stack (db + app) in the background via docker compose. Bootstraps `.env` from `.env.template` on first run. |
| `just down` | Stop and remove the stack's containers. |
| `just rebuild` | Rebuild the app image from scratch (`--no-cache`) and restart. Use after dependency changes. |
| `just logs` | Follow logs from the app container. |
| `just runserver` | Run the Django dev server locally (outside docker), using the project's venv. |
| `just migrate` | Apply database migrations locally. |
| `just check` | Run Django's system checks. |
| `just check-migrations` | Fail if models have changes not yet captured in a migration. |
| `just test` | Run the test suite (`manage.py test src`). |
| `just tailwind-install` | Install/update the Tailwind toolchain (node deps). |
| `just tailwind-start` | Watch and rebuild Tailwind CSS on change (dev). |
| `just tailwind-build` | Rebuild Tailwind CSS once (matches the Dockerfile build step). |
| `just find-edges` | Run the algorithm with your local data. |

Run `just --list` at any time to see this list from the CLI.

## Pulling Underdog Stats 
Pre-Req: Ensure your .env shows the below:

```bash
UNDERDOG_BASE_URL=https://api.underdogfantasy.com
UNDERDOG_STATE_CONFIG_ID=8176bf5b-d026-4be0-b6b8-02f1f101a8c6
```

### On Windows:

1) Using `docker compose up -d db` start the db
2) Once healthy check the migration using `python woc-app\manage.py check`
3) Confirm the committed models and migrations agree: `python woc-app\manage.py makemigrations src --check --dry-run`
4) Apply migrations: `python woc-app\manage.py sqlmigrate src 0007`
5) Apply all migrations: `python woc-app\manage.py migrate`
6) Verify status: `python woc-app\manage.py showmigrations src`
7) Run compete test suite: `python woc-app\manage.py test src.tests --verbosity 2`
8) Test live API without modifying the PostgreSQL: `python woc-app\manage.py pull_underdog_lines --dry-run`
    - If it properly responds without an access token and has individual stats for Games1-3 (kills only), it is running properly
9) Import live Underdog markets: `python woc-app\manage.py pull_underdog_lines`
10) Enter into the DB and check out the new data: `docker compose exec db psql -U woc -d woc`
11) Execute the following to grab the new data:
```bash
SELECT
    player_name,
    team_name,
    opponent_name,
    series_game_number,
    stat_type,
    line,
    status,
    resolution_status,
    scheduled_at
FROM underdog_markets
ORDER BY scheduled_at, player_name, series_game_number;
```
12) Use `\q` to exit the postgres terminal
13) Build the new frontend: `python woc-app\manage.py tailwind build` (or `just tailwind-build`)
14) Run the server: `python woc-app\manage.py runserver` (or `just runserver`)
15) Navigate to: http://127.0.0.1:8000/matches/


### On Mac:

1) Using `docker compose up -d db` start the db
2) Once healthy check the migration using `python woc-app/manage.py check`
3) Confirm the committed models and migrations agree: `python woc-app/manage.py makemigrations src --check --dry-run`
4) Apply migrations: `python woc-app/manage.py sqlmigrate src 0007`
5) Apply all migrations: `python woc-app/manage.py migrate`
6) Verify status: `python woc-app/manage.py showmigrations src`
7) Run compete test suite: `python woc-app/manage.py test src.tests --verbosity 2`
8) Test live API without modifying the PostgreSQL: `python woc-app/manage.py pull_underdog_lines --dry-run`
    - If it properly responds without an access token and has individual stats for Games1-3 (kills only), it is running properly
9) Import live Underdog markets: `python woc-app/manage.py pull_underdog_lines`
10) Enter into the DB and check out the new data: `docker compose exec db psql -U woc -d woc`
11) Execute the following to grab the new data:
```bash
SELECT
    player_name,
    team_name,
    opponent_name,
    series_game_number,
    stat_type,
    line,
    status,
    resolution_status,
    scheduled_at
FROM underdog_markets
ORDER BY scheduled_at, player_name, series_game_number;
```
12) Use `\q` to exit the postgres terminal
13) Build the new frontend: `python woc-app/manage.py tailwind build` (or `just tailwind-build`)
14) Run the server: `python woc-app/manage.py runserver` (or `just runserver`)
15) Navigate to: http://127.0.0.1:8000/matches/