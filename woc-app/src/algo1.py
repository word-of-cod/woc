# woc-app/src/algo1.py

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import os
import sys
from typing import Iterable

# Allow ``python algo1.py`` when the working directory is this ``src`` folder.
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    sys.path.pop(1)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from src.models import PlayerGameStat, UnderdogMarket
from src.tests import test_algo1

#class from claude 
@dataclass
class HistorySummary:
    games_used: int
    average: Decimal

#class from claude
@dataclass
class Edge:
    market_id: int 
    player_name: str
    stat_type: str
    line: Decimal
    projection: Decimal
    difference: Decimal
    recommendation: str

#main meat function... currently has a min_games? not sure if i need that now. might remove and then
#add later when i add recency weighting. also lookback_games is a new param that claude added to limit the 
#number of games to look back on. might remove that too if i add recency weighting
#the current algo does not consider when games happen
def find_edges(
    *,
    min_games: int = 1,
    lookback_games: int | None = None,
) -> list[Edge]:
    markets = load_underdog_markets()
    edges: list[Edge] = []

    for market in markets:
        history = filterByMode(load_player_history(market.player_id), market.market_scope, market.series_game_number)

        #claude added this lookback_games param to limit the number of games to look back on. i have removed for now.
        #in general we are going to use the entire history. i might weigh more recent performances harder, but that is all.
        #i cant think of a scenario where we would want to limit the number of games to look back on. if we do, we can add this back in.
        #need to remove the lookback_games param from the function signature if we remove this.
        #if lookback_games is not None:
        #    history = history[:lookback_games]

        summary = calculate_average(
            stats=history,
            stat_type=market.stat_type,
        )

        if summary.games_used < min_games:
            continue

        difference, recommendation = calculate_edge(
            projection=summary.average,
            line=market.line,
            marketScope=market.market_scope,
            gameNumber=market.series_game_number
        )

        edges.append(
            Edge(
                market_id=market.underdog_market_id, #formerly market.id, but changed to underdog_market_id to match the model field name
                player_name=market.player.name,
                stat_type=market.stat_type,
                line=market.line,
                projection=summary.average,
                difference=difference,
                recommendation=recommendation,
            )
        )

    return edges


def print_edges(edges: list[Edge]) -> None:
    """Print the edges produced by find_edges()."""
    if not edges:
        print("No edges found.")
        return

    for edge in edges:
        print(
            f"Market {edge.market_id}: {edge.player_name} | "
            f"{edge.stat_type} | line={edge.line} | "
            f"projection={edge.projection} | "
            f"difference={edge.difference} | "
            f"recommendation={edge.recommendation}"
        )


#helper function for getting the value of a stat from a PlayerGameStat object based on the stat type
#needs to be adjusted to include more stat types as they are added to the PlayerGameStat model
def get_stat_value(stat: PlayerGameStat, stat_type: str) -> Decimal:
    if stat_type == "KILLS":
        return Decimal(stat.kills)

    if stat_type == "DEATHS":
        return Decimal(stat.deaths)

    if stat_type == "GAMES_PLAYED":
        return Decimal(stat.games_played)

    raise ValueError(f"Unsupported stat type: {stat_type}")


#calculates the average of a given stat type from a list of PlayerGameStat objects and returns a 
#HistorySummary object containing the number of games used and the average value. 
#if there are no values, it returns a HistorySummary with 0 games used and an average of 0.
#needs to be updated to include more stat types as they are added to the PlayerGameStat model, 
#and needs to be updated to include recency weighting if that is added to the algo in the future
def calculate_average(
    stats: Iterable[PlayerGameStat],
    stat_type: str,
) -> HistorySummary:
    values = [
        get_stat_value(stat, stat_type)
        for stat in stats
    ]

    if not values:
        return HistorySummary(
            games_used=0,
            average=Decimal("0"),
        )

    average = sum(values) / len(values)

    return HistorySummary(
        games_used=len(values),
        average=average,
    )


