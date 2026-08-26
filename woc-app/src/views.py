from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .algorithm import find_edges, list_team_names
from .analytics import evaluate_betting_line, hit_rate_summary, matchup_label
from .breakingpoint_client import BreakingPointError
from .models import GameMap
from .pro_teams import PRO_TEAM_NAMES, normalize_team_name
from .selectors import (
    games_for_matches_page,
    known_player_tags,
    latest_season,
    live_underdog_markets,
    map_mode_splits_for_season,
    recent_games,
    roster_for_season,
    upcoming_match_schedule,
)
from .services.breakingpoint import sync_breakingpoint_stats

MAP_PICKER_SLOTS = range(1, 6)


def dashboard(request):
    games = recent_games(limit=8)
    for game in games:
        team_names = sorted({stat.team for stat in game.player_stats.all()})
        game.matchup_label = matchup_label(team_names=team_names, opponent=game.opponent)

    map_choices = list(GameMap.objects.values_list('name', flat=True))
    map_slots = []
    for game_number in MAP_PICKER_SLOTS:
        map_slots.append({
            'game_number': game_number,
            'field_name': f'map_{game_number}',
            'selected': request.GET.get(f'map_{game_number}', '').strip(),
        })
    selected_maps = {
        slot['game_number']: slot['selected'] for slot in map_slots if slot['selected']
    }

    team_choices = list_team_names()
    team_a = request.GET.get('team_a', '').strip()
    team_b = request.GET.get('team_b', '').strip()
    team_pair = (team_a, team_b) if team_a and team_b else None

    edges = (
        find_edges(selected_maps=selected_maps, team_names=team_pair)
        if selected_maps or team_pair
        else []
    )
    for edge in edges:
        edge.matchup_label = matchup_label(
            team_names=[edge.team_name] if edge.team_name else [],
            opponent=edge.opponent_name,
        )
    edges.sort(key=lambda edge: (edge.matchup_label, edge.series_game_number or 0, edge.player_name))

    return render(
        request,
        'dashboard.html',
        {
            'games': games,
            'upcoming_matches': upcoming_match_schedule(limit=8),
            'hit_rate': hit_rate_summary(limit=8),
            'map_choices': map_choices,
            'map_slots': map_slots,
            'team_choices': team_choices,
            'team_a': team_a,
            'team_b': team_b,
            'edges': edges,
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


def players(request):
    try:
        season = int(request.GET.get('season', 2026))
    except (TypeError, ValueError):
        season = 2026

    players_by_team = {
        normalize_team_name(team_name): {
            'name': team_name,
            'placement': placement,
            'players': [],
        }
        for placement, team_name in enumerate(PRO_TEAM_NAMES, start=1)
    }
    roster_entries = list(roster_for_season(season=season))
    splits_by_player = {}
    for split in map_mode_splits_for_season(
        season=season,
        player_ids=[entry.player_id for entry in roster_entries],
    ):
        split['kill_death_ratio'] = (
            split['total_kills'] / split['total_deaths']
            if split['total_deaths']
            else None
        )
        splits_by_player.setdefault(split['player_id'], []).append(split)

    for roster_entry in roster_entries:
        team = players_by_team.get(normalize_team_name(roster_entry.team_name))
        if team is None:
            continue
        player = roster_entry.player
        player.kill_death_ratio = (
            roster_entry.total_kills / roster_entry.total_deaths
            if roster_entry.total_deaths
            else None
        )
        player.games_played = roster_entry.games_played
        player.total_kills = roster_entry.total_kills
        player.total_deaths = roster_entry.total_deaths
        player.map_mode_splits = splits_by_player.get(player.player_id, [])
        team['players'].append(player)

    return render(
        request,
        'players.html',
        {
            'season': season,
            'team_groups': list(players_by_team.values()),
            'total_players': sum(
                len(team['players']) for team in players_by_team.values()
            ),
        },
    )


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
