# core/management/commands/sync_opensearch_one_item.py
# Syncs SINGULAR docker opensearch indexed item if any manual mysql data field changes are made 
# (go to 'sync_openserch_all.py' command if you want to sync ALL database items with docker indexed items)
# HOW TO: Run command in terminal (cd / ebay): python manage.py sync_opensearch_one_item "v1|ITEMID|0" *Include the quotes around the item_id*

from django.core.management.base import BaseCommand
from core.documents import CoreEbayitemDocument

class Command(BaseCommand):
    help = 'Sync a single CoreEbayitem entry to OpenSearch by item_id'

    def add_arguments(self, parser):
        parser.add_argument('item_id', type=str, help='The item_id of the CoreEbayitem to sync')

    def handle(self, *args, **kwargs):
        item_id = kwargs['item_id']

        # Sync the specific item to OpenSearch
        CoreEbayitemDocument.sync_item_by_id(item_id)
        self.stdout.write(self.style.SUCCESS(f"Synced CoreEbayitem with ID {item_id}"))