from datetime import date, datetime, timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from src.analytics import hit_rate_summary, matchup_label, suggested_side
from src.models import (
    BettingMarket,
    BettingLine,
    CompetitionStage,
    Game,
    GameMap,
    GameMode,
    GameSource,
    Player,
    PlayerGameStat,
    StageMapPoolEntry,
    UnderdogMarket,
)
from src.selectors import upcoming_match_schedule


class SuggestedSideTests(SimpleTestCase):
    def test_suggests_over_when_average_beats_line(self):
        self.assertEqual(suggested_side(values=[25, 27, 26], line=Decimal('20.5')), 'OVER')

    def test_suggests_under_when_average_is_below_line(self):
        self.assertEqual(suggested_side(values=[10, 12, 11], line=Decimal('20.5')), 'UNDER')

    def test_no_suggestion_without_history(self):
        self.assertIsNone(suggested_side(values=[], line=Decimal('20.5')))

    def test_no_suggestion_on_exact_average_match(self):
        self.assertIsNone(suggested_side(values=[20, 20], line=Decimal('20')))


class MatchupLabelTests(SimpleTestCase):
    def test_joins_both_teams_when_two_are_recorded(self):
        # Callers pass an already-sorted list; the helper just joins it as given.
        label = matchup_label(team_names=['Team A', 'Team B'], opponent='Team B')
        self.assertEqual(label, 'Team A vs. Team B')

    def test_falls_back_to_opponent_column_with_one_team(self):
        label = matchup_label(team_names=['Team A'], opponent='Team B')
        self.assertEqual(label, 'Team A vs. Team B')

    def test_falls_back_to_unknown_team_with_no_stats(self):
        label = matchup_label(team_names=[], opponent='Team B')
        self.assertEqual(label, 'Unknown team vs. Team B')


class HitRateSummaryTests(TestCase):
    def setUp(self):
        self.player = Player.objects.create(name='Example Player')
        game_map = GameMap.objects.create(name='Hacienda')
        mode = GameMode.objects.create(name='Hardpoint')
        stage = CompetitionStage.objects.create(
            name='Major 1',
            season=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 1),
        )
        pool_entry = StageMapPoolEntry.objects.create(
            stage=stage, game_map=game_map, mode=mode,
        )

        self.games = []
        for day, kills in ((1, 30), (8, 32), (15, 35)):
            game = Game.objects.create(
                pool_entry=pool_entry,
                source=GameSource.LAN,
                opponent='Team B',
                event_date=timezone.make_aware(datetime(2026, 1, day, 19, 0)),
            )
            PlayerGameStat.objects.create(
                player=self.player, game=game, kills=kills, deaths=15, team='Team A',
            )
            self.games.append(game)

    def test_correctly_predicts_a_line_using_other_games_average(self):
        # Player's other two games average 31 kills, comfortably above this
        # line, and the target game also clears it, so the suggestion hits.
        BettingLine.objects.create(
            player=self.player,
            game=self.games[2],
            market=BettingMarket.MAP_1_KILLS,
            line=Decimal('20.5'),
        )

        summary = hit_rate_summary()

        self.assertEqual(summary['decided'], 1)
        self.assertEqual(summary['hits'], 1)
        self.assertEqual(summary['rate'], 100.0)
        self.assertEqual(summary['entries'][0]['suggestion'], 'OVER')
        self.assertEqual(summary['entries'][0]['outcome'], 'OVER')
        self.assertTrue(summary['entries'][0]['is_hit'])

    def test_lines_without_a_recorded_stat_are_ignored(self):
        other_player = Player.objects.create(name='No Stats Player')
        BettingLine.objects.create(
            player=other_player,
            game=self.games[0],
            market=BettingMarket.MAP_1_KILLS,
            line=Decimal('20.5'),
        )

        summary = hit_rate_summary()

        self.assertEqual(summary['decided'], 0)
        self.assertIsNone(summary['rate'])
        self.assertEqual(summary['entries'], [])

    def test_includes_resolved_underdog_markets(self):
        UnderdogMarket.objects.create(
            external_id='underdog-line-1',
            external_player_id='underdog-player-1',
            external_match_id='underdog-match-1',
            player=self.player,
            game=self.games[0],
            player_name='Example Player',
            team_name='Team A',
            opponent_name='Team B',
            title='CoD: Example Player Kills on Game 1 O/U',
            display_stat='Kills on Game 1',
            series_game_number=1,
            stat_type='KILLS',
            line=Decimal('15.5'),
            status='ACTIVE',
            resolution_status='RESOLVED',
        )

        summary = hit_rate_summary()

        self.assertEqual(summary['decided'], 1)
        self.assertEqual(summary['entries'][0]['player_name'], 'Example Player')


class UpcomingMatchScheduleTests(TestCase):
    def test_dedupes_by_match_and_excludes_past_matches(self):
        UnderdogMarket.objects.create(
            external_id='past-line',
            external_player_id='p1',
            external_match_id='match-past',
            player_name='Past Player',
            team_name='Team A',
            opponent_name='Team B',
            title='past',
            display_stat='Kills on Game 1',
            series_game_number=1,
            stat_type='KILLS',
            line=Decimal('10'),
            scheduled_at=timezone.now() - timedelta(days=1),
        )
        for market_stat in ('KILLS', 'DEATHS'):
            UnderdogMarket.objects.create(
                external_id=f'future-line-{market_stat}',
                external_player_id='p2',
                external_match_id='match-future',
                player_name='Future Player',
                team_name='Team C',
                opponent_name='Team D',
                title='future',
                display_stat=f'{market_stat} on Game 1',
                series_game_number=1,
                stat_type=market_stat,
                line=Decimal('10'),
                scheduled_at=timezone.now() + timedelta(days=1),
            )

        schedule = upcoming_match_schedule()

        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule[0]['external_match_id'], 'match-future')
        self.assertEqual(schedule[0]['team_name'], 'Team C')
        self.assertEqual(schedule[0]['opponent_name'], 'Team D')
