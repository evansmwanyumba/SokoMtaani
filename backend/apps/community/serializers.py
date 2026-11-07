from rest_framework import serializers
from django.utils import timezone
from django.db import transaction

from apps.accounts.models import AccountStatus, User
from apps.categories.models import Category
from apps.products.models import Comment, Product, ProductStatus
from apps.products.serializers import ProductSerializer
from apps.notifications.models import Notification
from apps.notifications.services import create_notification

from .models import (
    Announcement,
    CartItem,
    CategorySuggestion,
    Favorite,
    PlatformSettings,
    Report,
    Review,
    Suspension,
    SupportConversation,
    SupportMessage,
    audit,
)


class BlockedMemberSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField()


class HelpfulVoteResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class FavoriteSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(status="active"),
        write_only=True,
    )
    product_id = serializers.UUIDField(source="product.id", read_only=True)
    product_detail = serializers.SerializerMethodField()

    class Meta:
        model = Favorite
        fields = ("id", "product", "product_id", "product_detail", "created_at")
        read_only_fields = ("id", "created_at")

    def create(self, validated_data):
        item, created = Favorite.objects.get_or_create(user=self.context["request"].user, **validated_data)
        self.did_create = created
        if created:
            create_notification(
                item.product.seller,
                Notification.Kind.FAVORITE,
                "A member saved your listing",
                "One of your active listings was added to a member's favourites.",
                item.product_id,
            )
        return item

    def get_product_detail(self, obj):
        from apps.products.serializers import ProductSerializer

        return ProductSerializer(obj.product, context=self.context).data


class ReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ("id", "reviewer", "seller", "rating", "content", "is_visible", "created_at", "updated_at")
        read_only_fields = ("id", "reviewer", "seller", "is_visible", "created_at", "updated_at")

    def get_reviewer(self, obj):
        return " ".join(part for part in (obj.reviewer.first_name, obj.reviewer.last_name) if part) or obj.reviewer.email.split("@")[0]


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ("id", "target_type", "target_id", "reason", "explanation", "status", "created_at")
        read_only_fields = ("id", "status", "created_at")

    def validate(self, attrs):
        target_type = attrs["target_type"]
        target_id = attrs["target_id"]
        models = {
            "product": Product,
            "comment": Comment,
            "review": Review,
            "user": User,
        }
        target_model = models.get(target_type)
        if target_model and not target_model.objects.filter(pk=target_id).exists():
            raise serializers.ValidationError({"target_id": "The reported content does not exist."})
        if target_type == Report.TargetType.MESSAGE:
            from apps.messaging.models import Message

            if not Message.objects.filter(pk=target_id).exists():
                raise serializers.ValidationError({"target_id": "The reported message does not exist."})
            message = Message.objects.select_related("conversation").get(pk=target_id)
            if self.context["request"].user.pk not in (message.conversation.buyer_id, message.conversation.seller_id):
                raise serializers.ValidationError({"target_id": "You may only report a message you received or sent."})
        if target_type == Report.TargetType.USER and str(target_id) == str(self.context["request"].user.pk):
            raise serializers.ValidationError({"target_id": "You cannot report your own account."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        report = Report.objects.create(reporter=self.context["request"].user, **validated_data)
        if report.target_type == Report.TargetType.USER:
            target = User.objects.get(pk=report.target_id)
            if target.account_status == AccountStatus.ACTIVE and not (target.is_staff or target.is_superuser):
                target.account_status = AccountStatus.TEMPORARILY_SUSPENDED
                target.suspension_expires_at = None
                target.save(update_fields=("account_status", "suspension_expires_at", "updated_at"))
                Product.objects.filter(seller=target, status=ProductStatus.ACTIVE).update(status=ProductStatus.PAUSED)
                Suspension.objects.create(
                    user=target,
                    moderator=None,
                    report=report,
                    reason="Automatically suspended after a member account report; administrator review required.",
                    starts_at=timezone.now(),
                )
                profile = getattr(target, "seller_profile", None)
                if profile and profile.is_active:
                    profile.is_active = False
                    profile.save(update_fields=("is_active", "updated_at"))
                audit(self.context["request"].user, "report.account_auto_suspended", target, metadata={"report_id": str(report.pk)})
        audit(
            self.context["request"].user,
            "report.created",
            report,
            metadata={"target_type": report.target_type},
        )
        return report


class PlatformSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSettings
        fields = (
            "contact_email",
            "contact_phone",
            "community_hours",
            "about_title",
            "about_intro",
            "team_title",
            "team_information",
        )


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(status="active"),
        source="product",
        write_only=True,
    )

    class Meta:
        model = CartItem
        fields = ("id", "product", "product_id", "created_at")
        read_only_fields = ("id", "product", "created_at")


class CategorySuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategorySuggestion
        fields = ("id", "name", "description", "status", "created_at")
        read_only_fields = ("id", "status", "created_at")

    def validate_name(self, value):
        value = value.strip()
        if Category.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("A matching category already exists.")
        if CategorySuggestion.objects.filter(
            requester=self.context["request"].user,
            name__iexact=value,
            status=CategorySuggestion.Status.PENDING,
        ).exists():
            raise serializers.ValidationError("You already requested this category.")
        return value

    def create(self, validated_data):
        return CategorySuggestion.objects.create(requester=self.context["request"].user, **validated_data)


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ("id", "title", "body", "is_published", "published_at", "author_name")
        read_only_fields = ("id", "published_at", "author_name")

    def get_author_name(self, obj):
        return "SokoMtaani Team" if obj.author.is_superuser or obj.author.admin_role == "super_admin" else obj.author.email


class SupportMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = SupportMessage
        fields = ("id", "body", "created_at", "sender_name", "is_admin")
        read_only_fields = fields

    def get_sender_name(self, obj):
        if obj.sender.is_superuser or obj.sender.admin_role == "super_admin":
            return "SokoMtaani Team"
        return " ".join(part for part in (obj.sender.first_name, obj.sender.last_name) if part) or obj.sender.email

    def get_is_admin(self, obj):
        return obj.sender.is_staff


class SupportConversationSerializer(serializers.ModelSerializer):
    messages = SupportMessageSerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = SupportConversation
        fields = ("id", "subject", "status", "created_at", "updated_at", "user_email", "messages")
        read_only_fields = ("id", "status", "created_at", "updated_at", "user_email", "messages")


class SupportConversationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportConversation
        fields = ("subject",)
