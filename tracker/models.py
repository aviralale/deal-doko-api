from django.db import models
from accounts.models import User


class Product(models.Model):
    url = models.URLField()
    title = models.CharField(max_length=255)
    current_price = models.FloatField()
    lowest_price = models.FloatField()
    highest_price = models.FloatField()
    last_checked = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="products")
    image_url = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    price_history = models.JSONField(default=list)
    alert_threshold = models.IntegerField(null=True, blank=True)
    is_in_stock = models.BooleanField(default=True)
    store = models.CharField(max_length=50, default="daraz")  # Store identifier
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("url", "user")  # One user can track a URL only once

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            self.lowest_price = self.current_price
            self.highest_price = self.current_price
        else:
            if self.current_price < self.lowest_price:
                self.lowest_price = self.current_price
            if self.current_price > self.highest_price:
                self.highest_price = self.current_price

        super().save(*args, **kwargs)

        if not is_new:
            from datetime import datetime

            timestamp = datetime.now().isoformat()

            if not isinstance(self.price_history, list):
                self.price_history = []

            self.price_history.append({"date": timestamp, "price": self.current_price})

            if len(self.price_history) > 100:
                self.price_history = self.price_history[-100:]

            super().save(update_fields=["price_history"])

    def __str__(self):
        return f"{self.title} - {self.user.email}"


class UserPreference(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="preferences"
    )
    email_notifications = models.BooleanField(default=True)
    notification_frequency = models.CharField(
        max_length=20,
        choices=[("instant", "Instant"), ("daily", "Daily"), ("weekly", "Weekly")],
        default="instant",
    )
    target_price_drop = models.IntegerField(default=10)  # Default alert at 10% drop

    def __str__(self):
        return f"Preferences for {self.user.email}"
