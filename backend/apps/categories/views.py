from django.db.models import Count, Prefetch, Q
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from apps.products.models import Product, ProductStatus

from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        active_children = Category.objects.filter(is_active=True).annotate(
            active_product_count=Count(
                "products",
                filter=Q(
                    products__status=ProductStatus.ACTIVE,
                    products__seller__is_active=True,
                    products__seller__is_admin_approved=True,
                    products__seller__account_status="active",
                ),
            )
        )
        return (
            Category.objects.filter(is_active=True, parent__isnull=True)
            .annotate(
                active_product_count=Count(
                    "products",
                    filter=Q(
                        products__status=ProductStatus.ACTIVE,
                        products__seller__is_active=True,
                        products__seller__is_admin_approved=True,
                        products__seller__account_status="active",
                    ),
                )
            )
            .prefetch_related(Prefetch("children", queryset=active_children.order_by("sort_order", "name"), to_attr="active_children"))
            .order_by("sort_order", "name")
        )
