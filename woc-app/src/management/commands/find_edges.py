from django.core.management.base import BaseCommand

from src.algorithm import main


class Command(BaseCommand):
    help = "Run the edge-finding algorithm against current Underdog markets and print the results."

    def handle(self, *args, **options):
        main()
