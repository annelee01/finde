from django.db import connection 
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

# automates periodically moving OUT_OF_STOCK database items into a separate table called .core_ebayitem_out_of_stock. companion file is core/cron.py

class Command(BaseCommand):
    help = 'Move OUT_OF_STOCK items to core_ebayitem_out_of_stock table and delete from core_ebayitem'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting the move_out_of_stock_items command...')
        # Calculate the date 14 days ago
        fourteen_days_ago = timezone.now() - timedelta(days=14)

        with connection.cursor() as cursor:
            cursor.execute("SET SQL_SAFE_UPDATES = 0;")

            # 1. Move OUT_OF_STOCK items from main table TO core_ebayitem_out_of_stock datatable OR move items that ended more than 14 days ago. 
            # This way, the manual relist logic can still relist the 'ended' items within that 14 day period, 
            # and give users the ability to "see" what happened items, while being in comliance with eBay's 30 data rentention policy.
            cursor.execute("""
                INSERT INTO core_ebayitem_out_of_stock
                SELECT *
                FROM core_ebayitem
                WHERE availability = 'OUT_OF_STOCK' OR itemEndDate < %s;
            """, [fourteen_days_ago])

            # 2. Delete out_of_stock items AND ended items from the main core_ebayitem table
            cursor.execute("""
                DELETE FROM core_ebayitem
                WHERE availability = 'OUT_OF_STOCK' OR itemEndDate < %s;
            """, [fourteen_days_ago])

            # 3. Now, delete records from core_ebayitem_out_of_stock table older than 14 days**
            cursor.execute("""
                DELETE FROM core_ebayitem_out_of_stock
                WHERE itemEndDate < %s;
            """, [fourteen_days_ago])

            cursor.execute("SET SQL_SAFE_UPDATES = 1;")
            
        self.stdout.write('Completed the move_out_of_stock_items command.')

            