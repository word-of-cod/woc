"""Read-only client for the Breaking Point (breakingpoint.gg) stats API.

Breaking Point exposes its Postgres tables directly through PostgREST, so
this client is just auth headers + pagination + simple `in.(...)` filters
on top of plain HTTP GETs. There is no bulk/mirror export here on purpose:
callers ask for specific players and a specific season.
"""
from __future__ import annotations

import requests
from django.conf import settings

PAGE_SIZE = 1000


class BreakingPointError(RuntimeError):
    pass


class BreakingPointClient:
    def __init__(self, *, base_url=None, api_key=None, access_token=None, session=None):
        self.base_url = (base_url or settings.BREAKINGPOINT_BASE_URL).rstrip('/')
        self.api_key = api_key or settings.BREAKINGPOINT_API_KEY
        self.access_token = access_token or settings.BREAKINGPOINT_ACCESS_TOKEN
        self.session = session or requests.Session()

        if not self.api_key or not self.access_token:
            raise BreakingPointError(
                'BREAKINGPOINT_API_KEY and BREAKINGPOINT_ACCESS_TOKEN must be set in '
                '.env. The access token expires roughly hourly — grab a fresh one '
                'from the site before each run.'
            )

    def _headers(self):
        return {
            'apikey': self.api_key,
            'Authorization': f'Bearer {self.access_token}',
        }

    def fetch_all(self, table: str, params: dict) -> list[dict]:
        rows = []
        start = 0
        while True:
            headers = self._headers()
            headers['Range-Unit'] = 'items'
            headers['Range'] = f'{start}-{start + PAGE_SIZE - 1}'
            response = self.session.get(
                f'{self.base_url}/{table}',
                params=params,
                headers=headers,
                timeout=30,
            )
            if response.status_code == 401:
                raise BreakingPointError(
                    'Breaking Point rejected the access token (401). It likely '
                    'expired — grab a fresh one from the site and update '
                    'BREAKINGPOINT_ACCESS_TOKEN in .env.'
                )
            response.raise_for_status()
            page = response.json()
            rows.extend(page)
            if len(page) < PAGE_SIZE:
                break
            start += PAGE_SIZE
        return rows

    def fetch_player_stats(self, *, season_id: int, player_tags: list[str]) -> list[dict]:
        tags = ','.join(f'"{tag}"' for tag in player_tags)
        params = {
            'season_id': f'eq.{season_id}',
            'player_tag': f'in.({tags})',
            'select': ','.join([
                'game_id', 'player_id', 'player_tag', 'team_id', 'match_id',
                'event_id', 'mode_id', 'map_id', 'datetime', 'event_type',
                'season_id', 'kills', 'deaths', 'damage', 'assists',
            ]),
        }
        return self.fetch_all('player_stats', params)

    def fetch_modes(self) -> dict[int, dict]:
        rows = self.fetch_all('modes', {'select': 'id,name,short_name'})
        return {row['id']: row for row in rows}

    def fetch_maps(self) -> dict[int, dict]:
        rows = self.fetch_all('maps', {'select': 'id,name'})
        return {row['id']: row for row in rows}

    def fetch_events(self, event_ids) -> dict[int, dict]:
        if not event_ids:
            return {}
        ids = ','.join(str(i) for i in sorted(set(event_ids)))
        rows = self.fetch_all(
            'events',
            {'id': f'in.({ids})', 'select': 'id,name,start_date,end_date'},
        )
        return {row['id']: row for row in rows}

    def fetch_matches(self, match_ids) -> dict[int, dict]:
        if not match_ids:
            return {}
        ids = ','.join(str(i) for i in sorted(set(match_ids)))
        rows = self.fetch_all(
            'matches',
            {'id': f'in.({ids})', 'select': 'id,team_1_id,team_2_id'},
        )
        return {row['id']: row for row in rows}

    def fetch_teams(self, team_ids) -> dict[int, dict]:
        if not team_ids:
            return {}
        ids = ','.join(str(i) for i in sorted(set(team_ids)))
        rows = self.fetch_all(
            'teams',
            {'id': f'in.({ids})', 'select': 'id,name'},
        )
        return {row['id']: row for row in rows}
