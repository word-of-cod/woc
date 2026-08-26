from django.core.management.base import BaseCommand, CommandError

from src.breakingpoint_client import BreakingPointError
from src.services.breakingpoint import sync_breakingpoint_stats


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
                'Pull every player-stat row belonging to the configured '
                'professional teams.'
            ),
        )

    def handle(self, *args, **options):
        season = options['season']
        player_tags = None
        if options.get('players') is not None:
            player_tags = [p.strip() for p in options['players'].split(',') if p.strip()]
            if not player_tags:
                raise CommandError('--players must include at least one player tag.')

        try:
            result = sync_breakingpoint_stats(
                season=season,
                player_tags=player_tags,
                pro_teams_only=options['pro_teams'],
            )
        except BreakingPointError as exc:
            raise CommandError(str(exc)) from exc

        for warning in result.warnings:
            self.stdout.write(self.style.WARNING(warning))

        if result.fetched_count == 0:
            return

        self.stdout.write(self.style.SUCCESS(
            f'Synced {result.games_created} new games, {result.players_created} new players, '
            f'and {result.stats_written} player-game stat rows for season {season}.'
        ))
