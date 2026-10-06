# core/management/commands/update_item_end_date.py

from django.core.management.base import BaseCommand
from core.models import CoreEbayitem
from finde.find_relistedItemId import check_item_availability

class Command(BaseCommand):
    help = 'Updates the itemEndDate field of all items in the database'

    def handle(self, *args, **options):
        # Get all items from the database
        all_items = CoreEbayitem.objects.all()

        # Iterate through each item and update itemEndDate
        for item in all_items:
            try:
                # Fetch item availability to get itemEndDate
                item_availability = check_item_availability(item.item_id)
                item_end_date = item_availability.get('itemEndDate', 'Unknown')

                # Update itemEndDate field
                item.itemEndDate = item_end_date
                item.save()

                self.stdout.write(self.style.SUCCESS(f"Updated itemEndDate for item {item.item_id}"))
            except Exception as e:
                # Handle exceptions gracefully
                self.stderr.write(self.style.ERROR(f"Failed to update itemEndDate for item {item.item_id}: {str(e)}"))
