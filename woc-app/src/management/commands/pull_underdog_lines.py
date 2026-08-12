from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from src.models import UnderdogMarket
from src.services.underdog import resolve_market
from src.underdog_client import UnderdogClient, UnderdogError
from src.underdog_parser import parse_payload


class Command(BaseCommand):
    help = 'Fetch supported Call of Duty markets from Underdog and upsert them.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch and parse markets without writing to PostgreSQL.',
        )
        parser.add_argument(
            '--no-resolve',
            action='store_true',
            help='Store markets without attempting player/game resolution.',
        )

    def handle(self, *args, **options):
        try:
            payload = UnderdogClient().fetch_esports_lines()
        except UnderdogError as exc:
            raise CommandError(str(exc)) from exc

        parsed_markets, parse_counts = parse_payload(payload)
        self.stdout.write(
            'Fetched {fetched}; supported {supported}; skipped non-CoD '
            '{skipped_not_cod}; skipped unsupported {skipped_unsupported}; '
            'skipped invalid {skipped_invalid}.'.format(**parse_counts)
        )

        if options['dry_run']:
            for market in parsed_markets:
                self.stdout.write(
                    f'{market.player_name}: '
                    f'{"Games 1-3" if market.series_game_number is None else f"Game {market.series_game_number}"} '
                    f'{market.stat_type} {market.line} '
                    f'({market.team_name} vs. {market.opponent_name})'
                )
            self.stdout.write(self.style.SUCCESS('Dry run complete; no rows written.'))
            return

        created_count = 0
        updated_count = 0
        resolution_counts = {}

        with transaction.atomic():
            for parsed in parsed_markets:
                market, created = UnderdogMarket.objects.update_or_create(
                    external_id=parsed.external_id,
                    defaults={
                        'stable_id': parsed.stable_id,
                        'external_player_id': parsed.external_player_id,
                        'external_match_id': parsed.external_match_id,
                        'player_name': parsed.player_name,
                        'team_name': parsed.team_name,
                        'opponent_name': parsed.opponent_name,
                        'title': parsed.title,
                        'display_stat': parsed.display_stat,
                        'market_scope': parsed.market_scope,
                        'series_game_number': parsed.series_game_number,
                        'stat_type': parsed.stat_type,
                        'line': parsed.line,
                        'status': parsed.status,
                        'scheduled_at': parsed.scheduled_at,
                        'expires_at': parsed.expires_at,
                        'source_updated_at': parsed.source_updated_at,
                        'raw_payload': parsed.raw_payload,
                    },
                )
                created_count += int(created)
                updated_count += int(not created)

                if not options['no_resolve']:
                    resolve_market(market)
                    resolution_counts[market.resolution_status] = (
                        resolution_counts.get(market.resolution_status, 0) + 1
                    )

        resolution_summary = ', '.join(
            f'{status.lower()}={count}'
            for status, count in sorted(resolution_counts.items())
        ) or 'resolution skipped'
        self.stdout.write(self.style.SUCCESS(
            f'Underdog sync complete: created={created_count}, '
            f'updated={updated_count}, {resolution_summary}.'
        ))
