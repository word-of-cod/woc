"""Read-only client for Underdog Fantasy's public market feed."""
from __future__ import annotations

import requests
from django.conf import settings


class UnderdogError(RuntimeError):
    pass


class UnderdogClient:
    def __init__(self, *, base_url=None, state_config_id=None, session=None):
        self.base_url = (base_url or settings.UNDERDOG_BASE_URL).rstrip('/')
        self.state_config_id = (
            state_config_id or settings.UNDERDOG_STATE_CONFIG_ID
        )
        self.session = session or requests.Session()

    def fetch_esports_lines(self) -> dict:
        try:
            response = self.session.get(
                f'{self.base_url}/v1/over_under_lines',
                params={
                    'product': 'fantasy',
                    'sport_id': 'esports',
                    'state_config_id': self.state_config_id,
                },
                headers={
                    'Accept': 'application/json',
                    'User-Agent': 'word-of-cod-market-importer/1.0',
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            raise UnderdogError(f'Could not reach Underdog: {exc}') from exc

        if response.status_code != 200:
            raise UnderdogError(
                f'Underdog returned HTTP {response.status_code}: '
                f'{response.text[:300]}'
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise UnderdogError('Underdog returned invalid JSON.') from exc

        if not isinstance(payload, dict) or not isinstance(
            payload.get('over_under_lines'), list
        ):
            raise UnderdogError(
                'Underdog response is missing an over_under_lines list.'
            )

        return payload
