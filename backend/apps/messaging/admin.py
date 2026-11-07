from django.contrib import admin

from apps.accounts.admin import secure_admin_site

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    can_delete = False
    readonly_fields = ("sender", "content", "attachment", "created_at", "read_at")

    def has_view_permission(self, request, obj=None):
        return False


class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "buyer", "seller", "product", "updated_at")
    search_fields = ("buyer__email", "seller__email")
    readonly_fields = ("id", "buyer", "seller", "product", "created_at", "updated_at")
    inlines = [MessageInline]

    def has_view_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "created_at", "read_at")
    readonly_fields = ("id", "conversation", "sender", "content", "attachment", "created_at", "read_at")

    def has_view_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


secure_admin_site.register(Conversation, ConversationAdmin)
secure_admin_site.register(Message, MessageAdmin)
