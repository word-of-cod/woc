from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from src.models import BettingMarket, GameSource
from src.services import (
    add_map_to_stage_pool,
    create_competition_stage,
    create_game,
    create_game_map,
    create_game_mode,
    create_player,
    create_team,
    record_player_result,
    set_betting_line,
)


class ServiceTests(TestCase):
    def setUp(self):
        self.team_one = create_team(name=' Atlanta FaZe ')
        self.team_two = create_team(name='OpTic Texas')
        self.player = create_player(name='Example Player')
        game_map = create_game_map(name='Hacienda')
        mode = create_game_mode(name='Hardpoint')
        stage = create_competition_stage(
            name='Major 1',
            season=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
        )
        self.pool_entry = add_map_to_stage_pool(
            stage=stage,
            game_map=game_map,
            mode=mode,
        )
        self.event_date = timezone.make_aware(
            datetime(2026, 1, 15, 19, 30)
        )

    def test_create_team_normalizes_whitespace(self):
        self.assertEqual(self.team_one.name, 'Atlanta FaZe')

    def test_create_team_rejects_blank_name(self):
        with self.assertRaises(ValueError):
            create_team(name='   ')

    def test_create_game_rejects_date_outside_stage(self):
        with self.assertRaises(ValidationError):
            create_game(
                pool_entry=self.pool_entry,
                source=GameSource.ONLINE,
                team_one=self.team_one,
                team_two=self.team_two,
                event_date=timezone.make_aware(
                    datetime(2026, 3, 1, 12, 0)
                ),
            )

    def test_result_and_line_services_update_existing_records(self):
        game = create_game(
            pool_entry=self.pool_entry,
            source=GameSource.ONLINE,
            team_one=self.team_one,
            team_two=self.team_two,
            event_date=self.event_date,
        )

        record_player_result(
            player=self.player,
            game=game,
            kills=20,
            deaths=15,
            team=self.team_one,
        )
        updated_stat = record_player_result(
            player=self.player,
            game=game,
            kills=25,
            deaths=14,
            team=self.team_one,
        )
        set_betting_line(
            player=self.player,
            game=game,
            market=BettingMarket.KILLS,
            line=Decimal('22.500'),
        )
        updated_line = set_betting_line(
            player=self.player,
            game=game,
            market=BettingMarket.KILLS,
            line=Decimal('23.500'),
        )

        self.assertEqual(updated_stat.kills, 25)
        self.assertEqual(updated_line.line, Decimal('23.500'))
