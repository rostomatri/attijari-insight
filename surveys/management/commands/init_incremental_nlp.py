# surveys/management/commands/init_incremental_nlp.py
from django.core.management.base import BaseCommand
from surveys.analytics.incremental_nlp import init_incremental_nlp

class Command(BaseCommand):
    help = "Initialise l'analyse NLP incrémentale (choisit K automatiquement + construit l'état)."

    def add_arguments(self, parser):
        parser.add_argument("--k_min", type=int, default=2)
        parser.add_argument("--k_max", type=int, default=12)
        parser.add_argument("--sample_size", type=int, default=2000)

    def handle(self, *args, **opts):
        out = init_incremental_nlp(
            k_min=opts["k_min"],
            k_max=opts["k_max"],
            sample_size=opts["sample_size"],
        )
        self.stdout.write(str(out))