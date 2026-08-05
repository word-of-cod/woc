from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from src.models import (
    CompetitionStage,
    Game,
    GameMap,
    GameMode,
    Player,
    PlayerGameStat,
    StageMapPoolEntry,
)


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        # Manifest static storage needs `collectstatic` to have run (it does
        # in the Docker image, not on a bare local checkout) — swap it out
        # so tests that render admin templates don't depend on that.
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class PlayerAdminChangeViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='password',
        )
        self.client.force_login(self.admin_user)

        stage = CompetitionStage.objects.create(
            name='Major 1',
            season=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        game_map = GameMap.objects.create(name='TestMap')
        mode = GameMode.objects.create(name='Hardpoint')
        pool_entry = StageMapPoolEntry.objects.create(
            stage=stage, game_map=game_map, mode=mode,
        )
        self.player = Player.objects.create(name='Huke')

        # A player with many games exercises the `game` FK dropdown on the
        # PlayerGameStat inline. Without raw_id_fields + select_related,
        # rendering this used to build a full <select> of every Game and
        # call Game.__str__ (which queries pool_entry/map/mode) once per
        # game per row — an N+1 blowup that timed out in production.
        for i in range(50):
            game = Game.objects.create(
                pool_entry=pool_entry,
                source='LAN',
                opponent=f'Opponent {i}',
                event_date=timezone.make_aware(datetime(2026, 1, 1) + timedelta(days=i)),
            )
            PlayerGameStat.objects.create(
                player=self.player, game=game, kills=10, deaths=5, team='Team A',
            )

    def test_change_view_renders_with_many_stats(self):
        url = reverse('admin:src_player_change', args=[self.player.player_id])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    def test_game_fk_is_rendered_as_raw_id_field_not_a_full_dropdown(self):
        url = reverse('admin:src_player_change', args=[self.player.player_id])

        response = self.client.get(url)

        self.assertNotContains(response, '<option value="1">Opponent 0')
