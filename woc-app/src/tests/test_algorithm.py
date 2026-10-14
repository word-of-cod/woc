from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from src.algorithm import filterByMap, find_edges, history_for_map_slot


def stat(*, kills, map_name, mode_name, opponent="Team B"):
    return SimpleNamespace(
        kills=kills,
        deaths=10,
        game=SimpleNamespace(
            game_map=SimpleNamespace(name=map_name),
            mode=SimpleNamespace(name=mode_name),
            opponent=opponent,
        ),
    )


@dataclass
class Player:
    name: str


@dataclass
class Market:
    underdog_market_id: int
    player: Player
    player_id: int
    stat_type: str
    line: Decimal
    market_scope: str
    series_game_number: int | None
    team_name: str = "Team A"
    opponent_name: str = "Team B"


class MapBasedAlgorithmTests(SimpleTestCase):
    def test_map_filter_is_case_and_whitespace_insensitive(self):
        history = [stat(kills=20, map_name="Hacienda", mode_name="Hardpoint")]

        self.assertEqual(filterByMap(history, "  hacienda "), history)

    def test_map_slot_requires_both_the_selected_map_and_slots_mode(self):
        matching = stat(kills=20, map_name="Hacienda", mode_name="Hardpoint")
        wrong_mode = stat(kills=6, map_name="Hacienda", mode_name="Search and Destroy")
        wrong_map = stat(kills=30, map_name="Vault", mode_name="Hardpoint")

        result = history_for_map_slot(
            [matching, wrong_mode, wrong_map], 1, "Hacienda", "",
        )

        self.assertEqual(result, [matching])

    @patch("src.algorithm.load_player_histories")
    @patch("src.algorithm.load_underdog_markets")
    def test_single_game_projection_uses_selected_map(self, load_markets, load_histories):
        market = Market(1, Player("Player One"), 10, "KILLS", Decimal("18.5"), "SINGLE_GAME", 1)
        load_markets.return_value = [market]
        load_histories.return_value = {
            10: [
                stat(kills=20, map_name="Hacienda", mode_name="Hardpoint"),
                stat(kills=30, map_name="Vault", mode_name="Hardpoint"),
            ]
        }

        edges = find_edges(selected_maps={1: "Hacienda"})

        self.assertEqual(edges[0].projection, Decimal("20"))

    @patch("src.algorithm.load_player_histories")
    @patch("src.algorithm.load_underdog_markets")
    def test_selecting_map_one_returns_only_map_one_markets(self, load_markets, load_histories):
        player = Player("Player One")
        load_markets.return_value = [
            Market(1, player, 10, "KILLS", Decimal("18.5"), "SINGLE_GAME", 1),
            Market(2, player, 10, "KILLS", Decimal("6.5"), "SINGLE_GAME", 2),
            Market(3, player, 10, "KILLS", Decimal("50.5"), "GAMES_1_3", None),
        ]
        load_histories.return_value = {
            10: [stat(kills=20, map_name="Den", mode_name="Hardpoint")]
        }

        edges = find_edges(selected_maps={1: "Den"})

        self.assertEqual([edge.market_id for edge in edges], [1])

    @patch("src.algorithm.load_player_histories")
    @patch("src.algorithm.load_underdog_markets")
    def test_games_one_to_three_projection_sums_each_selected_map(self, load_markets, load_histories):
        market = Market(2, Player("Player One"), 10, "KILLS", Decimal("45.5"), "GAMES_1_3", None)
        load_markets.return_value = [market]
        load_histories.return_value = {
            10: [
                stat(kills=20, map_name="Hacienda", mode_name="Hardpoint"),
                stat(kills=8, map_name="Raid", mode_name="Search and Destroy"),
                stat(kills=22, map_name="Vault", mode_name="Overload"),
            ]
        }

        edges = find_edges(selected_maps={1: "Hacienda", 2: "Raid", 3: "Vault"})

        self.assertEqual(edges[0].projection, Decimal("50"))
