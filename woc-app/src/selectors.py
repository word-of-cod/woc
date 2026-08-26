from datetime import timedelta

from django.db.models import Count, Prefetch, Q, QuerySet, Sum
from django.utils import timezone

from .models import (
    BettingLine,
    CompetitionStage,
    Game,
    Player,
    PlayerGameStat,
    ProfessionalRoster,
    ResolutionStatus,
    StageMapPoolEntry,
    UnderdogMarket,
)
from .pro_teams import PRO_TEAM_NAMES, normalize_team_name


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



def roster_for_season(*, season: int) -> QuerySet[ProfessionalRoster]:
    return (
        ProfessionalRoster.objects
        .filter(season=season)
        .select_related('player')
        .annotate(
            games_played=Count(
                'player__game_stats__game',
                filter=Q(
                    player__game_stats__game__pool_entry__stage__season=season
                ),
                distinct=True,
            ),
            total_kills=Sum(
                'player__game_stats__kills',
                filter=Q(
                    player__game_stats__game__pool_entry__stage__season=season
                ),
            ),
            total_deaths=Sum(
                'player__game_stats__deaths',
                filter=Q(
                    player__game_stats__game__pool_entry__stage__season=season
                ),
            ),
        )
        .order_by('team_name', 'display_order', 'player__name')
    )


def map_mode_splits_for_season(*, season: int, player_ids: list[int]):
    return (
        PlayerGameStat.objects
        .filter(
            player_id__in=player_ids,
            game__pool_entry__stage__season=season,
        )
        .values(
            'player_id',
            'game__pool_entry__game_map__name',
            'game__pool_entry__mode__name',
        )
        .annotate(
            maps_played=Count('game_id'),
            total_kills=Sum('kills'),
            total_deaths=Sum('deaths'),
        )
        .order_by(
            'player_id',
            'game__pool_entry__mode__name',
            'game__pool_entry__game_map__name',
        )
    )


def team_summaries_for_season(*, season: int):
    """Return the eight current CDL teams using only current-roster stats.

    `PlayerGameStat.team` is historical, so it can include former teams,
    substitutes, Challengers, and EWC opponents.  The Teams page intentionally
    uses the curated current roster as its boundary and only keeps a stat when
    the player was recorded for that same current team.
    """
    roster_by_player = {
        entry['player_id']: entry['team_name']
        for entry in ProfessionalRoster.objects.filter(season=season).values(
            'player_id', 'team_name'
        )
    }
    summaries = {
        team_name: {
            'team': team_name,
            'maps': set(),
            'players': set(),
            'events': set(),
            'total_kills': 0,
            'total_deaths': 0,
            'last_played': None,
        }
        for team_name in PRO_TEAM_NAMES
    }

    stats = PlayerGameStat.objects.filter(
        player_id__in=roster_by_player,
        game__pool_entry__stage__season=season,
    ).values(
        'player_id',
        'team',
        'game_id',
        'kills',
        'deaths',
        'game__event_date',
        'game__pool_entry__stage_id',
    )
    for stat in stats:
        team_name = roster_by_player[stat['player_id']]
        if normalize_team_name(stat['team']) != normalize_team_name(team_name):
            continue

        summary = summaries[team_name]
        summary['maps'].add(stat['game_id'])
        summary['players'].add(stat['player_id'])
        summary['events'].add(stat['game__pool_entry__stage_id'])
        summary['total_kills'] += stat['kills']
        summary['total_deaths'] += stat['deaths']
        if (
            summary['last_played'] is None
            or stat['game__event_date'] > summary['last_played']
        ):
            summary['last_played'] = stat['game__event_date']

    results = []
    for summary in summaries.values():
        summary['maps_played'] = len(summary.pop('maps'))
        summary['players_recorded'] = len(summary.pop('players'))
        summary['events_played'] = len(summary.pop('events'))
        summary['kill_death_ratio'] = (
            summary['total_kills'] / summary['total_deaths']
            if summary['total_deaths']
            else None
        )
        results.append(summary)

    return sorted(
        results,
        key=lambda summary: (
            -summary['maps_played'],
            -summary['total_kills'],
            summary['team'],
        ),
    )

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
