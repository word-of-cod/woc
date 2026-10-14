from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable
from src.models import PlayerGameStat, UnderdogMarket
from src.pro_teams import normalize_team_name

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
    market_scope: str
    series_game_number: int | None
    team_name: str
    opponent_name: str

#main meat function... currently has a min_games? not sure if i need that now. might remove and then
#add later when i add recency weighting. also lookback_games is a new param that claude added to limit the 
#number of games to look back on. might remove that too if i add recency weighting
#the current algo does not consider when games happen
def find_edges(
    *,
    min_games: int = 1,
    lookback_games: int | None = None,
    selected_maps: dict[int, str] | None = None,
    team_names: tuple[str, str] | None = None,
) -> list[Edge]:
    markets = load_underdog_markets()
    selected_maps = selected_maps or {}
    if team_names:
        wanted_pair = {normalize_team_name(name) for name in team_names}
        markets = [
            market for market in markets
            if {normalize_team_name(market.team_name), normalize_team_name(market.opponent_name)} == wanted_pair
        ]
    if selected_maps:
        selected_game_numbers = set(selected_maps)
        has_complete_aggregate = {1, 2, 3}.issubset(selected_game_numbers)
        markets = [
            market for market in markets
            if (
                market.market_scope == "SINGLE_GAME"
                and market.series_game_number in selected_game_numbers
            ) or (
                market.market_scope == "GAMES_1_3"
                and has_complete_aggregate
            )
        ]
    player_ids = {market.player_id for market in markets}
    histories = load_player_histories(player_ids)
    edges: list[Edge] = []

    for market in markets:
        player_history = histories.get(market.player_id, [])
        if market.market_scope == "GAMES_1_3" and selected_maps:
            summaries = [
                calculate_average(
                    stats=history_for_map_slot(
                        player_history,
                        game_number,
                        selected_maps.get(game_number),
                        market.opponent_name,
                    ),
                    stat_type=market.stat_type,
                )
                for game_number in range(1, 4)
            ]
            # A series projection needs a usable sample for every included map.
            # Returning no edge is safer than silently substituting zero for a map.
            if any(summary.games_used < min_games for summary in summaries):
                continue
            projection = sum(
                (summary.average for summary in summaries),
                start=Decimal("0"),
            )
        else:
            history = history_for_market(
                player_history,
                market.market_scope,
                market.series_game_number,
                selected_maps,
                market.opponent_name,
            )

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

            projection = summary.average * games_in_scope(market.market_scope)

        difference, recommendation = calculate_edge(
            projection=projection,
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
                projection=projection,
                difference=difference,
                recommendation=recommendation,
                market_scope=market.market_scope,
                series_game_number=market.series_game_number,
                team_name=market.team_name,
                opponent_name=market.opponent_name,
            )
        )

    return edges


def print_edges(edges: list[Edge]) -> None:
    """Print the edges produced by find_edges()."""
    if not edges:
        print("No edges found.")
        return

    for edge in edges:
        projection = edge.projection.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        difference = edge.difference.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        print(
            f"Market {edge.market_id}: {edge.player_name} | "
            f"{edge.stat_type} | line={edge.line} | "
            f"projection={projection} | "
            f"difference={difference} | "
            f"recommendation={edge.recommendation}"
        )


#helper function for getting the value of a stat from a PlayerGameStat object based on the stat type
#needs to be adjusted to include more stat types as they are added to the PlayerGameStat model
def get_stat_value(stat: PlayerGameStat, stat_type: str) -> Decimal:
    if stat_type == "KILLS":
        return Decimal(stat.kills)

    if stat_type == "DEATHS":
        return Decimal(stat.deaths)

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


#number of individual games a market's line represents, used to scale a per-game average up to a
#projection comparable to the line (e.g. a GAMES_1_3 line is a 3-map series total, not a per-game value)
def games_in_scope(marketScope: str) -> int:
    if marketScope == "GAMES_1_3":
        return 3
    return 1


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
    gameNumber: int | None = None,
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
        recommendation = "NO BET / ERROR - market scope or game number not recognized"
    
    return difference, recommendation


