from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime

from src.breakingpoint_client import BreakingPointClient, BreakingPointError
from src.models import (
    CompetitionStage,
    Game,
    GameMap,
    GameMode,
    GameSource,
    Player,
    PlayerGameStat,
    StageMapPoolEntry,
)
from src.pro_teams import (
    PRO_TEAM_NAMES,
    PRO_TEAM_NAMES_BY_NORMALIZED_NAME,
    normalize_team_name,
)

EVENT_TYPE_TO_SOURCE = {
    'Offline': GameSource.LAN,
    'LAN': GameSource.LAN,
    'Online': GameSource.ONLINE,
}


class Command(BaseCommand):
    help = (
        'Pull player_stats from Breaking Point (breakingpoint.gg) for selected '
        'player tags or all configured professional teams, then upsert them into '
        'the local schema. Run with a fresh access token in .env.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, required=True)
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument(
            '--players',
            type=str,
            help='Comma-separated Breaking Point player tags, e.g. "Huke,Simp".',
        )
        selection.add_argument(
            '--pro-teams',
            action='store_true',
            help=(
                'Pull every 2026 player-stat row belonging to the configured '
                'professional teams.'
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        season = options['season']
        player_tags = [
            p.strip()
            for p in (options.get('players') or '').split(',')
            if p.strip()
        ]
        if options.get('players') is not None and not player_tags:
            raise CommandError('--players must include at least one player tag.')

        client = BreakingPointClient()

        try:
            stats = client.fetch_player_stats(
                season_id=season,
                player_tags=None if options['pro_teams'] else player_tags,
            )
        except BreakingPointError as exc:
            raise CommandError(str(exc)) from exc

        if not stats:
            self.stdout.write(self.style.WARNING(
                f'No player_stats rows found for season={season}.'
            ))
            return

        teams_by_id = {}
        if options['pro_teams']:
            teams_by_id = client.fetch_teams({row['team_id'] for row in stats})
            stats = [
                row
                for row in stats
                if normalize_team_name(
                    teams_by_id.get(row['team_id'], {}).get('name', '')
                ) in PRO_TEAM_NAMES_BY_NORMALIZED_NAME
            ]
            if not stats:
                raise CommandError(
                    'Breaking Point returned no rows matching the configured pro '
                    f'teams: {", ".join(PRO_TEAM_NAMES)}.'
                )

        modes_by_id = client.fetch_modes()
        maps_by_id = client.fetch_maps()
        events_by_id = client.fetch_events({row['event_id'] for row in stats})
        matches_by_id = client.fetch_matches({row['match_id'] for row in stats})

        team_ids = set()
        for match in matches_by_id.values():
            team_ids.add(match['team_1_id'])
            team_ids.add(match['team_2_id'])
        missing_team_ids = team_ids.difference(teams_by_id)
        teams_by_id.update(client.fetch_teams(missing_team_ids))

        rows_by_game = defaultdict(list)
        for row in stats:
            rows_by_game[row['game_id']].append(row)

        games_created = 0
        players_created = 0
        stats_written = 0

        for game_id, rows in rows_by_game.items():
            first = rows[0]
            event = events_by_id.get(first['event_id'])
            match = matches_by_id.get(first['match_id'])
            if event is None or match is None:
                self.stdout.write(self.style.WARNING(
                    f'Skipping game {game_id}: missing event/match reference data.'
                ))
                continue

            stage, _ = CompetitionStage.objects.update_or_create(
                name=event['name'],
                season=season,
                defaults={
                    'start_date': parse_date(event['start_date']),
                    'end_date': parse_date(event['end_date']),
                },
            )

            mode_name = modes_by_id.get(first['mode_id'], {}).get(
                'name', f"Mode {first['mode_id']}"
            )
            map_name = maps_by_id.get(first['map_id'], {}).get(
                'name', f"Map {first['map_id']}"
            )
            game_map, _ = GameMap.objects.get_or_create(name=map_name)
            mode, _ = GameMode.objects.get_or_create(name=mode_name)
            pool_entry, _ = StageMapPoolEntry.objects.get_or_create(
                stage=stage, game_map=game_map, mode=mode,
            )

            source = EVENT_TYPE_TO_SOURCE.get(first['event_type'])
            if source is None:
                self.stdout.write(self.style.WARNING(
                    f"Skipping game {game_id}: unrecognized event_type "
                    f"{first['event_type']!r}."
                ))
                continue

            # Opponent is resolved from the first target player found in this
            # game. If your --players list spans both teams in the same
            # match, this field can only hold one side's perspective — a
            # limitation of the existing single `opponent` column on Game.
            player_team_id = first['team_id']
            opponent_team_id = (
                match['team_2_id'] if player_team_id == match['team_1_id']
                else match['team_1_id']
            )
            opponent_name = teams_by_id.get(opponent_team_id, {}).get(
                'name', f'Team {opponent_team_id}'
            )

            event_date = parse_datetime(first['datetime'])

            game, created = Game.objects.update_or_create(
                source_id=game_id,
                defaults={
                    'pool_entry': pool_entry,
                    'source': source,
                    'opponent': opponent_name,
                    'event_date': event_date,
                },
            )
            games_created += int(created)

            for row in rows:
                player, p_created = Player.objects.update_or_create(
                    player_id=row['player_id'],
                    defaults={'name': row['player_tag']},
                )
                players_created += int(p_created)

                team_name = teams_by_id.get(row['team_id'], {}).get(
                    'name', f"Team {row['team_id']}"
                )
                PlayerGameStat.objects.update_or_create(
                    player=player,
                    game=game,
                    defaults={
                        'kills': row['kills'] or 0,
                        'deaths': row['deaths'] or 0,
                        'team': team_name,
                    },
                )
                stats_written += 1

        self.stdout.write(self.style.SUCCESS(
            f'Synced {games_created} new games, {players_created} new players, '
            f'and {stats_written} player-game stat rows for season {season}'
            f'{" across the configured pro teams" if options["pro_teams"] else ""}.'
        ))
