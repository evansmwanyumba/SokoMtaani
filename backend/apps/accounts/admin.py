from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import AccountCreationForm
from .models import User


class UserAdmin(DjangoUserAdmin):
    add_form = AccountCreationForm
    ordering = ("email",)
    list_display = (
        "email",
        "admin_role",
        "account_status",
        "is_email_verified",
        "is_active",
        "is_staff",
    )
    list_filter = ("admin_role", "account_status", "is_email_verified", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = (
        "last_login",
        "date_joined",
        "updated_at",
        "role",
        "admin_role",
        "account_status",
        "suspension_expires_at",
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Marketplace access", {"fields": ("role", "admin_role", "account_status", "suspension_expires_at", "is_email_verified", "is_active")}),
        (
            "Permissions",
            {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )


secure_admin_site = admin.AdminSite(name="admin")
secure_admin_site.register(User, UserAdmin)
