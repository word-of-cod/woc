from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from src.breakingpoint_client import BreakingPointError
from src.services.breakingpoint import BreakingPointSyncResult
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
    ProfessionalRoster,
    StageMapPoolEntry,
    UnderdogMarket,
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
        UnderdogMarket.objects.create(
            external_id='underdog-line-1',
            external_player_id='underdog-player-1',
            external_match_id='underdog-match-1',
            player=player,
            game=game,
            player_name='Example Player',
            team_name='Atlanta FaZe',
            opponent_name='OpTic Texas',
            title='CoD: Example Player Kills on Game 1 O/U',
            display_stat='Kills on Game 1',
            series_game_number=1,
            stat_type='KILLS',
            line=Decimal('23.500'),
            status='ACTIVE',
            resolution_status='RESOLVED',
            scheduled_at=timezone.make_aware(datetime(2026, 1, 15, 19, 30)),
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
        self.assertContains(response, 'Underdog')
        self.assertContains(response, 'Game 1 Kills')

    def test_matches_page_handles_imported_game_without_betting_lines(self):
        BettingLine.objects.all().delete()
        UnderdogMarket.objects.all().delete()

        response = self.client.get(reverse('matches'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Player performance')
        self.assertNotContains(response, '<th class="px-4 py-3 font-medium">Market</th>', html=True)


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
class DashboardViewTests(TestCase):
    def setUp(self):
        player = Player.objects.create(name='Example Player')
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
        self.game = Game.objects.create(
            pool_entry=pool_entry,
            source=GameSource.LAN,
            opponent='Team B',
            source_id='breakingpoint-game-1',
            event_date=timezone.make_aware(datetime(2026, 1, 15, 19, 30)),
        )
        PlayerGameStat.objects.create(
            player=player,
            game=self.game,
            kills=24,
            deaths=16,
            team='Team A',
        )
        opponent_player = Player.objects.create(name='Opponent Player')
        PlayerGameStat.objects.create(
            player=opponent_player,
            game=self.game,
            kills=18,
            deaths=20,
            team='Team B',
        )
        UnderdogMarket.objects.create(
            external_id='underdog-line-1',
            external_player_id='underdog-player-1',
            external_match_id='underdog-match-1',
            player=player,
            game=self.game,
            player_name='Example Player',
            team_name='Team A',
            opponent_name='Team B',
            title='CoD: Example Player Kills on Game 1 O/U',
            display_stat='Kills on Game 1',
            series_game_number=1,
            stat_type='KILLS',
            line=Decimal('20.500'),
            status='ACTIVE',
            resolution_status='RESOLVED',
            scheduled_at=timezone.make_aware(datetime(2026, 1, 15, 19, 30)),
        )
        UnderdogMarket.objects.create(
            external_id='underdog-line-upcoming',
            external_player_id='underdog-player-2',
            external_match_id='underdog-match-2',
            player_name='Someone Else',
            team_name='Team A',
            opponent_name='Team C',
            title='CoD: Someone Else Kills on Game 1 O/U',
            display_stat='Kills on Game 1',
            series_game_number=1,
            stat_type='KILLS',
            line=Decimal('19.500'),
            status='ACTIVE',
            resolution_status='PENDING',
            scheduled_at=timezone.now() + timedelta(days=2),
        )

    def test_dashboard_renders_upcoming_matches_and_hit_rate(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertContains(response, 'Upcoming matches')
        self.assertContains(response, 'Team A vs. Team C')
        self.assertContains(response, 'Hit rate tracker')
        self.assertContains(response, 'Example Player')
        self.assertContains(response, 'Recent results')
        self.assertContains(response, 'Hacienda')
        self.assertContains(response, 'Update betting lines')
        self.assertContains(response, 'Team A vs. Team B')

    def test_dashboard_handles_no_data(self):
        UnderdogMarket.objects.all().delete()
        PlayerGameStat.objects.all().delete()
        Game.objects.all().delete()

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No upcoming matches scheduled.')
        self.assertContains(response, 'No resolved lines yet.')
        self.assertContains(response, 'No games have been recorded.')

    def test_dashboard_rejects_map_that_is_not_legal_for_slots_mode(self):
        raid = GameMap.objects.create(name='Raid')
        search = GameMode.objects.create(name='Search & Destroy')
        StageMapPoolEntry.objects.create(
            stage=self.game.stage,
            game_map=raid,
            mode=search,
        )

        response = self.client.get(reverse('dashboard'), {
            'team_a': 'Team A',
            'team_b': 'Team B',
            'map_1': 'Raid',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'That map is not valid for its series slot')
        self.assertEqual(response.context['edges'], [])
        map_one = response.context['map_slots'][0]
        map_two = response.context['map_slots'][1]
        self.assertNotIn('Raid', map_one['choices'])
        self.assertIn('Raid', map_two['choices'])


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
class TeamsViewTests(TestCase):
    def setUp(self):
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
            opponent='Los Angeles Thieves',
            source_id='breakingpoint-team-game-1',
            event_date=timezone.make_aware(datetime(2026, 1, 15, 19, 30)),
        )
        optic_player = Player.objects.create(name='OpTic Player')
        ProfessionalRoster.objects.create(
            season=2026,
            team_name='OpTic Texas',
            player=optic_player,
        )
        PlayerGameStat.objects.create(
            player=optic_player,
            game=game,
            kills=24,
            deaths=16,
            team='OpTic Texas',
        )
        PlayerGameStat.objects.create(
            player=Player.objects.create(name='Former OpTic Player'),
            game=game,
            kills=18,
            deaths=20,
            team='OpTic Texas',
        )

    def test_teams_page_displays_derived_team_stats(self):
        response = self.client.get(reverse('teams'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'teams.html')
        self.assertContains(response, 'Historical team performance')
        self.assertContains(response, 'OpTic Texas')
        self.assertContains(response, 'FaZe Vegas')
        self.assertNotContains(response, 'Former OpTic Player')
        self.assertContains(response, '24')
        self.assertContains(response, '1.50')
        self.assertContains(
            response,
            'href="/players/#team-optic-texas"',
            html=False,
        )

    def test_players_page_has_team_anchor_and_highlight_script(self):
        response = self.client.get(reverse('players'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="team-optic-texas"', html=False)
        self.assertContains(response, 'team-card-highlight')

    def test_teams_page_handles_no_data(self):
        PlayerGameStat.objects.all().delete()
        Game.objects.all().delete()

        response = self.client.get(reverse('teams'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No team statistics have been imported')


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
class RefreshBettingLinesViewTests(TestCase):
    def setUp(self):
        Player.objects.create(name='Huke')
        CompetitionStage.objects.create(
            name='Major 1',
            season=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
        )

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse('refresh_betting_lines'))
        self.assertEqual(response.status_code, 405)

    @patch('src.views.sync_breakingpoint_stats')
    def test_post_syncs_and_redirects_with_success_message(self, mock_sync):
        mock_sync.return_value = BreakingPointSyncResult(
            fetched_count=1, games_created=1, players_created=0, stats_written=1,
        )

        response = self.client.post(reverse('refresh_betting_lines'), follow=True)

        mock_sync.assert_called_once_with(season=2026, player_tags=['Huke'])
        self.assertRedirects(response, reverse('dashboard'))
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn('Synced 1 new games', str(messages[0]))

    @patch('src.views.sync_breakingpoint_stats')
    def test_post_shows_warning_when_no_stats_found(self, mock_sync):
        mock_sync.return_value = BreakingPointSyncResult(fetched_count=0)

        response = self.client.post(reverse('refresh_betting_lines'), follow=True)

        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn('No Breaking Point stats found', str(messages[0]))

    @patch('src.views.sync_breakingpoint_stats')
    def test_post_shows_error_on_breakingpoint_failure(self, mock_sync):
        mock_sync.side_effect = BreakingPointError('token expired')

        response = self.client.post(reverse('refresh_betting_lines'), follow=True)

        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn('token expired', str(messages[0]))

    def test_post_without_players_shows_error(self):
        Player.objects.all().delete()

        response = self.client.post(reverse('refresh_betting_lines'), follow=True)

        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn('Add at least one competition stage and player', str(messages[0]))
