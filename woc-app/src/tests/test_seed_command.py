from django.core.management import call_command
from django.test import TestCase

from src.models import BettingLine, CompetitionStage, Game, Player, PlayerGameStat


class SeedTestDataCommandTests(TestCase):
    def test_command_loads_expected_records_and_is_idempotent(self):
        call_command('seed_test_data', verbosity=0)
        call_command('seed_test_data', verbosity=0)

        self.assertEqual(Player.objects.count(), 12)
        self.assertEqual(Game.objects.count(), 24)
        self.assertEqual(PlayerGameStat.objects.count(), 96)
        self.assertEqual(BettingLine.objects.count(), 96)
        self.assertEqual(
            CompetitionStage.objects.filter(
                season=2026,
                name='Test Data',
            ).count(),
            1,
        )
        self.assertEqual(
            set(BettingLine.objects.values_list('market', flat=True)),
            {'M1_KILLS', 'M2_KILLS', 'M3_KILLS'},
        )
