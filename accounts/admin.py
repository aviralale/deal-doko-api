from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from .models import User
from django.utils.translation import gettext_lazy as _

admin.site.site_title = _("DealDoko Admin Site")
admin.site.site_header = _(
    "DealDoko Admin - Collecting deals like a traditional basket"
)


class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "username",
        "name",
        "is_admin",
        "is_active",
    )
    list_filter = ("is_admin", "is_active")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "name",
                    "username",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_admin",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Important dates", {"fields": ("date_joined",), "classes": ("collapse",)}),
    )
    readonly_fields = ("date_joined",)
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "name",
                    "username",
                    "password1",
                    "password2",
                    "is_admin",
                ),
            },
        ),
    )
    search_fields = (
        "email",
        "username",
        "name",
    )
    ordering = ("email",)
    filter_horizontal = ()


admin.site.register(User, UserAdmin)
admin.site.unregister(Group)
