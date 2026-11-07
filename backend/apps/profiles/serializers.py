from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import SellerProfile, UserProfile
from .services import normalize_kenyan_phone


class UserProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(source="user.last_name", required=False, allow_blank=True, max_length=150)

    class Meta:
        model = UserProfile
        fields = (
            "first_name",
            "last_name",
            "county",
            "town",
            "neighbourhood",
            "bio",
            "avatar",
            "phone_number",
            "phone_verified_at",
        )
        read_only_fields = ("phone_number", "phone_verified_at")

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if validated_data:
            instance.save()
        if user_data:
            for field, value in user_data.items():
                setattr(instance.user, field, value)
            instance.user.save(update_fields=[*user_data, "updated_at"])
        return instance


class SellerProfileSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(required=False)
    telegram_username = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[RegexValidator(r"^[A-Za-z0-9_]{5,32}$", "Enter a valid Telegram username.")],
    )

    class Meta:
        model = SellerProfile
        fields = (
            "display_name",
            "bio",
            "county",
            "town",
            "neighbourhood",
            "phone_number",
            "phone_verified_at",
            "allow_phone",
            "allow_whatsapp",
            "allow_sms",
            "allow_email",
            "allow_telegram",
            "telegram_username",
            "county",
            "town",
            "neighbourhood",
            "is_active",
            "created_at",
        )
        read_only_fields = ("phone_number", "phone_verified_at", "is_active", "created_at")


class PublicSellerSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(read_only=True)
    contacts = serializers.SerializerMethodField()

    class Meta:
        model = SellerProfile
        fields = ("id", "user_id", "display_name", "bio", "is_active", "created_at", "contacts")
        read_only_fields = fields

    def get_contacts(self, obj):
        phone_available = any((obj.allow_phone, obj.allow_whatsapp, obj.allow_sms))
        return {
            "phone": obj.phone_number if phone_available else "",
            "allow_phone": obj.allow_phone,
            "allow_whatsapp": obj.allow_whatsapp,
            "allow_sms": obj.allow_sms,
            "email": obj.user.email if obj.allow_email else "",
            "allow_email": obj.allow_email,
            "telegram": obj.telegram_username if obj.allow_telegram else "",
            "allow_telegram": obj.allow_telegram,
        }


class PhoneVerificationRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=32)

    def validate_phone_number(self, value):
        return normalize_kenyan_phone(value)


class PhoneVerificationConfirmSerializer(PhoneVerificationRequestSerializer):
    code = serializers.RegexField(r"^\d{6}$", max_length=6)


class SellerActivationSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    bio = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=32, required=False)

    def validate_phone_number(self, value):
        return normalize_kenyan_phone(value)
