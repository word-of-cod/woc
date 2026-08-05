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
    games = games_for_matches_page()

    for game in games:
        stats = list(game.player_stats.all())
        lines_by_player = {}
        for line in game.betting_lines.all():
            lines_by_player.setdefault(line.player_id, []).append(line)

        game.team_names = sorted({stat.team for stat in stats})
        game.player_rows = []

        for stat in stats:
            player_lines = lines_by_player.pop(stat.player_id, [])
            game.player_rows.append(
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
            game.player_rows.append(
                {
                    'player': remaining_lines[0].player,
                    'stat': None,
                    'lines': [
                        evaluate_betting_line(line=line, stat=None)
                        for line in remaining_lines
                    ],
                }
            )

    return render(
        request,
        'matches.html',
        {
            'games': games,
        },
    )
