from django.contrib import admin

from apps.accounts.admin import secure_admin_site

from .models import Category


@admin.register(Category, site=secure_admin_site)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "sort_order", "is_active")
    list_filter = ("is_active", "parent")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
