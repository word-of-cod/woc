from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from src.models import (
    CompetitionStage,
    Game,
    GameMap,
    GameMode,
    Player,
    PlayerGameStat,
    StageMapPoolEntry,
)

EVENTS = {
    10: {'id': 10, 'name': 'Major 1', 'start_date': '2026-01-01', 'end_date': '2026-02-01'},
}
MATCHES = {
    100: {'id': 100, 'team_1_id': 1, 'team_2_id': 2},
}
TEAMS = {
    1: {'id': 1, 'name': 'Team A'},
    2: {'id': 2, 'name': 'Team B'},
}
MODES = {
    1: {'id': 1, 'name': 'Hardpoint', 'short_name': 'HP'},
}
MAPS = {
    5: {'id': 5, 'name': 'TestMap'},
}


def make_stat_row(**overrides):
    row = {
        'game_id': 'game-uuid-1',
        'player_id': 39,
        'player_tag': 'Huke',
        'team_id': 1,
        'match_id': 100,
        'event_id': 10,
        'mode_id': 1,
        'map_id': 5,
        'datetime': '2026-01-15T19:30:00+00:00',
        'event_type': 'Offline',
        'season_id': 2026,
        'kills': 20,
        'deaths': 10,
        'damage': 1000,
        'assists': 5,
    }
    row.update(overrides)
    return row


def make_client_mock(stats, events=None, matches=None, teams=None, modes=None, maps=None):
    client = MagicMock()
    client.fetch_player_stats.return_value = stats
    client.fetch_modes.return_value = modes if modes is not None else MODES
    client.fetch_maps.return_value = maps if maps is not None else MAPS
    client.fetch_events.return_value = events if events is not None else EVENTS
    client.fetch_matches.return_value = matches if matches is not None else MATCHES
    client.fetch_teams.return_value = teams if teams is not None else TEAMS
    return client


@patch('src.management.commands.pull_breakingpoint_stats.BreakingPointClient')
class PullBreakingPointStatsCommandTests(TestCase):
    def test_creates_expected_records(self, mock_client_cls):
        stats = [
            make_stat_row(),
            make_stat_row(player_id=29, player_tag='Simp', team_id=2, kills=15, deaths=12),
        ]
        mock_client_cls.return_value = make_client_mock(stats)

        call_command('pull_breakingpoint_stats', season=2026, players='Huke,Simp', verbosity=0)

        self.assertEqual(Player.objects.count(), 2)
        self.assertEqual(Game.objects.count(), 1)
        self.assertEqual(PlayerGameStat.objects.count(), 2)
        self.assertEqual(GameMap.objects.get().name, 'TestMap')
        self.assertEqual(GameMode.objects.get().name, 'Hardpoint')
        self.assertEqual(CompetitionStage.objects.get().name, 'Major 1')

        game = Game.objects.get()
        self.assertEqual(game.source_id, 'game-uuid-1')
        self.assertEqual(game.opponent, 'Team B')
        self.assertEqual(game.get_source_display(), 'LAN')

        huke_stat = PlayerGameStat.objects.get(player__name='Huke')
        self.assertEqual(huke_stat.kills, 20)
        self.assertEqual(huke_stat.deaths, 10)
        self.assertEqual(huke_stat.team, 'Team A')

        simp_stat = PlayerGameStat.objects.get(player__name='Simp')
        self.assertEqual(simp_stat.kills, 15)
        self.assertEqual(simp_stat.team, 'Team B')

    def test_command_is_idempotent(self, mock_client_cls):
        stats = [make_stat_row()]
        mock_client_cls.return_value = make_client_mock(stats)

        call_command('pull_breakingpoint_stats', season=2026, players='Huke', verbosity=0)
        call_command('pull_breakingpoint_stats', season=2026, players='Huke', verbosity=0)

        self.assertEqual(Game.objects.count(), 1)
        self.assertEqual(Player.objects.count(), 1)
        self.assertEqual(PlayerGameStat.objects.count(), 1)
        self.assertEqual(StageMapPoolEntry.objects.count(), 1)

    def test_second_run_updates_existing_stats_instead_of_duplicating(self, mock_client_cls):
        mock_client_cls.return_value = make_client_mock([make_stat_row(kills=20, deaths=10)])
        call_command('pull_breakingpoint_stats', season=2026, players='Huke', verbosity=0)

        mock_client_cls.return_value = make_client_mock([make_stat_row(kills=30, deaths=5)])
        call_command('pull_breakingpoint_stats', season=2026, players='Huke', verbosity=0)

        self.assertEqual(PlayerGameStat.objects.count(), 1)
        stat = PlayerGameStat.objects.get()
        self.assertEqual(stat.kills, 30)
        self.assertEqual(stat.deaths, 5)

    def test_skips_game_with_missing_event_reference(self, mock_client_cls):
        stats = [make_stat_row(event_id=999)]
        mock_client_cls.return_value = make_client_mock(stats, events={})

        call_command('pull_breakingpoint_stats', season=2026, players='Huke', verbosity=0)

        self.assertEqual(Game.objects.count(), 0)
        self.assertEqual(Player.objects.count(), 0)

    def test_skips_game_with_missing_match_reference(self, mock_client_cls):
        stats = [make_stat_row()]
        mock_client_cls.return_value = make_client_mock(stats, matches={})

        call_command('pull_breakingpoint_stats', season=2026, players='Huke', verbosity=0)

        self.assertEqual(Game.objects.count(), 0)

    def test_skips_game_with_unrecognized_event_type(self, mock_client_cls):
        stats = [make_stat_row(event_type='')]
        mock_client_cls.return_value = make_client_mock(stats)

        call_command('pull_breakingpoint_stats', season=2026, players='Huke', verbosity=0)

        self.assertEqual(Game.objects.count(), 0)

    def test_lan_event_type_variant_is_recognized(self, mock_client_cls):
        stats = [make_stat_row(event_type='LAN')]
        mock_client_cls.return_value = make_client_mock(stats)

        call_command('pull_breakingpoint_stats', season=2026, players='Huke', verbosity=0)

        self.assertEqual(Game.objects.get().get_source_display(), 'LAN')

    def test_online_event_type_maps_to_online_source(self, mock_client_cls):
        stats = [make_stat_row(event_type='Online')]
        mock_client_cls.return_value = make_client_mock(stats)

        call_command('pull_breakingpoint_stats', season=2026, players='Huke', verbosity=0)

        self.assertEqual(Game.objects.get().get_source_display(), 'Online')

    def test_missing_map_or_mode_falls_back_to_placeholder_name(self, mock_client_cls):
        stats = [make_stat_row(map_id=999, mode_id=999)]
        mock_client_cls.return_value = make_client_mock(stats, modes={}, maps={})

        call_command('pull_breakingpoint_stats', season=2026, players='Huke', verbosity=0)

        self.assertEqual(GameMap.objects.get().name, 'Map 999')
        self.assertEqual(GameMode.objects.get().name, 'Mode 999')

    def test_requires_at_least_one_player_tag(self, mock_client_cls):
        with self.assertRaises(CommandError):
            call_command('pull_breakingpoint_stats', season=2026, players='  ,  ', verbosity=0)

    def test_no_stats_found_does_not_error(self, mock_client_cls):
        mock_client_cls.return_value = make_client_mock([])

        call_command('pull_breakingpoint_stats', season=2026, players='Nobody', verbosity=0)

        self.assertEqual(Game.objects.count(), 0)
        self.assertEqual(Player.objects.count(), 0)
