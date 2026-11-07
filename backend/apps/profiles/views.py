from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.accounts.models import AccountStatus
from apps.community.models import Favorite
from apps.messaging.models import Conversation, Message
from apps.products.models import Product, ProductStatus, ProductView
from apps.products.serializers import ProductSerializer

from .models import SellerProfile, UserProfile
from .permissions import IsActiveAccount, IsActiveSeller
from .serializers import (
    PhoneVerificationConfirmSerializer,
    PhoneVerificationRequestSerializer,
    SellerActivationSerializer,
    SellerProfileSerializer,
    PublicSellerSerializer,
    UserProfileSerializer,
)
from .services import issue_phone_verification, verify_phone_code


class MyProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsActiveAccount]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class MySellerProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = SellerProfileSerializer
    permission_classes = [IsAuthenticated, IsActiveSeller]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return get_object_or_404(SellerProfile, user=self.request.user, is_active=True)


class MySellerProductsView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsActiveSeller]

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user).select_related(
            "seller", "seller__seller_profile", "category"
        ).prefetch_related("product_images").order_by("-updated_at")


class SellerAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsActiveSeller]

    @extend_schema(responses={
        200: {
            "type": "object",
            "properties": {
                "active_listings": {"type": "integer"},
                "views": {"type": "integer"},
                "unique_visitors": {"type": "integer"},
                "enquiries": {"type": "integer"},
                "favourites": {"type": "integer"},
                "top_product": {"type": "object", "nullable": True},
                "monthly_views": {"type": "array", "items": {"type": "integer"}},
                "monthly_labels": {"type": "array", "items": {"type": "string"}},
                "recent_activity": {"type": "array", "items": {"type": "object"}},
            },
        }
    })
    def get(self, request):
        products = Product.objects.filter(seller=request.user)
        now = timezone.now()
        start = now - timedelta(weeks=11)
        events = ProductView.objects.filter(product__seller=request.user, created_at__gte=start)
        week_totals = {
            entry["week"].date(): entry["count"]
            for entry in events.annotate(week=TruncWeek("created_at"))
            .values("week")
            .annotate(count=Count("id"))
        }
        first_week = timezone.localdate(now) - timedelta(days=timezone.localdate(now).weekday())
        labels = []
        monthly = []
        for offset in range(11, -1, -1):
            week = first_week - timedelta(weeks=offset)
            labels.append(week.strftime("%b %d"))
            monthly.append(week_totals.get(week, 0))

        top_listing = products.order_by("-view_count", "-published_at").first()
        recent_messages = Message.objects.filter(conversation__seller=request.user).order_by("-created_at")[:3]
        recent_favourites = Favorite.objects.filter(product__seller=request.user).order_by("-created_at")[:2]
        recent_activity = [
            {
                "icon": "bi-chat-dots",
                "title": "New message about a listing",
                "created_at": message.created_at,
            }
            for message in recent_messages
        ] + [
            {
                "icon": "bi-heart",
                "title": "A member saved a listing",
                "created_at": favorite.created_at,
            }
            for favorite in recent_favourites
        ]
        recent_activity.sort(key=lambda item: item["created_at"], reverse=True)

        return Response(
            {
                "active_listings": products.filter(status=ProductStatus.ACTIVE).count(),
                "views": products.aggregate(total=Sum("view_count"))["total"] or 0,
                "unique_visitors": events.exclude(viewer__isnull=True).values("viewer_id").distinct().count(),
                "enquiries": Conversation.objects.filter(seller=request.user).count(),
                "favourites": Favorite.objects.filter(product__seller=request.user).count(),
                "top_product": ProductSerializer(top_listing, context={"request": request}).data if top_listing else None,
                "monthly_views": monthly,
                "monthly_labels": labels,
                "recent_activity": recent_activity[:5],
            }
        )


class PublicSellerListView(generics.ListAPIView):
    serializer_class = PublicSellerSerializer
    permission_classes = [AllowAny]
    queryset = SellerProfile.objects.filter(
        is_active=True,
        user__is_active=True,
        user__is_admin_approved=True,
        user__account_status=AccountStatus.ACTIVE,
    ).order_by("display_name")

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(display_name__icontains=search)
        return queryset


class PublicSellerDetailView(generics.RetrieveAPIView):
    serializer_class = PublicSellerSerializer
    permission_classes = [AllowAny]
    lookup_field = "user_id"
    queryset = SellerProfile.objects.filter(
        is_active=True,
        user__is_active=True,
        user__is_admin_approved=True,
        user__account_status=AccountStatus.ACTIVE,
    )


class PhoneVerificationRequestView(APIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    @extend_schema(request=PhoneVerificationRequestSerializer, responses={202: {"type": "object"}})
    def post(self, request):
        serializer = PhoneVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        issue_phone_verification(
            request.user,
            serializer.validated_data["phone_number"],
        )
        return Response(
            {"detail": "If delivery succeeded, a verification code has been sent."},
            status=status.HTTP_202_ACCEPTED,
        )


class PhoneVerificationConfirmView(APIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    @extend_schema(request=PhoneVerificationConfirmSerializer, responses={200: {"type": "object"}})
    def post(self, request):
        serializer = PhoneVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = verify_phone_code(
            request.user,
            serializer.validated_data["phone_number"],
            serializer.validated_data["code"],
        )
        if phone is None:
            return Response(
                {"code": "The verification code is invalid or expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.phone_number = phone
        profile.phone_verified_at = timezone.now()
        profile.save(update_fields=["phone_number", "phone_verified_at", "updated_at"])
        return Response({"detail": "Phone number verified."})


class SellerActivationView(APIView):
    permission_classes = [IsAuthenticated, IsActiveAccount]

    @extend_schema(request=SellerActivationSerializer, responses=SellerProfileSerializer)
    @transaction.atomic
    def post(self, request):
        serializer = SellerActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = UserProfile.objects.filter(user=request.user).first()
        values = serializer.validated_data
        requested_phone = values.get("phone_number")
        if (
            profile is None
            or not profile.phone_verified_at
            or not profile.phone_number
            or (requested_phone and requested_phone != profile.phone_number)
        ):
            return Response(
                {"phone_number": "Verify this phone number before activating seller capability."},
                status=status.HTTP_403_FORBIDDEN,
            )
        seller, _ = SellerProfile.objects.update_or_create(
            user=request.user,
            defaults={
                "display_name": values.get("display_name")
                or " ".join(part for part in (request.user.first_name, request.user.last_name) if part)
                or request.user.email.split("@")[0],
                "bio": values.get("bio", ""),
                "county": profile.county,
                "town": profile.town,
                "neighbourhood": profile.neighbourhood,
                "phone_number": profile.phone_number,
                "phone_verified_at": profile.phone_verified_at,
                "is_active": True,
            },
        )
        return Response(SellerProfileSerializer(seller).data, status=status.HTTP_200_OK)
