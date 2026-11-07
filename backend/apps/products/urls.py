from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProductCommentListCreateView, ProductViewSet

router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")

urlpatterns = [
    path(
        "products/<uuid:product_id>/comments/",
        ProductCommentListCreateView.as_view(),
        name="product-comments",
    ),
    path("", include(router.urls)),
]
