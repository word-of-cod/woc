"""Line outcomes, and a simple 'player average vs. line' suggestion backtest."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean

from .models import BettingLine, PlayerGameStat, ResolutionStatus, UnderdogMarket


def evaluate_betting_line(*, line, stat):
    is_underdog = hasattr(line, 'stat_type')
    if stat is None:
        return {
            'line': line,
            'market_display': (
                line.market_display if is_underdog else line.get_market_display()
            ),
            'provider_display': 'Underdog' if is_underdog else '',
            'actual_value': None,
            'outcome': 'PENDING',
        }

    if is_underdog and line.stat_type == 'KILLS':
        actual_value = stat.kills
    elif is_underdog and line.stat_type == 'DEATHS':
        actual_value = stat.deaths
    elif not is_underdog and line.market.endswith('_KILLS'):
        actual_value = stat.kills
    elif not is_underdog and line.market.endswith('_DEATHS'):
        actual_value = stat.deaths
    else:
        actual_value = None

    if actual_value is None:
        outcome = 'PENDING'
    elif actual_value > line.line:
        outcome = 'OVER'
    elif actual_value < line.line:
        outcome = 'UNDER'
    else:
        outcome = 'PUSH'

    return {
        'line': line,
        'market_display': (
            line.market_display if is_underdog else line.get_market_display()
        ),
        'provider_display': 'Underdog' if is_underdog else '',
        'actual_value': actual_value,
        'outcome': outcome,
    }


def matchup_label(*, team_names: list[str], opponent: str) -> str:
    if len(team_names) > 1:
        return ' vs. '.join(team_names)
    if team_names:
        return f'{team_names[0]} vs. {opponent}'
    return f'Unknown team vs. {opponent}'


def _stat_value(stat: PlayerGameStat, stat_type: str) -> int:
    return stat.kills if stat_type == 'KILLS' else stat.deaths


def suggested_side(*, values: list[int], line) -> str | None:
    """Naive suggestion: OVER/UNDER based on the player's average in their other games."""
    if not values:
        return None

    average = mean(values)
    if average > line:
        return 'OVER'
    if average < line:
        return 'UNDER'
    return None


def hit_rate_summary(*, limit: int = 8) -> dict:
    """Backtests the naive suggestion against every resolved line with a known result.

    The suggestion for a given line is computed from the player's other recorded
    games only (leave-one-out), so it never sees the game it's predicting.
    """
    stats_by_player = defaultdict(list)
    for stat in PlayerGameStat.objects.all():
        stats_by_player[stat.player_id].append(stat)

    candidates = []

    for line in BettingLine.objects.select_related('player', 'game'):
        stat = next(
            (s for s in stats_by_player[line.player_id] if s.game_id == line.game_id),
            None,
        )
        if stat is None:
            continue
        stat_type = 'DEATHS' if line.market.endswith('_DEATHS') else 'KILLS'
        candidates.append((line, stat, stat_type))

    for market in (
        UnderdogMarket.objects
        .filter(resolution_status=ResolutionStatus.RESOLVED)
        .select_related('player', 'game')
    ):
        stat = next(
            (s for s in stats_by_player[market.player_id] if s.game_id == market.game_id),
            None,
        )
        if stat is None:
            continue
        candidates.append((market, stat, market.stat_type))

    entries = []
    hits = 0
    decided = 0

    for line, stat, stat_type in candidates:
        other_values = [
            _stat_value(s, stat_type)
            for s in stats_by_player[line.player_id]
            if s.game_id != line.game_id
        ]
        suggestion = suggested_side(values=other_values, line=line.line)
        result = evaluate_betting_line(line=line, stat=stat)
        is_hit = suggestion is not None and suggestion == result['outcome']
        if suggestion is not None and result['outcome'] in ('OVER', 'UNDER'):
            decided += 1
            hits += int(is_hit)

        entries.append({
            'player_name': stat.player.name,
            'market_display': result['market_display'],
            'line': line.line,
            'suggestion': suggestion,
            'actual_value': result['actual_value'],
            'outcome': result['outcome'],
            'is_hit': is_hit,
            'game_id': line.game_id,
        })

    entries.sort(key=lambda entry: entry['game_id'], reverse=True)

    return {
        'hits': hits,
        'decided': decided,
        'rate': (hits / decided * 100) if decided else None,
        'entries': entries[:limit],
    }
