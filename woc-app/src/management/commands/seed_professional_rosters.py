from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from src.models import Player, ProfessionalRoster
from src.pro_teams import PRO_TEAM_ROSTERS_2026


class Command(BaseCommand):
    help = 'Seed the curated current professional roster snapshot for a season.'

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, default=2026)

    @transaction.atomic
    def handle(self, *args, **options):
        season = options['season']
        if season != 2026:
            raise CommandError('Only the maintained 2026 roster snapshot is available.')

        players_by_name = {
            player.name.lower(): player
            for player in Player.objects.filter(
                name__in=[
                    name for roster in PRO_TEAM_ROSTERS_2026.values()
                    for name in roster
                ]
            )
        }
        missing_players = [
            name for roster in PRO_TEAM_ROSTERS_2026.values() for name in roster
            if name.lower() not in players_by_name
        ]
        if missing_players:
            raise CommandError(
                'Cannot seed roster; import Breaking Point data first. Missing: '
                + ', '.join(missing_players)
            )

        ProfessionalRoster.objects.filter(season=season).delete()
        entries = []
        for team_name, player_names in PRO_TEAM_ROSTERS_2026.items():
            for display_order, player_name in enumerate(player_names, start=1):
                entries.append(ProfessionalRoster(
                    season=season,
                    team_name=team_name,
                    player=players_by_name[player_name.lower()],
                    display_order=display_order,
                ))
        ProfessionalRoster.objects.bulk_create(entries)
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(entries)} professional roster entries for {season}.'
        ))
