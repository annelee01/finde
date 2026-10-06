from django_cron import CronJobBase, Schedule
from core.management.commands.move_out_of_stock_items import Command  # Import Command

# automates periodically moving OUT_OF_STOCK database items into a separate table called .core_ebayitem_out_of_stock. companion file is move_out_of_stock_items.py under core/management/commands

class MoveOutOfStockItemsCronJob(CronJobBase):
    RUN_EVERY_MINS = 720  # Run twice a day (24 hours)

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'core.move_out_of_stock_items_cron_job'  # Unique code for this cron job

    def do(self):
        command = Command()  # Instantiate the Command class
        command.handle()    # Call the handle method to execute the command