#calculates the difference between a projection and a line, and returns the difference along with a 
#recommendation of "OVER", "UNDER", or "PUSH" based on whether the projection is greater than, less than, 
#or equal to the line. needs to be edited to offer an output of "NO BET" if the difference is within a 
#certain threshold, which can be added as a parameter to the function in the future
#possibly can remove the recommendation output and just return the difference, and then have the calling 
#function determine the recommendation based on the difference and a threshold parameter
def calculate_edge(
    *,
    projection: Decimal,
    line: Decimal,
    marketScope: str,
    gameNumber: int = None,
) -> tuple[Decimal, str]:

    ################################################################################
    #this is the part where you need to add the actual logic of the algorithm beyond
    #just doing the average of the kills/game.
    ################################################################################
    
    difference = projection - line

    if marketScope == "SINGLE_GAME" and gameNumber == 1: #if map 1
        if difference > 2:
            recommendation = "STRONG OVER"
        elif difference > 1 and difference <= 2:
            recommendation = "OVER"
        elif difference < -1 and difference >= -2:
            recommendation = "UNDER"
        elif difference < -2:
            recommendation = "STRONG UNDER"
        else:
            recommendation = "NO RECOMMENDATION"
    elif marketScope == "SINGLE_GAME" and gameNumber == 2: #if map 2
        if difference > 1:
            recommendation = "STRONG OVER"
        elif difference > .5 and difference <= 1:
            recommendation = "OVER"
        elif difference < -.5 and difference >= -1:
            recommendation = "UNDER"
        elif difference < -1:
            recommendation = "STRONG UNDER"
        else:
            recommendation = "NO RECOMMENDATION"
    elif marketScope == "SINGLE_GAME" and gameNumber == 3: #if map 3
        if difference > 2:
            recommendation = "STRONG OVER"
        elif difference > 1 and difference <= 2:
            recommendation = "OVER"
        elif difference < -1 and difference >= -2:
            recommendation = "UNDER"
        elif difference < -2:
            recommendation = "STRONG UNDER"
        else:
            recommendation = "NO RECOMMENDATION"
    elif marketScope == "GAMES_1_3": #if maps 1-3
        if difference > 3:
            recommendation = "STRONG OVER"
        elif difference > 1 and difference <= 3:
            recommendation = "OVER"
        elif difference < -1 and difference >= -3:
            recommendation = "UNDER"
        elif difference < -3:
            recommendation = "STRONG UNDER"
        else:
            recommendation = "NO RECOMMENDATION"
    else: 
        recommendation = "NO BET / ERROR- market_id not recognized"
    
    return difference, recommendation


#helper functions for loading markets and player history from the database. these functions use Django's ORM 
#to query the database and return lists of UnderdogMarket and PlayerGameStat objects, respectively. they also 
#use select_related to optimize the queries by fetching related player and game objects in a single query.
def load_underdog_markets() -> list[UnderdogMarket]:
    return list(UnderdogMarket.objects
                .filter(player__isnull=False)
                .select_related("player", "game"))
    #uncomment the below for test data querying out of test_algo1.py
    #return test_algo1.testMarkets
        

def load_player_history(player_id: int) -> list[PlayerGameStat]:
    return list(PlayerGameStat.objects
                .filter(player_id=player_id)
                .select_related("player", "game")
                .order_by("-game__event_date"))
    #uncomment the below for test data querying out of test_algo1.py
    #return test_algo1.testPlayerHistory.get(player_id, [])

def filterByMode(player_history: list[PlayerGameStat], marketScope: str, gameNumber: int) -> list[PlayerGameStat]:
    if marketScope == "SINGLE_GAME" and gameNumber == 1:
        return [stat for stat in player_history if stat.game.number == 1]
    elif marketScope == "SINGLE_GAME" and gameNumber == 2:
        return [stat for stat in player_history if stat.game.number == 2]
    elif marketScope == "SINGLE_GAME" and gameNumber == 3:
        return [stat for stat in player_history if stat.game.number == 3]
    elif marketScope == "GAMES_1_3":
        return player_history
    else:
        return []

def filterByMap(player_history: list[PlayerGameStat], mapName: str) -> list[PlayerGameStat]:
    return [stat for stat in player_history if stat.game.map_name == mapName]

def getMapName() -> str:
    return "map1"  # Placeholder implementation; replace with actual logic to determine the map name later

def main() -> None:
    edges = find_edges()
    print_edges(edges)


if __name__ == "__main__":
    main()