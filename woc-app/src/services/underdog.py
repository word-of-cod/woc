"""Persistence and reconciliation for imported Underdog markets."""
from __future__ import annotations

from datetime import timedelta
import re

from django.db import transaction

from ..models import (
    BettingProvider,
    Game,
    MarketScope,
    Player,
    PlayerAlias,
    ResolutionStatus,
    UnderdogMarket,
)


MODE_ALIASES_BY_GAME_NUMBER = {
    1: {'hardpoint', 'hp'},
    2: {'searchanddestroy', 'snd'},
    3: {'overload'},
}


def normalize_name(value: str) -> str:
    normalized = re.sub(r'[^a-z0-9]', '', (value or '').lower())
    return normalized.removeprefix('team')


def names_match(left: str, right: str) -> bool:
    left_normalized = normalize_name(left)
    right_normalized = normalize_name(right)
    if not left_normalized or not right_normalized:
        return False
    return (
        left_normalized == right_normalized
        or left_normalized.endswith(right_normalized)
        or right_normalized.endswith(left_normalized)
    )


def resolve_player(market: UnderdogMarket) -> Player | None:
    alias = (
        PlayerAlias.objects
        .filter(
            provider=BettingProvider.UNDERDOG,
            external_player_id=market.external_player_id,
        )
        .select_related('player')
        .first()
    )
    if alias:
        return alias.player

    normalized_market_name = normalize_name(market.player_name)
    matches = [
        player
        for player in Player.objects.all()
        if normalize_name(player.name) == normalized_market_name
    ]
    if len(matches) != 1:
        return None

    player = matches[0]
    PlayerAlias.objects.create(
        player=player,
        provider=BettingProvider.UNDERDOG,
        external_player_id=market.external_player_id,
        display_name=market.player_name,
    )
    return player


def game_matches_market(game: Game, market: UnderdogMarket) -> bool:
    expected_modes = MODE_ALIASES_BY_GAME_NUMBER.get(
        market.series_game_number, set()
    )
    if normalize_name(game.mode.name) not in expected_modes:
        return False

    player_stat = next(
        (stat for stat in game.player_stats.all() if stat.player_id == market.player_id),
        None,
    )
    if player_stat is None or not names_match(player_stat.team, market.team_name):
        return False

    possible_opponents = {game.opponent}
    possible_opponents.update(
        stat.team
        for stat in game.player_stats.all()
        if not names_match(stat.team, player_stat.team)
    )
    return any(
        names_match(name, market.opponent_name)
        for name in possible_opponents
    )


@transaction.atomic
def resolve_market(market: UnderdogMarket) -> UnderdogMarket:
    player = resolve_player(market)
    if player is None:
        market.player = None
        market.game = None
        market.resolution_status = ResolutionStatus.UNMATCHED_PLAYER
        market.resolution_note = (
            f'No unique local player matched {market.player_name!r}.'
        )
        market.save(update_fields=(
            'player', 'game', 'resolution_status', 'resolution_note'
        ))
        return market

    market.player = player
    if market.market_scope == MarketScope.GAMES_1_3:
        market.game = None
        market.resolution_status = ResolutionStatus.PENDING
        market.resolution_note = (
            'Aggregate Games 1-3 market is not linked to one map-level game.'
        )
        market.save(update_fields=(
            'player', 'game', 'resolution_status', 'resolution_note'
        ))
        return market

    if market.scheduled_at is None:
        market.game = None
        market.resolution_status = ResolutionStatus.UNMATCHED_GAME
        market.resolution_note = 'Underdog did not provide a scheduled match time.'
        market.save(update_fields=(
            'player', 'game', 'resolution_status', 'resolution_note'
        ))
        return market

    window_start = market.scheduled_at - timedelta(hours=18)
    window_end = market.scheduled_at + timedelta(hours=18)
    candidates = list(
        Game.objects
        .filter(
            player_stats__player=player,
            event_date__range=(window_start, window_end),
        )
        .select_related('pool_entry__mode')
        .prefetch_related('player_stats')
        .distinct()
    )
    candidates = [
        game for game in candidates if game_matches_market(game, market)
    ]

    if len(candidates) == 1:
        market.game = candidates[0]
        market.resolution_status = ResolutionStatus.RESOLVED
        market.resolution_note = ''
    elif not candidates:
        market.game = None
        market.resolution_status = ResolutionStatus.UNMATCHED_GAME
        market.resolution_note = (
            'No game matched player, teams, scheduled time, and expected mode.'
        )
    else:
        market.game = None
        market.resolution_status = ResolutionStatus.AMBIGUOUS
        market.resolution_note = f'{len(candidates)} games matched this market.'

    market.save(update_fields=(
        'player', 'game', 'resolution_status', 'resolution_note'
    ))
    return market


def resolve_unresolved_markets() -> dict[str, int]:
    counters = {status: 0 for status in ResolutionStatus.values}
    markets = UnderdogMarket.objects.exclude(
        resolution_status=ResolutionStatus.RESOLVED
    )
    for market in markets.iterator():
        resolve_market(market)
        counters[market.resolution_status] += 1
    return counters
