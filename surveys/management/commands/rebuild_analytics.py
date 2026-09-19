from django.core.management.base import BaseCommand
from surveys.analytics.builder import rebuild_analytics_snapshot

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        out = rebuild_analytics_snapshot()
        self.stdout.write(str(out))