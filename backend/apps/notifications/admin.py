from django.contrib import admin

from apps.accounts.admin import secure_admin_site

from .models import Notification, NotificationPreference


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


secure_admin_site.register(Notification, ReadOnlyAdmin)
secure_admin_site.register(NotificationPreference, ReadOnlyAdmin)
