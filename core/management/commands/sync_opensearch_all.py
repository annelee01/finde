# core/management/commands/sync_opensearch_all.py
# Syncs ALL docker opensearch indexed items if any manual mysql data field changes are made
# HOW TO: Run command in terminal (cd / ebay): 'python manage.py sync_opensearch_all' 

from django.core.management.base import BaseCommand
from core.models import CoreEbayitem
from core.documents import CoreEbayitemDocument

class Command(BaseCommand):
    help = "Sync MySQL data with OpenSearch"

    def handle(self, *args, **kwargs):
        # Fetch all instances from MySQL
        items = CoreEbayitem.objects.all()

        # Update OpenSearch for each instance
        for item in items:
            try:
                CoreEbayitemDocument.create_or_update(item)  # Call the create_or_update method
                self.stdout.write(self.style.SUCCESS(f"Synced CoreEbayitem {item.id} to OpenSearch"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error syncing CoreEbayitem {item.id}: {e}"))