#helper functions for loading markets and player history from the database. these functions use Django's ORM 
#to query the database and return lists of UnderdogMarket and PlayerGameStat objects, respectively. they also 
#use select_related to optimize the queries by fetching related player and game objects in a single query.
def load_underdog_markets() -> list[UnderdogMarket]:
    return list(UnderdogMarket.objects
                .filter(player__isnull=False)
                .select_related("player"))
    #uncomment the below for test data querying out of test_algo1.py
    #return test_algo1.testMarkets


#distinct team names appearing among current underdog markets, for populating the
#dashboard's team 1 / team 2 dropdowns.
def list_team_names() -> list[str]:
    names = set()
    for market in load_underdog_markets():
        if market.team_name:
            names.add(market.team_name)
        if market.opponent_name:
            names.add(market.opponent_name)
    return sorted(names)


def load_player_histories(player_ids: Iterable[int]) -> dict[int, list[PlayerGameStat]]:
    stats = (PlayerGameStat.objects
             .filter(player_id__in=player_ids)
             .select_related(
                 "player",
                 "game",
                 "game__pool_entry",
                 "game__pool_entry__mode",
                 "game__pool_entry__game_map",
             )
             .order_by("-game__event_date"))

    histories: dict[int, list[PlayerGameStat]] = {}
    for stat in stats:
        histories.setdefault(stat.player_id, []).append(stat)
    return histories
    #uncomment the below for test data querying out of test_algo1.py
    #return test_algo1.testPlayerHistory

def filterByMode(player_history: list[PlayerGameStat], marketScope: str, gameNumber: int | None) -> list[PlayerGameStat]:
    if marketScope == "SINGLE_GAME" and gameNumber == 1:
        return [stat for stat in player_history if stat.game.mode.name.upper() == "HARDPOINT"]
    elif marketScope == "SINGLE_GAME" and gameNumber == 2:
        return [stat for stat in player_history if stat.game.mode.name.upper() in ("SEARCH & DESTROY", "SEARCH AND DESTROY")]
    elif marketScope == "SINGLE_GAME" and gameNumber == 3:
        return [stat for stat in player_history if stat.game.mode.name.upper() == "OVERLOAD"]
    elif marketScope == "GAMES_1_3":
        return player_history
    else:
        return []

def filterByMap(player_history: list[PlayerGameStat], mapName: str) -> list[PlayerGameStat]:
    normalized_map = mapName.strip().casefold()
    return [
        stat for stat in player_history
        if stat.game.game_map.name.strip().casefold() == normalized_map
    ]

def filterByOpponent(player_history: list[PlayerGameStat], opponentName: str) -> list[PlayerGameStat]:
    normalized_opponent = normalize_team_name(opponentName)
    return [
        stat for stat in player_history
        if normalize_team_name(stat.game.opponent) == normalized_opponent
    ]

def history_for_map_slot(
    player_history: list[PlayerGameStat],
    game_number: int,
    map_name: str | None,
    opponent_name: str,
) -> list[PlayerGameStat]:
    """Return history relevant to one slot in an upcoming series."""
    history = filterByMode(player_history, "SINGLE_GAME", game_number)
    if map_name:
        history = filterByMap(history, map_name)

    # Head-to-head data is useful when it exists, but an all-opponent map sample
    # is preferable to dropping an otherwise valid projection.
    if opponent_name:
        matchup_history = filterByOpponent(history, opponent_name)
        if matchup_history:
            return matchup_history
    return history


def history_for_market(
    player_history: list[PlayerGameStat],
    market_scope: str,
    game_number: int | None,
    selected_maps: dict[int, str],
    opponent_name: str,
) -> list[PlayerGameStat]:
    if market_scope == "SINGLE_GAME" and game_number is not None:
        return history_for_map_slot(
            player_history,
            game_number,
            selected_maps.get(game_number),
            opponent_name,
        )
    return filterByMode(player_history, market_scope, game_number)

def main() -> None:
    edges = find_edges()
    print_edges(edges)
