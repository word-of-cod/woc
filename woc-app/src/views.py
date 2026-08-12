from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .analytics import evaluate_betting_line, hit_rate_summary, matchup_label
from .breakingpoint_client import BreakingPointError
from .selectors import (
    games_for_matches_page,
    known_player_tags,
    latest_season,
    live_underdog_markets,
    recent_games,
    upcoming_match_schedule,
)
from .services.breakingpoint import sync_breakingpoint_stats


def dashboard(request):
    games = recent_games(limit=8)
    for game in games:
        team_names = sorted({stat.team for stat in game.player_stats.all()})
        game.matchup_label = matchup_label(team_names=team_names, opponent=game.opponent)

    return render(
        request,
        'dashboard.html',
        {
            'games': games,
            'upcoming_matches': upcoming_match_schedule(limit=8),
            'hit_rate': hit_rate_summary(limit=8),
        },
    )


@require_POST
def refresh_betting_lines(request):
    season = latest_season()
    player_tags = known_player_tags()

    if season is None or not player_tags:
        messages.error(
            request,
            'Add at least one competition stage and player before syncing '
            'Breaking Point stats.',
        )
        return redirect('dashboard')

    try:
        result = sync_breakingpoint_stats(season=season, player_tags=player_tags)
    except BreakingPointError as exc:
        messages.error(request, f'Breaking Point sync failed: {exc}')
        return redirect('dashboard')

    if result.fetched_count == 0:
        messages.warning(request, f'No Breaking Point stats found for season {season}.')
    else:
        messages.success(
            request,
            f'Synced {result.games_created} new games, {result.players_created} new '
            f'players, and {result.stats_written} player-game stat rows.',
        )

    return redirect('dashboard')


def matches(request):
    paginator = Paginator(games_for_matches_page(), 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    games = page_obj.object_list
    live_market_groups = {}
    for market in live_underdog_markets():
        group = live_market_groups.setdefault(
            market.external_match_id,
            {
                'scheduled_at': market.scheduled_at,
                'team_name': market.team_name,
                'opponent_name': market.opponent_name,
                'markets': [],
            },
        )
        group['markets'].append(market)

    for game in games:
        stats = list(game.player_stats.all())
        lines_by_player = {}
        betting_lines = list(game.betting_lines.all())
        betting_lines.extend(game.underdog_markets.all())
        for line in betting_lines:
            lines_by_player.setdefault(line.player_id, []).append(line)

        game.team_names = sorted({stat.team for stat in stats})
        game.has_betting_lines = bool(betting_lines)
        game.matchup_label = matchup_label(team_names=game.team_names, opponent=game.opponent)
        rows_by_team = {}

        for stat in stats:
            player_lines = lines_by_player.pop(stat.player_id, [])
            rows_by_team.setdefault(stat.team, []).append(
                {
                    'player': stat.player,
                    'stat': stat,
                    'lines': [
                        evaluate_betting_line(line=line, stat=stat)
                        for line in player_lines
                    ],
                }
            )

        for remaining_lines in lines_by_player.values():
            rows_by_team.setdefault('Team not recorded', []).append(
                {
                    'player': remaining_lines[0].player,
                    'stat': None,
                    'lines': [
                        evaluate_betting_line(line=line, stat=None)
                        for line in remaining_lines
                    ],
                }
            )

        game.team_groups = [
            {
                'name': team_name,
                'rows': rows_by_team[team_name],
            }
            for team_name in sorted(rows_by_team)
        ]

    return render(
        request,
        'matches.html',
        {
            'games': games,
            'page_obj': page_obj,
            'total_games': paginator.count,
            'live_market_groups': list(live_market_groups.values()),
        },
    )
