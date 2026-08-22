"""Test data for validating the behavior of ``algo1.py``."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class TestPlayer:
	player_id: int
	name: str


@dataclass
class TestMarket:
	underdog_market_id: int
	player: TestPlayer
	player_id: int
	stat_type: str
	line: Decimal
	market_scope: str
	series_game_number: int


@dataclass
class TestPlayerGameStat:
	kills: int
	deaths: int


kenny = TestPlayer(player_id=1, name="Kenny")
shotzzy = TestPlayer(player_id=2, name="Shotzzy")
simp = TestPlayer(player_id=3, name="Simp")

testMarkets = [
	TestMarket(1, kenny, kenny.player_id, "KILLS", Decimal("21.5"), "SINGLE_GAME", 1),
	TestMarket(2, shotzzy, shotzzy.player_id, "KILLS", Decimal("6.5"), "SINGLE_GAME", 2),
	TestMarket(3, simp, simp.player_id, "KILLS", Decimal("24.5"), "SINGLE_GAME", 3),
]

testPlayerHistory = {
	1: [TestPlayerGameStat(kills=22, deaths=18), TestPlayerGameStat(kills=20, deaths=21),TestPlayerGameStat(kills=25, deaths=18), TestPlayerGameStat(kills=19, deaths=21)],
	2: [TestPlayerGameStat(kills=11, deaths=4), TestPlayerGameStat(kills=8, deaths=8),TestPlayerGameStat(kills=2, deaths=9), TestPlayerGameStat(kills=10, deaths=3)],
	3: [TestPlayerGameStat(kills=25, deaths=19), TestPlayerGameStat(kills=24, deaths=20), TestPlayerGameStat(kills=22, deaths=18), TestPlayerGameStat(kills=20, deaths=21)],
}


