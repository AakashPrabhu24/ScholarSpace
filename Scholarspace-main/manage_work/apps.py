from django.apps import AppConfig
import os


class ManageWorkConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "manage_work"

    def ready(self):
        # Import signals to register them
        from . import signals
        
        # Only start the reminder thread in the main process.
        # Django autoreloader imports everything twice — RUN_MAIN is only
        # set to "true" in the actual server process, not the reloader watcher.
        if os.environ.get("RUN_MAIN") == "true":
            from .reminders import start_reminder_thread
            start_reminder_thread()
