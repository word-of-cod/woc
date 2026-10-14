from datetime import date, datetime
from decimal import Decimal

from django.db import transaction

from ..models import (
    BettingLine,
    BettingMarket,
    CompetitionStage,
    Game,
    GameMap,
    GameMode,
    GameSource,
    Player,
    PlayerGameStat,
    StageMapPoolEntry,
)


@transaction.atomic
def create_player(*, name: str) -> Player:
    cleaned_name = name.strip()

    if not cleaned_name:
        raise ValueError('Player name cannot be empty.')

    return Player.objects.create(name=cleaned_name)


@transaction.atomic
def create_game_map(*, name: str) -> GameMap:
    cleaned_name = name.strip()

    if not cleaned_name:
        raise ValueError('Map name cannot be empty.')

    game_map, _created = GameMap.objects.get_or_create(
        name=cleaned_name,
    )

    return game_map


@transaction.atomic
def create_game_mode(*, name: str) -> GameMode:
    cleaned_name = name.strip()

    if not cleaned_name:
        raise ValueError('Mode name cannot be empty.')

    mode, _created = GameMode.objects.get_or_create(
        name=cleaned_name,
    )

    return mode


@transaction.atomic
def create_competition_stage(
    *,
    name: str,
    season: int,
    start_date: date,
    end_date: date,
) -> CompetitionStage:
    cleaned_name = name.strip()

    if not cleaned_name:
        raise ValueError('Stage name cannot be empty.')

    if end_date < start_date:
        raise ValueError(
            'Stage end date cannot be before its start date.'
        )

    return CompetitionStage.objects.create(
        name=cleaned_name,
        season=season,
        start_date=start_date,
        end_date=end_date,
    )


@transaction.atomic
def add_map_to_stage_pool(
    *,
    stage: CompetitionStage,
    game_map: GameMap,
    mode: GameMode,
) -> StageMapPoolEntry:
    pool_entry, _created = (
        StageMapPoolEntry.objects.get_or_create(
            stage=stage,
            game_map=game_map,
            mode=mode,
        )
    )

    return pool_entry


@transaction.atomic
def create_game(
    *,
    pool_entry: StageMapPoolEntry,
    source: GameSource,
    opponent: str,
    event_date: datetime,
) -> Game:
    cleaned_opponent = opponent.strip()

    if not cleaned_opponent:
        raise ValueError('Opponent cannot be empty.')

    return Game.objects.create(
        pool_entry=pool_entry,
        source=source,
        opponent=cleaned_opponent,
        event_date=event_date,
    )


@transaction.atomic
def record_player_result(
    *,
    player: Player,
    game: Game,
    kills: int,
    deaths: int,
    team: str,
) -> PlayerGameStat:
    if kills < 0:
        raise ValueError('Kills cannot be negative.')

    if deaths < 0:
        raise ValueError('Deaths cannot be negative.')

    cleaned_team = team.strip()

    if not cleaned_team:
        raise ValueError('Team cannot be empty.')

    result, _created = PlayerGameStat.objects.update_or_create(
        player=player,
        game=game,
        defaults={
            'kills': kills,
            'deaths': deaths,
            'team': cleaned_team,
        },
    )

    return result


@transaction.atomic
def set_betting_line(
    *,
    player: Player,
    game: Game,
    market: BettingMarket,
    line: Decimal,
) -> BettingLine:
    if line < 0:
        raise ValueError('Betting line cannot be negative.')

    betting_line, _created = BettingLine.objects.update_or_create(
        player=player,
        game=game,
        market=market,
        defaults={
            'line': line,
        },
    )

    return betting_line
