import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    "check-daily-price-drops": {
        "task": "tracker.tasks.check_daily_price_drops",
        "schedule": crontab(hour=8, minute=0),  # Run every day at 8 AM
    },
    "check-weekly-price-drops": {
        "task": "tracker.tasks.check_weekly_price_drops",
        "schedule": crontab(
            day_of_week=0, hour=9, minute=0
        ),  # Run every Sunday at 9 AM
    },
    "update-all-products": {
        "task": "tracker.tasks.update_all_products",
        "schedule": crontab(hour="*/6", minute=0),  # Run every 6 hours
    },
}
