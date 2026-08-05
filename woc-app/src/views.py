from django.core.paginator import Paginator
from django.shortcuts import render

from .selectors import games_for_matches_page, recent_games


def evaluate_betting_line(*, line, stat):
    if stat is None:
        return {
            'line': line,
            'actual_value': None,
            'outcome': 'PENDING',
        }

    if line.market.endswith('_KILLS'):
        actual_value = stat.kills
    elif line.market.endswith('_DEATHS'):
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
        'actual_value': actual_value,
        'outcome': outcome,
    }


def dashboard(request):
    games = recent_games(limit=20)

    return render(
        request,
        'dashboard.html',
        {
            'games': games,
        },
    )


def matches(request):
    paginator = Paginator(games_for_matches_page(), 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    games = page_obj.object_list

    for game in games:
        stats = list(game.player_stats.all())
        lines_by_player = {}
        betting_lines = list(game.betting_lines.all())
        for line in betting_lines:
            lines_by_player.setdefault(line.player_id, []).append(line)

        game.team_names = sorted({stat.team for stat in stats})
        game.has_betting_lines = bool(betting_lines)
        if len(game.team_names) > 1:
            game.matchup_label = ' vs. '.join(game.team_names)
        elif game.team_names:
            game.matchup_label = f'{game.team_names[0]} vs. {game.opponent}'
        else:
            game.matchup_label = f'Unknown team vs. {game.opponent}'
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
        },
    )
