from datetime import date, datetime

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from src.models import (
    CompetitionStage,
    Game,
    GameMap,
    GameMode,
    GameSource,
    Player,
    PlayerGameStat,
    ProfessionalRoster,
    StageMapPoolEntry,
)


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'
        },
    }
)
class PlayersViewTests(TestCase):
    def setUp(self):
        stage = CompetitionStage.objects.create(
            name='Major 1',
            season=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
        )
        pool_entry = StageMapPoolEntry.objects.create(
            stage=stage,
            game_map=GameMap.objects.create(name='Hacienda'),
            mode=GameMode.objects.create(name='Hardpoint'),
        )
        game = Game.objects.create(
            pool_entry=pool_entry,
            source=GameSource.LAN,
            opponent='Los Angeles Thieves',
            source_id='players-view-game',
            event_date=timezone.make_aware(datetime(2026, 1, 15, 19, 30)),
        )
        optic_player = Player.objects.create(name='Dashy')
        PlayerGameStat.objects.create(
            player=optic_player,
            game=game,
            kills=30,
            deaths=20,
            team='OpTic Texas',
        )
        unrelated_player = Player.objects.create(name='Challenger')
        PlayerGameStat.objects.create(
            player=unrelated_player,
            game=game,
            kills=20,
            deaths=20,
            team='Amateur Team',
        )
        ProfessionalRoster.objects.create(
            season=2026,
            team_name='OpTic Texas',
            player=optic_player,
            display_order=1,
        )

    def test_players_page_groups_pro_players_and_calculates_totals(self):
        response = self.client.get(reverse('players'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'players.html')
        self.assertContains(response, 'OpTic Texas')
        self.assertContains(response, 'Dashy')
        self.assertContains(response, '30')
        self.assertContains(response, '20')
        self.assertContains(response, '1.50')
        self.assertContains(response, 'View map and mode breakdown')
        self.assertContains(response, 'Hacienda')
        self.assertContains(response, 'Hardpoint')
        self.assertNotContains(response, 'Challenger')

    def test_players_page_lists_empty_pro_teams(self):
        response = self.client.get(reverse('players'))

        self.assertContains(response, 'Los Angeles Thieves')
        self.assertContains(
            response,
            'No 2026 player data imported for this team.',
        )
