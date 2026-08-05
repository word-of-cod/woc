import json
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction
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


class Command(BaseCommand):
    help = 'Idempotently load src/testData1.json into the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=Path,
            default=Path(__file__).resolve().parents[2] / 'testData1.json',
            help='Optional path to a test-data JSON file.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        path = options['path']
        data = self._read_data(path)

        players = data.get('Players', [])
        games = data.get('Matches', [])
        stats = data.get('Player_Match_Stats', [])
        lines = data.get('BETTING_LINES', [])
        self._validate(players, games, stats, lines)

        parsed_dates = [self._parse_date(row['event_date']) for row in games]
        stage, _ = CompetitionStage.objects.update_or_create(
            season=2026,
            name='Test Data',
            defaults={
                'start_date': min(parsed_dates),
                'end_date': max(parsed_dates),
            },
        )

        players_by_id = {}
        for row in players:
            player, _ = Player.objects.update_or_create(
                player_id=row['player_id'],
                defaults={'name': row['name'].strip()},
            )
            players_by_id[row['player_id']] = player

        games_by_id = {}
        for row in games:
            game_map, _ = GameMap.objects.get_or_create(name=row['map'].strip())
            mode, _ = GameMode.objects.get_or_create(name=row['mode'].strip())
            pool_entry, _ = StageMapPoolEntry.objects.get_or_create(
                stage=stage,
                game_map=game_map,
                mode=mode,
            )
            event_date = timezone.make_aware(
                datetime.combine(self._parse_date(row['event_date']), time(hour=12))
            )
            game, _ = Game.objects.update_or_create(
                game_id=row['match_id'],
                defaults={
                    'pool_entry': pool_entry,
                    'source': row['source'],
                    'opponent': row['opponent'].strip(),
                    'event_date': event_date,
                },
            )
            games_by_id[row['match_id']] = game

        for row in stats:
            PlayerGameStat.objects.update_or_create(
                player=players_by_id[row['player_id']],
                game=games_by_id[row['match_id']],
                defaults={
                    'kills': row['kills'],
                    'deaths': row['deaths'],
                    'team': row['team_at_match_time'].strip(),
                },
            )

        market_map = {
            'M1': BettingMarket.MAP_1_KILLS,
            'M2': BettingMarket.MAP_2_KILLS,
            'M3': BettingMarket.MAP_3_KILLS,
        }
        BettingLine.objects.filter(
            player_id__in=players_by_id,
            game_id__in=games_by_id,
            market__in=('KILLS', 'DEATHS'),
        ).delete()
        for row in lines:
            BettingLine.objects.update_or_create(
                player=players_by_id[row['player_id']],
                game=games_by_id[row['match_id']],
                market=market_map[row['market']],
                defaults={'line': Decimal(str(row['line']))},
            )

        self._reset_sequences()
        self.stdout.write(
            self.style.SUCCESS(
                f'Loaded {len(players)} players, {len(games)} games, '
                f'{len(stats)} stats, and {len(lines)} betting lines.'
            )
        )

    @staticmethod
    def _read_data(path):
        if not path.exists():
            raise CommandError(f'Test-data file does not exist: {path}')
        try:
            return json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'Unable to read test data: {exc}') from exc

    @staticmethod
    def _parse_date(value):
        try:
            return datetime.strptime(value, '%m/%d/%Y').date()
        except (TypeError, ValueError) as exc:
            raise CommandError(
                f'Invalid event date {value!r}; expected MM/DD/YYYY.'
            ) from exc

    @staticmethod
    def _validate(players, games, stats, lines):
        if not players or not games:
            raise CommandError('Test data must contain Players and Matches.')

        player_ids = [row['player_id'] for row in players]
        game_ids = [row['match_id'] for row in games]
        player_id_set = set(player_ids)
        game_id_set = set(game_ids)

        if len(player_ids) != len(player_id_set):
            raise CommandError('Players contains duplicate player_id values.')
        if len(game_ids) != len(game_id_set):
            raise CommandError('Matches contains duplicate match_id values.')

        valid_sources = set(GameSource.values)
        valid_markets = {'M1', 'M2', 'M3'}
        stat_keys = set()
        line_keys = set()

        for row in games:
            if row['source'] not in valid_sources:
                raise CommandError(f"Invalid game source: {row['source']!r}")

        for row in stats:
            key = (row['player_id'], row['match_id'])
            if row['player_id'] not in player_id_set or row['match_id'] not in game_id_set:
                raise CommandError(f'Stat references an unknown player or match: {key}')
            if key in stat_keys:
                raise CommandError(f'Duplicate player/match stat: {key}')
            if row['kills'] < 0 or row['deaths'] < 0:
                raise CommandError(f'Stat has negative kills or deaths: {key}')
            stat_keys.add(key)

        for row in lines:
            key = (row['player_id'], row['match_id'], row['market'])
            if row['player_id'] not in player_id_set or row['match_id'] not in game_id_set:
                raise CommandError(f'Line references an unknown player or match: {key}')
            if row['market'] not in valid_markets:
                raise CommandError(f"Invalid betting market: {row['market']!r}")
            if Decimal(str(row['line'])) < 0:
                raise CommandError(f'Betting line is negative: {key}')
            if key in line_keys:
                raise CommandError(f'Duplicate betting line: {key}')
            line_keys.add(key)

    @staticmethod
    def _reset_sequences():
        statements = connection.ops.sequence_reset_sql(
            no_style(),
            [Player, Game, GameMap, GameMode, CompetitionStage, StageMapPoolEntry],
        )
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
