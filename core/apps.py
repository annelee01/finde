from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):   
        import core.signals
        # NOTE 'import core.signal's' doesn't need to be "accessed" (assigned to a variable). 
        # The act of importing the signals module is enough to register the signal handlers