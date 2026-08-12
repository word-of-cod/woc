from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from src.models import Player, ProfessionalRoster
from src.pro_teams import PRO_TEAM_ROSTERS_2026


class SeedProfessionalRostersCommandTests(TestCase):
    def setUp(self):
        for player_names in PRO_TEAM_ROSTERS_2026.values():
            for name in player_names:
                Player.objects.get_or_create(name=name)

    def test_seeds_exactly_the_curated_2026_roster(self):
        output = StringIO()

        call_command('seed_professional_rosters', season=2026, stdout=output)

        self.assertEqual(ProfessionalRoster.objects.count(), 32)
        self.assertEqual(
            list(ProfessionalRoster.objects.filter(team_name='FaZe Vegas').values_list(
                'player__name', flat=True
            )),
            ['04', 'Abuzah', 'Drazah', 'Simp'],
        )

    def test_fails_if_breakingpoint_players_have_not_been_imported(self):
        Player.objects.filter(name='Drazah').delete()

        with self.assertRaises(CommandError):
            call_command('seed_professional_rosters', season=2026)
