from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import AccountMode, AdminRole, User


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    admin_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "admin_role",
            "account_mode",
            "account_status",
            "is_email_verified",
            "is_admin_approved",
            "date_joined",
        )
        read_only_fields = fields

    def get_role(self, obj):
        if obj.admin_role == AdminRole.SUPER_ADMIN or obj.is_superuser:
            return "administrator"
        if obj.admin_role == AdminRole.MODERATOR:
            return "moderator"
        if obj.admin_role == AdminRole.SUPPORT_ADMIN:
            return "support_administrator"
        if hasattr(obj, "seller_profile") and obj.seller_profile.is_active:
            return "seller"
        return "buyer"

    def get_admin_role(self, obj):
        if obj.is_superuser:
            return AdminRole.SUPER_ADMIN
        return obj.admin_role


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class CsrfTokenSerializer(serializers.Serializer):
    csrfToken = serializers.CharField()


class MfaRequiredSerializer(serializers.Serializer):
    mfa_required = serializers.BooleanField()
    enrollment_required = serializers.BooleanField()
    provisioning_uri = serializers.CharField(required=False)


class MfaCodeSerializer(serializers.Serializer):
    code = serializers.RegexField(regex=r"^\d{6}$", max_length=6)


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    account_mode = serializers.ChoiceField(choices=AccountMode.choices, default=AccountMode.GENERAL)

    class Meta:
        model = User
        fields = ("email", "password", "first_name", "last_name", "account_mode")

    def validate_email(self, value):
        normalized = User.objects.normalize_address(value)
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return normalized

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, is_admin_approved=True, **validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField(trim_whitespace=False)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)
