from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from src.models import (
    CompetitionStage,
    Game,
    GameMap,
    GameMode,
    GameSource,
    Player,
    PlayerAlias,
    PlayerGameStat,
    ResolutionStatus,
    StageMapPoolEntry,
    UnderdogMarket,
)
from src.underdog_client import UnderdogClient, UnderdogError
from src.underdog_parser import parse_payload
from src.underdog_service import resolve_market


def underdog_payload(*, stat='kills_on_game_1', title='CoD: Simp Kills on Game 1 O/U'):
    return {
        'over_under_lines': [{
            'id': 'line-1',
            'stable_id': 'stable-1|balanced',
            'stat_value': '24.5',
            'status': 'active',
            'updated_at': '2026-08-05T12:00:00Z',
            'over_under': {
                'title': title,
                'appearance_stat': {
                    'appearance_id': 'appearance-1',
                    'display_stat': 'Kills on Game 1',
                    'stat': stat,
                },
            },
        }],
        'appearances': [{
            'id': 'appearance-1',
            'match_id': 101,
            'player_id': 'underdog-player-1',
            'team_id': 'away-team',
        }],
        'players': [{
            'id': 'underdog-player-1',
            'first_name': 'CoD:',
            'last_name': 'Simp',
        }],
        'games': [{
            'id': 101,
            'away_team_id': 'away-team',
            'home_team_id': 'home-team',
            'full_team_names_title': 'Atlanta FaZe @ OpTic Texas',
            'scheduled_at': '2026-08-06T19:00:00Z',
        }],
    }


class UnderdogClientTests(SimpleTestCase):
    @override_settings(
        UNDERDOG_BASE_URL='https://example.test',
        UNDERDOG_STATE_CONFIG_ID='state-1',
    )
    def test_fetches_public_esports_feed(self):
        response = Mock(status_code=200)
        response.json.return_value = underdog_payload()
        session = Mock()
        session.get.return_value = response

        payload = UnderdogClient(session=session).fetch_esports_lines()

        self.assertEqual(payload['over_under_lines'][0]['id'], 'line-1')
        _, kwargs = session.get.call_args
        self.assertNotIn('Authorization', kwargs['headers'])
        self.assertEqual(kwargs['params']['sport_id'], 'esports')

    @override_settings(
        UNDERDOG_BASE_URL='https://example.test',
        UNDERDOG_STATE_CONFIG_ID='state-1',
    )
    def test_rejects_non_success_response(self):
        response = Mock(status_code=503, text='unavailable')
        session = Mock()
        session.get.return_value = response

        with self.assertRaises(UnderdogError):
            UnderdogClient(session=session).fetch_esports_lines()


class UnderdogParserTests(SimpleTestCase):
    def test_parses_supported_cod_market_and_relationships(self):
        markets, counters = parse_payload(underdog_payload())

        self.assertEqual(counters['supported'], 1)
        self.assertEqual(len(markets), 1)
        market = markets[0]
        self.assertEqual(market.player_name, 'Simp')
        self.assertEqual(market.team_name, 'Atlanta FaZe')
        self.assertEqual(market.opponent_name, 'OpTic Texas')
        self.assertEqual(market.series_game_number, 1)
        self.assertEqual(market.line, Decimal('24.5'))

    def test_parses_games_one_through_three_kills_market(self):
        payload = underdog_payload(
            stat='kills_on_games_1_2_3',
            title='CoD: Simp Kills on Game 1+2+3 O/U',
        )

        markets, counters = parse_payload(payload)

        self.assertEqual(counters['supported'], 1)
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].market_scope, 'GAMES_1_3')
        self.assertIsNone(markets[0].series_game_number)
        self.assertEqual(markets[0].stat_type, 'KILLS')


class UnderdogResolutionTests(TestCase):
    def setUp(self):
        self.player = Player.objects.create(name='Simp')
        game_map = GameMap.objects.create(name='Hacienda')
        mode = GameMode.objects.create(name='Hardpoint')
        stage = CompetitionStage.objects.create(
            name='Major 1',
            season=2026,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
        )
        pool_entry = StageMapPoolEntry.objects.create(
            stage=stage,
            game_map=game_map,
            mode=mode,
        )
        self.game = Game.objects.create(
            pool_entry=pool_entry,
            source=GameSource.ONLINE,
            opponent='OpTic Texas',
            source_id='bp-game-1',
            event_date=timezone.make_aware(datetime(2026, 8, 6, 19, 0)),
        )
        PlayerGameStat.objects.create(
            player=self.player,
            game=self.game,
            kills=27,
            deaths=20,
            team='Atlanta FaZe',
        )

    def test_resolves_player_and_game_using_game_one_mode(self):
        market = UnderdogMarket.objects.create(
            external_id='line-1',
            external_player_id='underdog-player-1',
            external_match_id='101',
            player_name='Simp',
            team_name='Atlanta FaZe',
            opponent_name='OpTic Texas',
            title='CoD: Simp Kills on Game 1 O/U',
            display_stat='Kills on Game 1',
            series_game_number=1,
            stat_type='KILLS',
            line=Decimal('24.5'),
            scheduled_at=timezone.make_aware(datetime(2026, 8, 6, 19, 0)),
        )

        resolve_market(market)

        market.refresh_from_db()
        self.assertEqual(market.player, self.player)
        self.assertEqual(market.game, self.game)
        self.assertEqual(market.resolution_status, ResolutionStatus.RESOLVED)
        self.assertTrue(PlayerAlias.objects.filter(
            external_player_id='underdog-player-1', player=self.player
        ).exists())

    @patch('src.management.commands.pull_underdog_lines.UnderdogClient')
    def test_pull_command_is_idempotent(self, client_class):
        client_class.return_value.fetch_esports_lines.return_value = underdog_payload()

        call_command('pull_underdog_lines', '--no-resolve', stdout=StringIO())
        call_command('pull_underdog_lines', '--no-resolve', stdout=StringIO())

        self.assertEqual(UnderdogMarket.objects.count(), 1)
