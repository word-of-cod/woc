from django.shortcuts import render

from .selectors import recent_games


def dashboard(request):
    games = recent_games(limit=20)

    return render(
        request,
        'dashboard.html',
        {
            'games': games,
        },
    )