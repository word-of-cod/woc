from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from src.models import (
    BettingLine,
    BettingMarket,
    CompetitionStage,
    Game,
    GameMap,
    GameMode,
    GameSource,
    Player,
    PlayerGameStat,
    StageMapPoolEntry,
)


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
)
class MatchesViewTests(TestCase):
    def setUp(self):
        player = Player.objects.create(name='Example Player')
        opponent_player = Player.objects.create(name='Opponent Player')
        game_map = GameMap.objects.create(name='Hacienda')
        mode = GameMode.objects.create(name='Hardpoint')
        stage = CompetitionStage.objects.create(
            name='Major 1',
            season=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
        )
        pool_entry = StageMapPoolEntry.objects.create(
            stage=stage,
            game_map=game_map,
            mode=mode,
        )
        game = Game.objects.create(
            pool_entry=pool_entry,
            source=GameSource.LAN,
            opponent='OpTic Texas',
            source_id='breakingpoint-game-1',
            event_date=timezone.make_aware(
                datetime(2026, 1, 15, 19, 30)
            ),
        )
        PlayerGameStat.objects.create(
            player=player,
            game=game,
            kills=24,
            deaths=16,
            team='Atlanta FaZe',
        )
        PlayerGameStat.objects.create(
            player=opponent_player,
            game=game,
            kills=18,
            deaths=20,
            team='OpTic Texas',
        )
        BettingLine.objects.create(
            player=player,
            game=game,
            market=BettingMarket.MAP_1_KILLS,
            line=Decimal('22.500'),
        )

    def test_matches_page_displays_game_stats_and_line(self):
        response = self.client.get(reverse('matches'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'matches.html')
        self.assertContains(response, 'Hacienda')
        self.assertContains(response, 'Hardpoint')
        self.assertContains(response, 'OpTic Texas')
        self.assertContains(response, 'Atlanta FaZe')
        self.assertContains(response, 'OpTic Texas')
        self.assertContains(response, 'Example Player')
        self.assertContains(response, 'Opponent Player')
        self.assertContains(response, 'Map 1 kills')
        self.assertContains(response, '22.5')
        self.assertContains(response, '24')
        self.assertContains(response, 'OVER')

    def test_matches_page_handles_imported_game_without_betting_lines(self):
        BettingLine.objects.all().delete()

        response = self.client.get(reverse('matches'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Player performance')
        self.assertNotContains(response, '<th class="px-4 py-3 font-medium">Market</th>', html=True)
