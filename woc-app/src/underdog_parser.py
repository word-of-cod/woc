"""Pure parsing functions for Underdog's denormalized market payload."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from django.utils.dateparse import parse_datetime

from .models import BettingStatType, MarketScope, MarketStatus


SUPPORTED_STAT_PATTERN = re.compile(r'^(kills|deaths)_on_game_([1-3])$')
GAMES_1_3_KILLS_STATS = {
    'kills_on_games_1_2_3',
    'kills_on_game_1_2_3',
}


@dataclass(frozen=True)
class ParsedUnderdogMarket:
    external_id: str
    stable_id: str
    external_player_id: str
    external_match_id: str
    player_name: str
    team_name: str
    opponent_name: str
    title: str
    display_stat: str
    market_scope: str
    series_game_number: int | None
    stat_type: str
    line: Decimal
    status: str
    scheduled_at: object
    expires_at: object
    source_updated_at: object
    raw_payload: dict


def _team_names(game: dict, appearance: dict) -> tuple[str, str]:
    title = str(game.get('full_team_names_title') or '')
    if ' @ ' not in title:
        return '', ''

    away_name, home_name = (part.strip() for part in title.split(' @ ', 1))
    appearance_team_id = str(appearance.get('team_id') or '')
    away_team_id = str(game.get('away_team_id') or '')
    home_team_id = str(game.get('home_team_id') or '')

    if appearance_team_id and appearance_team_id == away_team_id:
        return away_name, home_name
    if appearance_team_id and appearance_team_id == home_team_id:
        return home_name, away_name
    return '', ''


def parse_payload(payload: dict) -> tuple[list[ParsedUnderdogMarket], dict[str, int]]:
    appearances = {
        str(row.get('id')): row
        for row in payload.get('appearances', [])
        if row.get('id') is not None
    }
    players = {
        str(row.get('id')): row
        for row in payload.get('players', [])
        if row.get('id') is not None
    }
    games = {
        str(row.get('id')): row
        for row in payload.get('games', [])
        if row.get('id') is not None
    }

    counters = {
        'fetched': 0,
        'supported': 0,
        'skipped_not_cod': 0,
        'skipped_unsupported': 0,
        'skipped_invalid': 0,
    }
    parsed = []

    for raw in payload.get('over_under_lines', []):
        counters['fetched'] += 1
        over_under = raw.get('over_under') or {}
        appearance_stat = over_under.get('appearance_stat') or {}
        title = str(over_under.get('title') or '')

        if not title.lower().startswith('cod:'):
            counters['skipped_not_cod'] += 1
            continue

        raw_stat = str(appearance_stat.get('stat') or '').lower()
        stat_match = SUPPORTED_STAT_PATTERN.match(raw_stat)
        is_games_1_3_kills = raw_stat in GAMES_1_3_KILLS_STATS
        if stat_match is None and not is_games_1_3_kills:
            counters['skipped_unsupported'] += 1
            continue

        external_id = raw.get('id')
        appearance_id = appearance_stat.get('appearance_id')
        raw_line = raw.get('stat_value')
        if not external_id or not appearance_id or raw_line is None:
            counters['skipped_invalid'] += 1
            continue

        try:
            line = Decimal(str(raw_line))
        except (InvalidOperation, TypeError, ValueError):
            counters['skipped_invalid'] += 1
            continue

        appearance = appearances.get(str(appearance_id), {})
        external_player_id = str(appearance.get('player_id') or '')
        player = players.get(external_player_id, {})
        external_match_id = str(appearance.get('match_id') or '')
        game = games.get(external_match_id, {})

        player_name = str(player.get('last_name') or '').strip()
        if not player_name:
            player_name_match = re.match(
                r'^CoD:\s*(.+?)\s+(?:Kills|Deaths)\s+on Game',
                title,
                re.IGNORECASE,
            )
            player_name = (
                player_name_match.group(1).strip() if player_name_match else ''
            )

        if not player_name or not external_player_id or not external_match_id:
            counters['skipped_invalid'] += 1
            continue

        team_name, opponent_name = _team_names(game, appearance)
        raw_status = str(raw.get('status') or '').upper()
        valid_statuses = set(MarketStatus.values)
        status = raw_status if raw_status in valid_statuses else MarketStatus.UNKNOWN
        stat_type = (
            BettingStatType.KILLS
            if is_games_1_3_kills or stat_match.group(1) == 'kills'
            else BettingStatType.DEATHS
        )

        parsed.append(ParsedUnderdogMarket(
            external_id=str(external_id),
            stable_id=str(raw.get('stable_id') or ''),
            external_player_id=external_player_id,
            external_match_id=external_match_id,
            player_name=player_name,
            team_name=team_name,
            opponent_name=opponent_name,
            title=title,
            display_stat=str(appearance_stat.get('display_stat') or ''),
            market_scope=(
                MarketScope.GAMES_1_3
                if is_games_1_3_kills
                else MarketScope.SINGLE_GAME
            ),
            series_game_number=(
                None if is_games_1_3_kills else int(stat_match.group(2))
            ),
            stat_type=stat_type,
            line=line,
            status=status,
            scheduled_at=parse_datetime(str(game.get('scheduled_at') or '')),
            expires_at=parse_datetime(str(raw.get('expires_at') or '')),
            source_updated_at=parse_datetime(str(raw.get('updated_at') or '')),
            raw_payload=raw,
        ))
        counters['supported'] += 1

    return parsed, counters
