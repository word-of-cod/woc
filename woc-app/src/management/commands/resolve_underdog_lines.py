from django.core.management.base import BaseCommand

from src.services.underdog import resolve_unresolved_markets


class Command(BaseCommand):
    help = 'Retry player/game resolution for unresolved Underdog markets.'

    def handle(self, *args, **options):
        counters = resolve_unresolved_markets()
        summary = ', '.join(
            f'{status.lower()}={count}'
            for status, count in counters.items()
            if count
        ) or 'no unresolved markets'
        self.stdout.write(self.style.SUCCESS(
            f'Underdog resolution complete: {summary}.'
        ))
