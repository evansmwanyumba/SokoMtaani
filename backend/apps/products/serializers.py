from django.core.validators import FileExtensionValidator
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.accounts.models import User
from apps.categories.models import Category

from .models import (
    Comment,
    MAX_PRODUCT_IMAGES,
    Product,
    ProductCondition,
    ProductImage,
    validate_image_size,
)


class SellerSummarySerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    contacts = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "display_name", "contacts")

    @extend_schema_field(serializers.CharField())
    def get_display_name(self, obj):
        if self.context.get("seller_name_override"):
            return self.context["seller_name_override"]
        return " ".join(part for part in (obj.first_name, obj.last_name) if part) or obj.email.split("@")[0]

    def get_contacts(self, obj):
        profile = getattr(obj, "seller_profile", None)
        if profile is None or not profile.is_active:
            return {}
        phone_available = any((profile.allow_phone, profile.allow_whatsapp, profile.allow_sms))
        return {
            "phone": profile.phone_number if phone_available else "",
            "allow_phone": profile.allow_phone,
            "allow_whatsapp": profile.allow_whatsapp,
            "allow_sms": profile.allow_sms,
            "email": obj.email if profile.allow_email else "",
            "allow_email": profile.allow_email,
            "telegram": profile.telegram_username if profile.allow_telegram else "",
            "allow_telegram": profile.allow_telegram,
        }

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image", "alt_text", "sort_order")
        read_only_fields = fields


@extend_schema_field(ProductImageSerializer(many=True))
class ProductImagesField(serializers.Field):
    default_error_messages = {
        "too_many": f"A listing can have at most {MAX_PRODUCT_IMAGES} images.",
        "invalid": "Upload valid JPEG, PNG or WebP image files.",
    }

    def get_value(self, dictionary):
        if hasattr(dictionary, "getlist"):
            values = dictionary.getlist(self.field_name)
            return values if values else serializers.empty
        return super().get_value(dictionary)

    def to_internal_value(self, data):
        values = data if isinstance(data, (list, tuple)) else [data]
        if len(values) > MAX_PRODUCT_IMAGES:
            self.fail("too_many")
        image_field = serializers.ImageField(
            validators=[
                FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"]),
                validate_image_size,
            ]
        )
        return [image_field.run_validation(value) for value in values]

    def to_representation(self, value):
        images = value.all() if hasattr(value, "all") else value
        return ProductImageSerializer(images, many=True, context=self.context).data


class ProductConditionField(serializers.ChoiceField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            labels = {label.casefold(): value for value, label in self.choices.items()}
            data = labels.get(data.casefold(), data)
        return super().to_internal_value(data)


class ProductSerializer(serializers.ModelSerializer):
    seller = serializers.SerializerMethodField()
    category = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Category.objects.filter(is_active=True),
    )
    images = ProductImagesField(source="product_images", required=False)
    condition = ProductConditionField(choices=ProductCondition.choices)
    primary_image = serializers.SerializerMethodField()
    seller_rating = serializers.SerializerMethodField()
    seller_review_count = serializers.SerializerMethodField()
    contact_preferences = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    contact_email = serializers.SerializerMethodField()
    telegram_username = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "seller",
            "category",
            "name",
            "description",
            "price",
            "old_price",
            "negotiable",
            "condition",
            "county",
            "town",
            "neighbourhood",
            "status",
            "admin_created",
            "seller_name_override",
            "view_count",
            "published_at",
            "created_at",
            "updated_at",
            "images",
            "primary_image",
            "seller_rating",
            "seller_review_count",
            "contact_preferences",
            "phone",
            "contact_email",
            "telegram_username",
        )
        read_only_fields = (
            "id",
            "seller",
            "status",
            "admin_created",
            "seller_name_override",
            "view_count",
            "published_at",
            "created_at",
            "updated_at",
            "primary_image",
            "seller_rating",
            "seller_review_count",
            "contact_preferences",
            "phone",
            "contact_email",
            "telegram_username",
        )

    def validate(self, attrs):
        incoming_images = attrs.get("product_images", [])
        current_count = self.instance.product_images.count() if self.instance else 0
        if current_count + len(incoming_images) > MAX_PRODUCT_IMAGES:
            raise serializers.ValidationError(
                {"images": f"A listing can have at most {MAX_PRODUCT_IMAGES} images."}
            )
        return attrs

    def create(self, validated_data):
        images = validated_data.pop("product_images", [])
        product = Product.objects.create(**validated_data)
        self._save_images(product, images)
        return product

    def update(self, instance, validated_data):
        images = validated_data.pop("product_images", [])
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        self._save_images(instance, images)
        return instance

    @staticmethod
    def _save_images(product, images):
        for index, image in enumerate(images, start=product.product_images.count()):
            ProductImage.objects.create(product=product, image=image, sort_order=index)

    def get_seller(self, obj):
        context = dict(self.context)
        if obj.seller_name_override:
            context["seller_name_override"] = obj.seller_name_override
        return SellerSummarySerializer(obj.seller, context=context).data

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_primary_image(self, obj):
        image = obj.product_images.first()
        if image is None:
            return None
        request = self.context.get("request")
        url = image.image.url
        return request.build_absolute_uri(url) if request else url

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_seller_rating(self, obj):
        return getattr(obj, "seller_rating_value", None)

    @extend_schema_field(serializers.IntegerField())
    def get_seller_review_count(self, obj):
        return getattr(obj, "seller_review_count_value", 0)

    def get_contact_preferences(self, obj):
        return getattr(obj.seller, "seller_profile", None) and SellerSummarySerializer(
            obj.seller, context=self.context
        ).data["contacts"] or {}

    def get_phone(self, obj):
        return self.get_contact_preferences(obj).get("phone", "")

    def get_contact_email(self, obj):
        return self.get_contact_preferences(obj).get("email", "")

    def get_telegram_username(self, obj):
        return self.get_contact_preferences(obj).get("telegram", "")

class CommentSerializer(serializers.ModelSerializer):
    author = SellerSummarySerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ("id", "author", "content", "is_visible", "created_at")
        read_only_fields = ("id", "author", "is_visible", "created_at")
