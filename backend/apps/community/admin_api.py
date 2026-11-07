from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncMonth
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer

from apps.accounts.models import AccountStatus, AdminRole
from apps.categories.models import Category
from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification
from apps.notifications.services import create_notification
from apps.products.models import Product, ProductCondition, ProductStatus
from apps.products.serializers import ProductSerializer
from apps.profiles.models import SellerProfile

from .models import (
    Announcement,
    AuditLog,
    CategorySuggestion,
    PlatformSettings,
    Report,
    Review,
    SupportConversation,
    Suspension,
    audit,
)
from .permissions import IsMarketplaceAdmin
from .serializers import PlatformSettingsSerializer


User = get_user_model()


class AdminActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=(
            "review",
            "assign",
            "resolve",
            "dismiss",
            "pause",
            "activate",
            "sold",
            "suspend",
            "ban",
            "reactivate",
            "hide",
            "restore",
            "disable",
            "enable",
            "set-admin-role",
            "approve",
            "delete",
            "deactivate",
        )
    )
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    expires_in_days = serializers.IntegerField(min_value=1, max_value=365, required=False)
    admin_role = serializers.ChoiceField(choices=AdminRole.choices, required=False)


class AdminUserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    admin_role = serializers.ChoiceField(choices=AdminRole.choices, required=False, allow_null=True)

    def validate_email(self, value):
        value = User.objects.normalize_address(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password

        validate_password(value)
        return value

    def create(self, validated_data):
        admin_role = validated_data.pop("admin_role", None)
        user = User.objects.create_user(**validated_data, is_admin_approved=True)
        if admin_role:
            user.admin_role = admin_role
            user.is_staff = True
            user.save(update_fields=("admin_role", "is_staff"))
        return user


class AdminProductCreateSerializer(serializers.Serializer):
    seller_id = serializers.UUIDField(required=False)
    category = serializers.CharField(max_length=120)
    name = serializers.CharField(max_length=140)
    description = serializers.CharField(max_length=5000)
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    condition = serializers.ChoiceField(choices=ProductCondition.choices)
    county = serializers.CharField(max_length=80)
    town = serializers.CharField(max_length=100)


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")

    def validate_email(self, value):
        value = User.objects.normalize_address(value)
        if User.objects.exclude(pk=self.instance.pk).filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value


class AdminConversationCreateSerializer(serializers.Serializer):
    buyer_id = serializers.UUIDField()
    seller_id = serializers.UUIDField()
    product_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        buyer = get_object_or_404(User, pk=attrs["buyer_id"], is_active=True, is_admin_approved=True)
        seller = get_object_or_404(User, pk=attrs["seller_id"], is_active=True, is_admin_approved=True)
        if buyer.pk == seller.pk:
            raise serializers.ValidationError({"seller_id": "Buyer and seller must be different accounts."})
        if not SellerProfile.objects.filter(user=seller, is_active=True).exists():
            raise serializers.ValidationError({"seller_id": "Select an active seller account."})
        product_id = attrs.pop("product_id", None)
        product = None
        if product_id:
            product = get_object_or_404(Product, pk=product_id, seller=seller)
        attrs.update({"buyer": buyer, "seller": seller, "product": product})
        return attrs


class AdminCategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("name", "description")

    def validate_name(self, value):
        slug = slugify(value)
        if not slug:
            raise serializers.ValidationError("Enter a category name containing letters or numbers.")
        if Category.objects.filter(slug=slug).exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value


class AdminAnnouncementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ("title", "body", "is_published")


class AdminAnnouncementUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ("title", "body", "is_published")


class AnnouncementAdminSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ("id", "title", "body", "is_published", "published_at", "author_name")

    def get_author_name(self, obj):
        return "SokoMtaani Team"


class AdminResourceView(APIView):
    permission_classes = [IsMarketplaceAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, resource):
        data = self.get_resource_data(resource, request=request)
        if isinstance(data, dict):
            return Response(data)
        paginator = PageNumberPagination()
        return Response(paginator.get_paginated_response(paginator.paginate_queryset(data, request, view=self)).data)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request, resource):
        self.require_super_admin(request)
        if resource == "users":
            serializer = AdminUserCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            audit(request.user, "admin.user.created", user)
            from apps.accounts.serializers import UserSerializer

            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        if resource == "products":
            fields = AdminProductCreateSerializer(data=request.data)
            fields.is_valid(raise_exception=True)
            seller_id = fields.validated_data.get("seller_id")
            seller = (
                get_object_or_404(
                    SellerProfile.objects.select_related("user"),
                    user_id=seller_id,
                    is_active=True,
                ).user
                if seller_id
                else request.user
            )
            listing_data = {key: value for key, value in request.data.items() if key != "seller_id"}
            listing = ProductSerializer(data=listing_data, context={"request": request})
            listing.is_valid(raise_exception=True)
            product = listing.save(
                seller=seller,
                admin_created=True,
                seller_name_override="SokoMtaani Team",
                status=ProductStatus.ACTIVE,
            )
            audit(request.user, "admin.product.created", product)
            return Response(ProductSerializer(product, context={"request": request}).data, status=status.HTTP_201_CREATED)
        if resource == "categories":
            serializer = AdminCategoryCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            category = serializer.save()
            audit(request.user, "admin.category.created", category)
            return Response(
                {"id": str(category.pk), "name": category.name, "status": "active"},
                status=status.HTTP_201_CREATED,
            )
        if resource == "announcements":
            serializer = AdminAnnouncementCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            announcement = serializer.save(author=request.user)
            audit(request.user, "admin.announcement.created", announcement)
            return Response(AnnouncementAdminSerializer(announcement).data, status=status.HTTP_201_CREATED)
        if resource == "conversations":
            serializer = AdminConversationCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data
            conversation = Conversation.objects.filter(
                buyer=values["buyer"],
                seller=values["seller"],
                product=values["product"],
            ).first()
            created = conversation is None
            if created:
                conversation = Conversation.objects.create(
                    buyer=values["buyer"],
                    seller=values["seller"],
                    product=values["product"],
                    admin_created=True,
                )
            if created:
                for member in (conversation.buyer, conversation.seller):
                    Notification.objects.create(
                        user=member,
                        kind=Notification.Kind.SYSTEM,
                        title="A conversation was opened for you",
                        message="SokoMtaani support opened this conversation. No message was sent on your behalf.",
                        target_id=str(conversation.pk),
                    )
            audit(request.user, "admin.conversation.created", conversation)
            return Response(
                {"id": str(conversation.pk), "admin_created": conversation.admin_created},
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        raise serializers.ValidationError({"resource": "Creation is not available for this resource."})

    @extend_schema(request=PlatformSettingsSerializer, responses=PlatformSettingsSerializer)
    def patch(self, request, resource):
        self.require_super_admin(request)
        if resource != "settings":
            raise serializers.ValidationError({"resource": "Only platform settings can be edited here."})
        settings_obj = PlatformSettings.get_solo()
        serializer = PlatformSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit(request.user, "admin.platform_settings.updated", settings_obj)
        return Response(serializer.data)


    @staticmethod
    def require_super_admin(request):
        if not (request.user.is_superuser or request.user.admin_role == AdminRole.SUPER_ADMIN):
            raise PermissionDenied("Only a super administrator can perform this operation.")

    def get_resource_data(self, resource, request=None):
        if resource == "users":
            return [
                {
                    "id": str(user.pk),
                    "email": user.email,
                    "name": " ".join(part for part in (user.first_name, user.last_name) if part),
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.admin_role or user.role,
                    "status": "pending_approval" if not user.is_admin_approved else user.account_status,
                    "is_admin_approved": user.is_admin_approved,
                    "is_demo_account": user.is_demo_account,
                    "is_email_verified": user.is_email_verified,
                    "created_at": user.date_joined,
                }
                for user in User.objects.only(
                    "id", "email", "first_name", "last_name", "role", "admin_role",
                    "account_status", "is_email_verified", "is_admin_approved", "date_joined",
                    "is_demo_account",
                )
            ]
        if resource == "sellers":
            return [
                {
                    "id": str(profile.user_id),
                    "display_name": profile.display_name,
                    "email": profile.user.email,
                    "status": "active" if profile.is_active else "suspended",
                    "created_at": profile.created_at,
                }
                for profile in SellerProfile.objects.select_related("user")
            ]
        if resource == "products":
            return [
                {
                    "id": str(product.pk),
                    "name": product.name,
                    "seller": product.seller.email,
                    "category": product.category.name,
                    "description": product.description,
                    "price": product.price,
                    "condition": product.condition,
                    "county": product.county,
                    "town": product.town,
                    "status": product.status,
                    "created_at": product.created_at,
                }
                for product in Product.objects.select_related("seller", "category")
            ]
        if resource == "categories":
            return [
                {
                    "id": str(category.pk),
                    "name": category.name,
                    "status": "active" if category.is_active else "disabled",
                    "created_at": category.created_at,
                }
                for category in Category.objects.all()
            ]
        if resource == "category-suggestions":
            return [
                {
                    "id": str(item.pk),
                    "name": item.name,
                    "description": item.description,
                    "requester": item.requester.email,
                    "status": item.status,
                    "created_at": item.created_at,
                }
                for item in CategorySuggestion.objects.select_related("requester")
            ]
        if resource == "announcements":
            return AnnouncementAdminSerializer(
                Announcement.objects.select_related("author"),
                many=True,
            ).data
        if resource == "reports":
            return [self.report_row(report) for report in Report.objects.select_related("reporter", "assigned_to")]
        if resource == "message-reports":
            return [
                self.report_row(report)
                for report in Report.objects.filter(target_type=Report.TargetType.MESSAGE).select_related(
                    "reporter", "assigned_to"
                )
            ]
        if resource == "reviews":
            return [
                {
                    "id": str(review.pk),
                    "seller": review.seller.email,
                    "reviewer": review.reviewer.email,
                    "rating": review.rating,
                    "content": review.content,
                    "status": "visible" if review.is_visible else "hidden",
                    "created_at": review.created_at,
                }
                for review in Review.objects.select_related("reviewer", "seller")
            ]
        if resource in {"security-activity", "audit-logs"}:
            return [
                {
                    "id": str(entry.pk),
                    "actor": entry.actor.email,
                    "name": entry.action,
                    "action": entry.action,
                    "target_type": entry.target_type,
                    "target_id": entry.target_id,
                    "status": entry.reason,
                    "created_at": entry.created_at,
                }
                for entry in AuditLog.objects.select_related("actor")
            ]
        if resource == "analytics":
            period = request.query_params.get("period", "30d") if request else "30d"
            period_days = {"7d": 7, "30d": 30, "90d": 90, "12m": 365}.get(period, 30)
            now = timezone.now()
            start = now - timedelta(days=period_days)
            if period == "12m":
                current_month = now.year * 12 + now.month - 1
                labels = [
                    datetime(
                        (current_month - offset) // 12,
                        (current_month - offset) % 12 + 1,
                        1,
                    ).strftime("%b %Y")
                    for offset in range(11, -1, -1)
                ]
                start = now - timedelta(days=366)
            else:
                labels = [(now.date() - timedelta(days=offset)).strftime("%b %d") for offset in range(period_days - 1, -1, -1)]
            user_counts = self.counts_by_time(User.objects.filter(date_joined__gte=start), "date_joined", period == "12m")
            listing_counts = self.counts_by_time(
                Product.objects.filter(published_at__gte=start),
                "published_at",
                period == "12m",
            )
            category_distribution = list(
                Product.objects.filter(status=ProductStatus.ACTIVE)
                .values("category__name")
                .annotate(count=Count("id"))
                .order_by("-count", "category__name")[:6]
            )
            county_distribution = list(
                Product.objects.filter(status=ProductStatus.ACTIVE)
                .values("county")
                .annotate(count=Count("id"))
                .order_by("-count", "county")[:10]
            )
            activity = [
                {
                    "action": entry.action,
                    "actor": entry.actor.email,
                    "target_type": entry.target_type,
                    "created_at": entry.created_at,
                }
                for entry in AuditLog.objects.filter(created_at__gte=now - timedelta(days=30))
                .select_related("actor")
                .order_by("-created_at")[:8]
            ]
            return {
                "users": User.objects.count(),
                "active_users": User.objects.filter(is_active=True, account_status=AccountStatus.ACTIVE).count(),
                "active_sellers": SellerProfile.objects.filter(is_active=True).count(),
                "active_products": Product.objects.filter(status=ProductStatus.ACTIVE).count(),
                "open_reports": Report.objects.filter(status__in=(Report.Status.OPEN, Report.Status.ASSIGNED)).count(),
                "pending_approvals": User.objects.filter(is_admin_approved=False).count(),
                "reviews": Review.objects.filter(is_visible=True).count(),
                "announcements": Announcement.objects.filter(is_published=True).count(),
                "support_conversations": SupportConversation.objects.filter(status="open").count(),
                "orders_available": False,
                "revenue_available": False,
                "period": period,
                "trend_labels": labels,
                "user_growth": [user_counts.get(label, 0) for label in labels],
                "listing_growth": [listing_counts.get(label, 0) for label in labels],
                "category_distribution": category_distribution,
                "county_distribution": county_distribution,
                "recent_activity": activity,
            }
        if resource == "moderation-analytics":
            pending_reports = Report.objects.filter(
                status__in=(Report.Status.OPEN, Report.Status.ASSIGNED)
            )
            account_reports = pending_reports.filter(target_type=Report.TargetType.USER)
            return {
                "pending_reports": pending_reports.count(),
                "reported_accounts": account_reports.values("target_id").distinct().count(),
                "reported_listings": pending_reports.filter(target_type=Report.TargetType.PRODUCT).count(),
                "reported_reviews": pending_reports.filter(target_type=Report.TargetType.REVIEW).count(),
                "resolved_reports": Report.objects.filter(
                    status__in=(Report.Status.RESOLVED, Report.Status.DISMISSED)
                ).count(),
                "recent_suspensions": Suspension.objects.filter(
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).count(),
            }
        if resource == "settings":
            from django.conf import settings

            return {
                "debug": settings.DEBUG,
                "email_configured": bool(settings.EMAIL_HOST),
                "sms_configured": bool(settings.SMS_PROVIDER_URL and settings.SMS_PROVIDER_API_KEY),
                "database_engine": settings.DATABASES["default"]["ENGINE"],
                "site_content": PlatformSettingsSerializer(PlatformSettings.get_solo()).data,
            }
        if resource == "pending-approvals":
            return [
                {
                    "id": str(user.pk),
                    "email": user.email,
                    "name": " ".join(part for part in (user.first_name, user.last_name) if part),
                    "status": "pending_approval",
                    "created_at": user.date_joined,
                }
                for user in User.objects.filter(is_admin_approved=False).order_by("date_joined")
            ]
        if resource == "conversations":
            return [
                {
                    "id": str(conversation.pk),
                    "buyer": conversation.buyer.email,
                    "seller": conversation.seller.email,
                    "product": conversation.product.name if conversation.product else "",
                    "messages": conversation.message_count,
                    "admin_created": conversation.admin_created,
                    "created_at": conversation.created_at,
                }
                for conversation in Conversation.objects.select_related("buyer", "seller", "product").annotate(
                    message_count=Count("messages")
                )
            ]
        raise serializers.ValidationError({"resource": "Unknown administration resource."})

    @staticmethod
    def counts_by_time(queryset, field, monthly):
        truncation = TruncMonth if monthly else TruncDate
        rows = (
            queryset.annotate(bucket=truncation(field))
            .values("bucket")
            .annotate(count=Count("pk"))
            .order_by("bucket")
        )
        return {
            (row["bucket"].strftime("%b %Y") if monthly else row["bucket"].strftime("%b %d")): row["count"]
            for row in rows
        }

    @staticmethod
    def report_row(report):
        return {
            "id": str(report.pk),
            "reporter": report.reporter.email,
            "target_type": report.target_type,
            "target_id": str(report.target_id),
            "reason": report.reason,
            "status": report.status,
            "assigned_to": report.assigned_to.email if report.assigned_to else None,
            "created_at": report.created_at,
        }


class AdminObjectUpdateView(APIView):
    permission_classes = [IsMarketplaceAdmin]

    @extend_schema(
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        operation_id="admin_update_object",
    )
    def patch(self, request, resource, object_id):
        AdminResourceView.require_super_admin(request)
        if resource == "users":
            user = get_object_or_404(User, pk=object_id)
            serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            audit(request.user, "admin.user.updated", user)
            from apps.accounts.serializers import UserSerializer

            return Response(UserSerializer(user).data)
        if resource == "products":
            product = get_object_or_404(Product, pk=object_id)
            serializer = ProductSerializer(product, data=request.data, partial=True, context={"request": request})
            serializer.is_valid(raise_exception=True)
            product = serializer.save()
            audit(request.user, "admin.product.updated", product)
            return Response(ProductSerializer(product, context={"request": request}).data)
        if resource == "announcements":
            announcement = get_object_or_404(Announcement, pk=object_id)
            serializer = AdminAnnouncementUpdateSerializer(announcement, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            audit(request.user, "admin.announcement.updated", announcement)
            return Response(AnnouncementAdminSerializer(announcement).data)
        raise serializers.ValidationError({"resource": "This resource cannot be edited."})


class AdminActionView(APIView):
    permission_classes = [IsMarketplaceAdmin]

    @extend_schema(
        request=AdminActionSerializer,
        responses=inline_serializer(
            name="AdminActionResponse",
            fields={"detail": serializers.CharField()},
        ),
    )
    def post(self, request, resource, object_id):
        serializer = AdminActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_name = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")
        with transaction.atomic():
            target = self.get_target(resource, object_id)
            self.perform_action(request, resource, target, action_name, serializer.validated_data, reason)
            audit(
                request.user,
                f"admin.{action_name}",
                target,
                reason=reason,
                metadata={"resource": resource},
            )
        return Response({"detail": "Action recorded."}, status=status.HTTP_200_OK)

    @staticmethod
    def get_target(resource, object_id):
        models = {
            "users": User,
            "sellers": User,
            "products": Product,
            "categories": Category,
            "category-suggestions": CategorySuggestion,
            "reports": Report,
            "message-reports": Report,
            "reviews": Review,
        }
        model = models.get(resource)
        if model is None:
            raise serializers.ValidationError({"resource": "Actions are not available for this resource."})
        queryset = model.objects.all()
        if resource == "message-reports":
            queryset = queryset.filter(target_type=Report.TargetType.MESSAGE)
        return get_object_or_404(queryset, pk=object_id)

    def perform_action(self, request, resource, target, action_name, values, reason):
        if resource in {"reports", "message-reports"}:
            self.handle_report(request, target, action_name, reason)
        elif resource == "products":
            if action_name == "delete":
                AdminResourceView.require_super_admin(request)
            self.handle_product(target, action_name)
        elif resource == "users":
            self.handle_user(request, target, action_name, values, reason)
        elif resource == "sellers":
            self.handle_seller(target, action_name)
        elif resource == "reviews":
            self.handle_review(target, action_name)
        elif resource == "categories":
            self.handle_category(target, action_name)
        elif resource == "category-suggestions":
            self.handle_category_suggestion(target, action_name)
        else:
            raise serializers.ValidationError({"resource": "This resource cannot be modified."})

    @staticmethod
    def handle_report(request, report, action_name, reason):
        if action_name in {"review", "assign"}:
            if report.status in (Report.Status.RESOLVED, Report.Status.DISMISSED):
                raise serializers.ValidationError({"action": "Resolved reports cannot be assigned."})
            report.status = Report.Status.ASSIGNED
            report.assigned_to = request.user
        elif action_name == "resolve":
            report.status = Report.Status.RESOLVED
            report.resolved_at = timezone.now()
            report.resolution = reason
        elif action_name == "dismiss":
            report.status = Report.Status.DISMISSED
            report.resolved_at = timezone.now()
            report.resolution = reason
        elif action_name == "suspend":
            user = AdminActionView.reported_user(report)
            AdminActionView.handle_user(
                request,
                user,
                "suspend",
                {},
                reason or f"Suspended after report {report.pk}",
                report=report,
            )
            report.status = Report.Status.ASSIGNED
            report.assigned_to = request.user
        else:
            raise serializers.ValidationError({"action": "This action is not valid for reports."})
        report.save(update_fields=["status", "assigned_to", "resolved_at", "resolution", "updated_at"])

    @staticmethod
    def handle_product(product, action_name):
        if action_name == "delete":
            try:
                product.delete()
            except ProtectedError as error:
                raise serializers.ValidationError(
                    {"action": "This listing is referenced by retained records and cannot be deleted."}
                ) from error
            return
        status_by_action = {
            "review": ProductStatus.PAUSED,
            "pause": ProductStatus.PAUSED,
            "activate": ProductStatus.ACTIVE,
            "sold": ProductStatus.SOLD,
        }
        if action_name not in status_by_action:
            raise serializers.ValidationError({"action": "This action is not valid for listings."})
        product.status = status_by_action[action_name]
        product.save(update_fields=["status", "updated_at"])

    @staticmethod
    def handle_user(request, user, action_name, values, reason, report=None):
        if action_name == "approve":
            AdminResourceView.require_super_admin(request)
            if user.is_admin_approved:
                raise serializers.ValidationError({"action": "This account is already approved."})
            user.is_admin_approved = True
            user.save(update_fields=["is_admin_approved", "updated_at"])
            Notification.objects.create(
                user=user,
                kind=Notification.Kind.SYSTEM,
                title="Your account was approved",
                message="You can now sign in to SokoMtaani.",
                target_id=str(user.pk),
            )
            return
        if action_name == "deactivate":
            AdminResourceView.require_super_admin(request)
            if user.pk == request.user.pk or user.is_superuser:
                raise serializers.ValidationError({"action": "Superuser accounts cannot be deactivated here."})
            user.account_status = AccountStatus.DEACTIVATED
            user.is_active = False
            user.save(update_fields=["account_status", "is_active", "updated_at"])
            return
        if action_name == "delete":
            AdminResourceView.require_super_admin(request)
            if user.pk == request.user.pk or user.is_superuser:
                raise serializers.ValidationError({"action": "Superuser accounts cannot be deleted here."})
            try:
                if user.is_demo_account:
                    from django.db.models import Q

                    demo_conversations = Conversation.objects.filter(admin_created=True).filter(
                        Q(buyer=user) | Q(seller=user)
                    )
                    Message.objects.filter(conversation__in=demo_conversations).delete()
                    demo_conversations.delete()
                user.delete()
            except ProtectedError as error:
                raise serializers.ValidationError(
                    {"action": "This account has retained conversations, reports, or moderation records. Deactivate it instead."}
                ) from error
            return
        if action_name == "set-admin-role":
            if request.user.admin_role != AdminRole.SUPER_ADMIN:
                raise PermissionDenied("Only a super administrator can assign administrative roles.")
            if not values.get("admin_role"):
                raise serializers.ValidationError({"admin_role": "Choose an administrative role."})
            if user.pk == request.user.pk and values["admin_role"] != AdminRole.SUPER_ADMIN:
                raise serializers.ValidationError({"admin_role": "You cannot remove your own super administrator role."})
            user.admin_role = values["admin_role"]
            user.is_staff = user.admin_role != AdminRole.NONE
            user.save(update_fields=["admin_role", "is_staff", "updated_at"])
            return
        if action_name == "suspend":
            expires_at = None
            expires_at = timezone.now() + timedelta(days=values.get("expires_in_days", 7))
            user.account_status = AccountStatus.TEMPORARILY_SUSPENDED
            user.suspension_expires_at = expires_at
            user.save(update_fields=["account_status", "suspension_expires_at", "updated_at"])
            Product.objects.filter(seller=user, status=ProductStatus.ACTIVE).update(status=ProductStatus.PAUSED)
            Suspension.objects.create(
                user=user,
                moderator=request.user,
                reason=reason or "Administrative suspension",
                starts_at=timezone.now(),
                expires_at=expires_at,
                permanent=False,
                report=report,
            )
            return
        if action_name == "ban":
            user.account_status = AccountStatus.PERMANENTLY_BANNED
            user.suspension_expires_at = None
            user.save(update_fields=["account_status", "suspension_expires_at", "updated_at"])
            Product.objects.filter(seller=user, status=ProductStatus.ACTIVE).update(status=ProductStatus.PAUSED)
            Suspension.objects.create(
                user=user,
                moderator=request.user,
                reason=reason or "Administrative ban",
                starts_at=timezone.now(),
                permanent=True,
                report=report,
            )
            return
        if action_name == "reactivate":
            user.account_status = AccountStatus.ACTIVE
            user.suspension_expires_at = None
            user.save(update_fields=["account_status", "suspension_expires_at", "updated_at"])
            return
        raise serializers.ValidationError({"action": "This action is not valid for accounts."})

    @staticmethod
    def reported_user(report):
        if report.target_type == Report.TargetType.USER:
            target = User.objects.filter(pk=report.target_id).first()
        elif report.target_type == Report.TargetType.MESSAGE:
            message = Message.objects.select_related("conversation").filter(pk=report.target_id).first()
            if message:
                if message.sender_id == report.reporter_id:
                    target_id = (
                        message.conversation.seller_id
                        if message.conversation.buyer_id == report.reporter_id
                        else message.conversation.buyer_id
                    )
                else:
                    target_id = message.sender_id
                target = User.objects.filter(pk=target_id).first()
            else:
                target = None
        elif report.target_type == Report.TargetType.PRODUCT:
            target = User.objects.filter(products__pk=report.target_id).first()
        elif report.target_type == Report.TargetType.REVIEW:
            reported_user_id = Review.objects.filter(pk=report.target_id).values_list("reviewer_id", flat=True).first()
            target = User.objects.filter(pk=reported_user_id).first() if reported_user_id else None
        elif report.target_type == Report.TargetType.COMMENT:
            from apps.products.models import Comment

            target = User.objects.filter(product_comments__pk=report.target_id).first()
        else:
            target = None
        if target is None:
            raise serializers.ValidationError({"action": "No account could be resolved for this report."})
        return target

    @staticmethod
    def handle_seller(user, action_name):
        try:
            profile = user.seller_profile
        except SellerProfile.DoesNotExist as error:
            raise serializers.ValidationError({"seller": "The member does not have seller capability."}) from error
        if action_name == "suspend":
            profile.is_active = False
        elif action_name == "activate":
            profile.is_active = True
        else:
            raise serializers.ValidationError({"action": "This action is not valid for sellers."})
        profile.save(update_fields=["is_active", "updated_at"])

    @staticmethod
    def handle_review(review, action_name):
        if action_name == "hide":
            review.is_visible = False
        elif action_name == "restore":
            review.is_visible = True
        else:
            raise serializers.ValidationError({"action": "This action is not valid for reviews."})
        review.save(update_fields=["is_visible", "updated_at"])

    @staticmethod
    def handle_category(category, action_name):
        if action_name == "disable":
            category.is_active = False
        elif action_name == "enable":
            category.is_active = True
        else:
            raise serializers.ValidationError({"action": "This action is not valid for categories."})
        category.save(update_fields=["is_active", "updated_at"])

    @staticmethod
    def handle_category_suggestion(suggestion, action_name):
        if suggestion.status != CategorySuggestion.Status.PENDING:
            raise serializers.ValidationError({"action": "This category request has already been reviewed."})
        if action_name == "approve":
            slug = slugify(suggestion.name)
            if not slug:
                raise serializers.ValidationError({"action": "The suggested category name is invalid."})
            category, created = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": suggestion.name, "description": suggestion.description},
            )
            if not created and not category.is_active:
                category.is_active = True
                category.save(update_fields=("is_active", "updated_at"))
            suggestion.status = CategorySuggestion.Status.APPROVED
            create_notification(
                suggestion.requester,
                Notification.Kind.SYSTEM,
                "Your category request was approved",
                f"{suggestion.name} is now available for listings.",
                category.pk,
            )
        elif action_name == "dismiss":
            suggestion.status = CategorySuggestion.Status.REJECTED
            create_notification(
                suggestion.requester,
                Notification.Kind.SYSTEM,
                "Your category request was not approved",
                f"The request for {suggestion.name} was not approved.",
                suggestion.pk,
            )
        else:
            raise serializers.ValidationError({"action": "This action is not valid for category requests."})
        suggestion.save(update_fields=("status", "updated_at"))


class AdminMessageEvidenceView(APIView):
    permission_classes = [IsMarketplaceAdmin]

    @extend_schema(
        responses=inline_serializer(
            name="AdminMessageEvidenceResponse",
            fields={
                "report_id": serializers.UUIDField(),
                "message": inline_serializer(
                    name="AdminReportedMessage",
                    fields={
                        "id": serializers.UUIDField(),
                        "sender": serializers.EmailField(),
                        "content": serializers.CharField(),
                        "attachment": serializers.URLField(allow_null=True),
                        "created_at": serializers.DateTimeField(),
                    },
                ),
            },
        )
    )
    def get(self, request, report_id):
        report = get_object_or_404(
            Report.objects.filter(
                target_type=Report.TargetType.MESSAGE,
                status=Report.Status.ASSIGNED,
                assigned_to=request.user,
            ),
            pk=report_id,
        )
        message = get_object_or_404(Message.objects.select_related("sender"), pk=report.target_id)
        audit(
            request.user,
            "admin.message_evidence.accessed",
            report,
            metadata={"message_id": str(message.pk)},
        )
        return Response(
            {
                "report_id": str(report.pk),
                "message": {
                    "id": str(message.pk),
                    "sender": message.sender.email,
                    "content": message.content,
                    "attachment": request.build_absolute_uri(message.attachment.url) if message.attachment else None,
                    "created_at": message.created_at,
                },
            }
        )
