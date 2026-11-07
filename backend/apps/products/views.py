from django.db.models import Avg, Count, F, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.profiles.permissions import IsApprovedActiveUser, IsSellerOwner

from .filters import ProductFilterBackend
from .models import Comment, Product, ProductStatus, ProductView
from .serializers import CommentSerializer, ProductSerializer


class ProductAvailabilitySerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=(ProductStatus.ACTIVE, ProductStatus.PAUSED, ProductStatus.SOLD)
    )


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsSellerOwner]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    filter_backends = [ProductFilterBackend]

    def get_queryset(self):
        queryset = Product.objects.select_related(
            "seller", "seller__seller_profile", "category"
        ).prefetch_related("product_images").annotate(
            seller_rating_value=Avg(
                "seller__seller_reviews_received__rating",
                filter=Q(seller__seller_reviews_received__is_visible=True),
            ),
            seller_review_count_value=Count(
                "seller__seller_reviews_received",
                filter=Q(seller__seller_reviews_received__is_visible=True),
                distinct=True,
            ),
        )
        queryset = queryset.filter(
            seller__is_active=True,
            seller__is_admin_approved=True,
            seller__account_status="active",
        )
        if self.action in {"retrieve", "update", "partial_update", "destroy", "availability"} and self.request.user.is_authenticated:
            return queryset.filter(
                Q(status=ProductStatus.ACTIVE) | Q(seller=self.request.user)
            ).distinct()
        return queryset.filter(status=ProductStatus.ACTIVE)

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        product = self.get_object()
        viewer = request.user if request.user.is_authenticated else None
        if product.seller_id != getattr(viewer, "pk", None):
            ProductView.objects.create(product=product, viewer=viewer)
            Product.objects.filter(pk=product.pk).update(view_count=F("view_count") + 1)
            response.data["view_count"] = product.view_count + 1
        return response

    @action(detail=True, methods=["post"], url_path="availability")
    def availability(self, request, pk=None):
        product = self.get_object()
        serializer = ProductAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product.status = serializer.validated_data["status"]
        product.save(update_fields=["status", "updated_at"])
        return Response(ProductSerializer(product, context=self.get_serializer_context()).data, status=status.HTTP_200_OK)


class ProductCommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    parser_classes = [JSONParser, FormParser]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsApprovedActiveUser()]
        return [AllowAny()]

    def get_product(self):
        return get_object_or_404(
            Product.objects.filter(status=ProductStatus.ACTIVE),
            pk=self.kwargs["product_id"],
        )

    def get_queryset(self):
        return (
            Comment.objects.filter(product=self.get_product(), is_visible=True)
            .select_related("author")
        )

    def perform_create(self, serializer):
        serializer.save(product=self.get_product(), author=self.request.user)
