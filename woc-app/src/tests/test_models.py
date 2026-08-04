from datetime import date, datetime
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
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


class SchemaModelTests(TestCase):
    def setUp(self):
        self.player = Player.objects.create(
            name="Example Player",
        )

        self.game_map = GameMap.objects.create(
            name="Hacienda",
        )

        self.hardpoint = GameMode.objects.create(
            name="Hardpoint",
        )

        self.stage = CompetitionStage.objects.create(
            name="Major 1",
            season=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
        )

        self.pool_entry = StageMapPoolEntry.objects.create(
            stage=self.stage,
            game_map=self.game_map,
            mode=self.hardpoint,
        )

        self.game = Game.objects.create(
            pool_entry=self.pool_entry,
            source=GameSource.ONLINE,
            opponent="Example Opponent",
            event_date=timezone.make_aware(
                datetime(2026, 1, 15, 19, 30)
            ),
        )

    def test_game_gets_map_mode_and_stage_from_pool_entry(self):
        self.assertEqual(
            self.game.game_map,
            self.game_map,
        )
        self.assertEqual(
            self.game.mode,
            self.hardpoint,
        )
        self.assertEqual(
            self.game.stage,
            self.stage,
        )

    def test_same_map_can_return_in_later_stage(self):
        later_stage = CompetitionStage.objects.create(
            name="Major 3",
            season=2026,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 6, 30),
        )

        later_pool_entry = StageMapPoolEntry.objects.create(
            stage=later_stage,
            game_map=self.game_map,
            mode=self.hardpoint,
        )

        self.assertNotEqual(
            self.pool_entry.pool_entry_id,
            later_pool_entry.pool_entry_id,
        )
        self.assertEqual(
            later_pool_entry.game_map,
            self.game_map,
        )

    def test_pool_combination_cannot_be_duplicated(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StageMapPoolEntry.objects.create(
                    stage=self.stage,
                    game_map=self.game_map,
                    mode=self.hardpoint,
                )

    def test_create_player_game_stat(self):
        stat = PlayerGameStat.objects.create(
            player=self.player,
            game=self.game,
            kills=25,
            deaths=18,
            team="Example Team",
        )

        self.assertEqual(stat.kills, 25)
        self.assertEqual(stat.deaths, 18)
        self.assertEqual(stat.game, self.game)

    def test_player_game_stat_combination_is_unique(self):
        PlayerGameStat.objects.create(
            player=self.player,
            game=self.game,
            kills=25,
            deaths=18,
            team="Example Team",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PlayerGameStat.objects.create(
                    player=self.player,
                    game=self.game,
                    kills=30,
                    deaths=15,
                    team="Example Team",
                )

    def test_create_betting_line(self):
        betting_line = BettingLine.objects.create(
            player=self.player,
            game=self.game,
            market=BettingMarket.KILLS,
            line=Decimal("24.500"),
        )

        self.assertEqual(
            betting_line.line,
            Decimal("24.500"),
        )

    def test_same_betting_market_cannot_be_duplicated(self):
        BettingLine.objects.create(
            player=self.player,
            game=self.game,
            market=BettingMarket.KILLS,
            line=Decimal("24.500"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BettingLine.objects.create(
                    player=self.player,
                    game=self.game,
                    market=BettingMarket.KILLS,
                    line=Decimal("25.500"),
                )