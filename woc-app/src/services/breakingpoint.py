"""Sync logic for pulling Breaking Point player stats into the local schema.

Shared by the `pull_breakingpoint_stats` management command and the dashboard's
manual "Update betting lines" button — both just need fresh results so that
existing betting lines can be evaluated against them.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime

from ..breakingpoint_client import BreakingPointClient
from ..models import (
    CompetitionStage,
    Game,
    GameMap,
    GameMode,
    GameSource,
    Player,
    PlayerGameStat,
    StageMapPoolEntry,
)
from ..pro_teams import PRO_TEAM_NAMES_BY_NORMALIZED_NAME, normalize_team_name

EVENT_TYPE_TO_SOURCE = {
    'Offline': GameSource.LAN,
    'LAN': GameSource.LAN,
    'Online': GameSource.ONLINE,
}


@dataclass
class BreakingPointSyncResult:
    fetched_count: int = 0
    games_created: int = 0
    players_created: int = 0
    stats_written: int = 0
    warnings: list[str] = field(default_factory=list)


@transaction.atomic
def sync_breakingpoint_stats(
    *,
    season: int,
    player_tags: list[str] | None = None,
    pro_teams_only: bool = False,
) -> BreakingPointSyncResult:
    """Pull Breaking Point player stats and upsert them into the local schema.

    Pass `player_tags` for an explicit player list, or `pro_teams_only=True` to
    pull every player in the season and keep only rows whose team matches the
    configured professional rosters (see `pro_teams.PRO_TEAM_NAMES`).
    """
    if not player_tags and not pro_teams_only:
        raise ValueError('At least one player tag is required.')

    client = BreakingPointClient()
    stats = client.fetch_player_stats(
        season_id=season,
        player_tags=None if pro_teams_only else player_tags,
    )

    result = BreakingPointSyncResult(fetched_count=len(stats))
    if not stats:
        scope = 'pro teams' if pro_teams_only else f'players={player_tags}'
        result.warnings.append(
            f'No player_stats rows found for season={season}, {scope}.'
        )
        return result

    modes_by_id = client.fetch_modes()
    maps_by_id = client.fetch_maps()
    events_by_id = client.fetch_events({row['event_id'] for row in stats})
    matches_by_id = client.fetch_matches({row['match_id'] for row in stats})

    team_ids = set()
    for match in matches_by_id.values():
        team_ids.add(match['team_1_id'])
        team_ids.add(match['team_2_id'])
    teams_by_id = client.fetch_teams(team_ids)

    rows_by_game = defaultdict(list)
    for row in stats:
        rows_by_game[row['game_id']].append(row)

    for game_id, rows in rows_by_game.items():
        first = rows[0]
        event = events_by_id.get(first['event_id'])
        match = matches_by_id.get(first['match_id'])
        if event is None or match is None:
            result.warnings.append(
                f'Skipping game {game_id}: missing event/match reference data.'
            )
            continue

        if pro_teams_only:
            rows = [
                row for row in rows
                if normalize_team_name(
                    teams_by_id.get(row['team_id'], {}).get('name', '')
                ) in PRO_TEAM_NAMES_BY_NORMALIZED_NAME
            ]
            if not rows:
                continue

        stage, _ = CompetitionStage.objects.update_or_create(
            name=event['name'],
            season=season,
            defaults={
                'start_date': parse_date(event['start_date']),
                'end_date': parse_date(event['end_date']),
            },
        )

        mode_name = modes_by_id.get(first['mode_id'], {}).get(
            'name', f"Mode {first['mode_id']}"
        )
        map_name = maps_by_id.get(first['map_id'], {}).get(
            'name', f"Map {first['map_id']}"
        )
        game_map, _ = GameMap.objects.get_or_create(name=map_name)
        mode, _ = GameMode.objects.get_or_create(name=mode_name)
        pool_entry, _ = StageMapPoolEntry.objects.get_or_create(
            stage=stage, game_map=game_map, mode=mode,
        )

        source = EVENT_TYPE_TO_SOURCE.get(first['event_type'])
        if source is None:
            source = GameSource.OTHER
            result.warnings.append(
                f"Game {game_id} has unrecognized event_type "
                f"{first['event_type']!r}; recorded as {GameSource.OTHER.label}."
            )

        # Opponent is resolved from the first target player found in this
        # game. If your --players list spans both teams in the same
        # match, this field can only hold one side's perspective — a
        # limitation of the existing single `opponent` column on Game.
        player_team_id = first['team_id']
        opponent_team_id = (
            match['team_2_id'] if player_team_id == match['team_1_id']
            else match['team_1_id']
        )
        opponent_name = teams_by_id.get(opponent_team_id, {}).get(
            'name', f'Team {opponent_team_id}'
        )

        event_date = parse_datetime(first['datetime'])

        try:
            game, created = Game.objects.update_or_create(
                source_id=game_id,
                defaults={
                    'pool_entry': pool_entry,
                    'source': source,
                    'opponent': opponent_name,
                    'event_date': event_date,
                },
            )
        except ValidationError:
            # Breaking Point sometimes reuses one event_id across multiple
            # real occurrences of a tournament, so the event's recorded date
            # window doesn't always cover every game filed under it.
            result.warnings.append(
                f"Skipping game {game_id}: {event_date} falls outside "
                f"{event['name']}'s recorded {stage.start_date}–{stage.end_date} window."
            )
            continue
        result.games_created += int(created)

        for row in rows:
            player, p_created = Player.objects.update_or_create(
                player_id=row['player_id'],
                defaults={'name': row['player_tag']},
            )
            result.players_created += int(p_created)

            team_name = teams_by_id.get(row['team_id'], {}).get(
                'name', f"Team {row['team_id']}"
            )
            PlayerGameStat.objects.update_or_create(
                player=player,
                game=game,
                defaults={
                    'kills': row['kills'] or 0,
                    'deaths': row['deaths'] or 0,
                    'team': team_name,
                },
            )
            result.stats_written += 1

    return result
