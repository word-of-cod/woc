from datetime import timedelta

from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from .models import (
    BettingLine,
    CompetitionStage,
    Game,
    Player,
    PlayerGameStat,
    ResolutionStatus,
    StageMapPoolEntry,
    UnderdogMarket,
)


def get_player(*, player_id: int) -> Player:
    return Player.objects.get(player_id=player_id)

def get_game(*, game_id: int) -> Game:
    return (
        Game.objects
        .select_related(
            'pool_entry',
            'pool_entry__stage',
            'pool_entry__game_map',
            'pool_entry__mode',
        )

        .get(game_id=game_id)
    )

def recent_games(*, limit: int = 20) -> QuerySet[Game]:
    return (
        Game.objects
        .filter(source_id__isnull=False)
        .select_related(
            'pool_entry',
            'pool_entry__stage',
            'pool_entry__game_map',
            'pool_entry__mode',
        )
        .prefetch_related(
            'player_stats__player',
            'betting_lines__player',
        )
        .order_by('-event_date', '-game_id')[:limit]
    )


def games_for_matches_page() -> QuerySet[Game]:
    return (
        Game.objects
        .filter(source_id__isnull=False)
        .select_related(
            'pool_entry',
            'pool_entry__stage',
            'pool_entry__game_map',
            'pool_entry__mode',
        )
        .prefetch_related(
            Prefetch(
                'player_stats',
                queryset=PlayerGameStat.objects.select_related('player').order_by(
                    '-kills',
                    'deaths',
                    'player__name',
                ),
            ),
            Prefetch(
                'betting_lines',
                queryset=BettingLine.objects.select_related('player').order_by(
                    'market',
                    'player__name',
                ),
            ),
            Prefetch(
                'underdog_markets',
                queryset=UnderdogMarket.objects.filter(
                    resolution_status=ResolutionStatus.RESOLVED,
                ).select_related('player').order_by(
                    'player__name',
                    'stat_type',
                ),
            ),
        )
        .order_by('-event_date', '-game_id')
    )


def live_underdog_markets() -> QuerySet[UnderdogMarket]:
    return (
        UnderdogMarket.objects
        .filter(
            status='ACTIVE',
            scheduled_at__gte=timezone.now() - timedelta(hours=6),
        )
        .select_related('player', 'game')
        .order_by('scheduled_at', 'external_match_id', 'player_name', 'series_game_number')
    )

def upcoming_match_schedule(*, limit: int = 8) -> list[dict]:
    rows = (
        UnderdogMarket.objects
        .filter(scheduled_at__gte=timezone.now())
        .order_by('scheduled_at', 'external_match_id')
        .values('external_match_id', 'team_name', 'opponent_name', 'scheduled_at')[:200]
    )
    matches = []
    seen_match_ids = set()
    for row in rows:
        if row['external_match_id'] in seen_match_ids:
            continue
        seen_match_ids.add(row['external_match_id'])
        matches.append(row)
        if len(matches) >= limit:
            break
    return matches


def latest_season() -> int | None:
    return (
        CompetitionStage.objects
        .order_by('-season')
        .values_list('season', flat=True)
        .first()
    )


def known_player_tags() -> list[str]:
    return list(Player.objects.order_by('name').values_list('name', flat=True))


def games_for_stage(
    *,
    stage_id: int,
) -> QuerySet[Game]:
    return (
        Game.objects
        .filter(pool_entry__stage_id=stage_id)
        .select_related(
            'pool_entry',
            'pool_entry__stage',
            'pool_entry__game_map',
            'pool_entry__mode',
        )
        .order_by('-event_date', '-game_id')
    )


def map_pool_for_stage(
    *,
    stage_id: int,
) -> QuerySet[StageMapPoolEntry]:
    return (
        StageMapPoolEntry.objects
        .filter(stage_id=stage_id)
        .select_related(
            'stage',
            'game_map',
            'mode',
        )
        .order_by(
            'mode__name',
            'game_map__name',
        )
    )


def stats_for_game(
    *,
    game_id: int,
) -> QuerySet[PlayerGameStat]:
    return (
        PlayerGameStat.objects
        .filter(game_id=game_id)
        .select_related(
            'player',
            'game',
            'game__pool_entry',
            'game__pool_entry__game_map',
            'game__pool_entry__mode',
        )
        .order_by(
            '-kills',
            'deaths',
            'player__name',
        )
    )


def stats_for_player(
    *,
    player_id: int,
) -> QuerySet[PlayerGameStat]:
    return (
        PlayerGameStat.objects
        .filter(player_id=player_id)
        .select_related(
            'player',
            'game',
            'game__pool_entry',
            'game__pool_entry__stage',
            'game__pool_entry__game_map',
            'game__pool_entry__mode',
        )
        .order_by('-game__event_date')
    )


def betting_lines_for_game(
    *,
    game_id: int,
) -> QuerySet[BettingLine]:
    return (
        BettingLine.objects
        .filter(game_id=game_id)
        .select_related(
            'player',
            'game',
        )
        .order_by(
            'player__name',
            'market',
        )
    )


def stages_for_season(
    *,
    season: int,
) -> QuerySet[CompetitionStage]:
    return (
        CompetitionStage.objects
        .filter(season=season)
        .order_by('start_date')
    )
