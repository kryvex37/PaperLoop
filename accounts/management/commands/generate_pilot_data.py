from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ml_engine.datasets.pilot import generate_pilot_data


class Command(BaseCommand):
    help = "Generate deterministic synthetic PaperLoop institutions, waste, pickups and recycler candidates."

    def add_arguments(self, parser):
        parser.add_argument("--institutions", type=int, default=80)
        parser.add_argument("--requests", type=int, default=1500)
        parser.add_argument("--months", type=int, default=24)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--output", type=Path)

    def handle(self, *args, **options):
        path = options["output"] or settings.BASE_DIR / "ml_engine" / "datasets" / "data"
        try:
            counts = generate_pilot_data(path, institutions=options["institutions"],
                                         requests=options["requests"], months=options["months"],
                                         seed=options["seed"])
        except (ValueError, OSError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"Generated synthetic pilot data at {path}: {counts}"))
