from django.contrib import admin
from apps.accounts.admin import secure_admin_site

from .models import Comment, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "seller", "category", "price", "county", "status", "published_at")
    list_filter = ("status", "condition", "county", "category")
    search_fields = ("name", "description", "seller__email", "town", "neighbourhood")
    readonly_fields = ("id", "view_count", "created_at", "updated_at")
    inlines = [ProductImageInline]


class CommentAdmin(admin.ModelAdmin):
    list_display = ("product", "author", "is_visible", "created_at")
    list_filter = ("is_visible", "created_at")
    search_fields = ("content", "product__name", "author__email")
    readonly_fields = ("id", "created_at", "updated_at")


secure_admin_site.register(Product, ProductAdmin)
secure_admin_site.register(Comment, CommentAdmin)
