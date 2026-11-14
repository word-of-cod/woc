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

## Pulling data

Commands below are written with `/`. On Windows, use `\` in paths (`python woc-app\manage.py ...`) or just use the `just` recipe where one exists.

Pre-req: your `.env` has the Underdog settings (they're also in `.env.template`):

```bash
UNDERDOG_BASE_URL=https://api.underdogfantasy.com
UNDERDOG_STATE_CONFIG_ID=8176bf5b-d026-4be0-b6b8-02f1f101a8c6
```

### Local setup

1) Start the db: `docker compose up -d db`
2) Once it's healthy, run system checks: `just check`
3) Confirm models and migrations agree: `just check-migrations`
4) Apply migrations: `just migrate`, then verify with `python woc-app/manage.py showmigrations src`
5) Run the test suite: `just test`

### Underdog lines

1) Test the live API without writing to Postgres: `python woc-app/manage.py pull_underdog_lines --dry-run`
    - If it responds without an access token and shows individual stats for Games 1-3 (kills only), it's working
2) Import live Underdog markets: `python woc-app/manage.py pull_underdog_lines`
3) Inspect the data: `docker compose exec db psql -U woc -d woc`, then:
```sql
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
4) `\q` exits psql

### Breaking Point stats

Needs a fresh `BREAKINGPOINT_ACCESS_TOKEN` in `.env`.

```bash
python woc-app/manage.py pull_breakingpoint_stats --season 2026 --pro-teams
# or specific players
python woc-app/manage.py pull_breakingpoint_stats --season 2026 --players "Huke,Simp"
```

Inside the docker stack, prefix with `docker compose exec app` and drop the `woc-app/` (e.g. `docker compose exec app python manage.py pull_breakingpoint_stats --season 2026 --pro-teams`). After changing `.env`, run `docker compose up -d app` so the container picks up the new values.

### Run the site

1) Build the frontend: `just tailwind-build`
2) Run the server: `just runserver`
3) Open http://127.0.0.1:8000/ (dashboard) or http://127.0.0.1:8000/matches/
