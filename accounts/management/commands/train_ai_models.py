from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ml_engine.training.train_models import train_all_models


class Command(BaseCommand):
    help = "Train and evaluate the synthetic pilot forecasting, recycler-ranking, and aggregation models."

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", type=Path)
        parser.add_argument("--artifact-dir", type=Path)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--epochs", type=int, default=35)

    def handle(self, *args, **options):
        data_dir = options["data_dir"] or settings.BASE_DIR / "ml_engine" / "datasets" / "data"
        artifact_dir = options["artifact_dir"] or settings.BASE_DIR / "ml_engine" / "artifacts"
        required_data = ("weekly_waste.csv", "ranking_candidates.csv", "aggregation_candidates.csv")
        if any(not (data_dir / name).is_file() for name in required_data):
            raise CommandError(f"Pilot data not found under {data_dir}. Run generate_pilot_data first.")
        try:
            metrics = train_all_models(data_dir, artifact_dir, seed=options["seed"], epochs=options["epochs"])
        except (ValueError, OSError, RuntimeError, KeyError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"Saved checkpoints under {artifact_dir}"))
        self.stdout.write(f"Held-out synthetic metrics: {metrics}")
