from django.core.management.base import BaseCommand, CommandError

from src.breakingpoint_client import BreakingPointError
from src.services.breakingpoint import sync_breakingpoint_stats


class Command(BaseCommand):
    help = (
        'Pull player_stats from Breaking Point (breakingpoint.gg) for the given '
        'season and player tags, and upsert them into the local schema. Intended '
        'to run manually (e.g. weekly) with a fresh access token in .env.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, required=True)
        parser.add_argument(
            '--players',
            type=str,
            required=True,
            help='Comma-separated Breaking Point player tags, e.g. "Huke,Simp".',
        )

    def handle(self, *args, **options):
        season = options['season']
        player_tags = [p.strip() for p in options['players'].split(',') if p.strip()]
        if not player_tags:
            raise CommandError('--players must include at least one player tag.')

        try:
            result = sync_breakingpoint_stats(season=season, player_tags=player_tags)
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
