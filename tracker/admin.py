from django.contrib import admin
from .models import Product, UserPreference


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "user",
        "current_price",
        "lowest_price",
        "store",
        "is_in_stock",
        "last_checked",
    )
    list_filter = ("store", "is_in_stock", "created_at")
    search_fields = ("title", "user__email", "description")
    readonly_fields = ("lowest_price", "highest_price", "last_checked", "created_at")
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("title", "url", "user", "store", "image_url", "description")},
        ),
        (
            "Price Information",
            {
                "fields": (
                    "current_price",
                    "lowest_price",
                    "highest_price",
                    "price_history",
                    "alert_threshold",
                )
            },
        ),
        ("Status", {"fields": ("is_in_stock", "last_checked", "created_at")}),
    )


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "email_notifications",
        "notification_frequency",
        "target_price_drop",
    )
    list_filter = ("email_notifications", "notification_frequency")
    search_fields = ("user__email",)
