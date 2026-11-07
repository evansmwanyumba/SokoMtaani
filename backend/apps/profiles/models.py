import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="profile",
        on_delete=models.CASCADE,
    )
    county = models.CharField(max_length=80, blank=True)
    town = models.CharField(max_length=100, blank=True)
    neighbourhood = models.CharField(max_length=120, blank=True)
    bio = models.CharField(max_length=500, blank=True)
    phone_number = models.CharField(max_length=16, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to="profiles/avatars/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user}"


class SellerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="seller_profile",
        on_delete=models.CASCADE,
    )
    display_name = models.CharField(max_length=120)
    bio = models.CharField(max_length=1000, blank=True)
    county = models.CharField(max_length=80, blank=True)
    town = models.CharField(max_length=100, blank=True)
    neighbourhood = models.CharField(max_length=120, blank=True)
    phone_number = models.CharField(max_length=16, unique=True)
    phone_verified_at = models.DateTimeField()
    allow_phone = models.BooleanField(default=False)
    allow_whatsapp = models.BooleanField(default=False)
    allow_sms = models.BooleanField(default=False)
    allow_email = models.BooleanField(default=False)
    allow_telegram = models.BooleanField(default=False)
    telegram_username = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name


class PhoneVerification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="phone_verifications",
        on_delete=models.CASCADE,
    )
    phone_number = models.CharField(max_length=16, db_index=True)
    code_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "phone_number", "expires_at"])]

    @property
    def is_valid(self):
        return (
            self.consumed_at is None
            and self.expires_at > timezone.now()
            and self.attempts < 5
        )

    def __str__(self):
        return f"Phone verification for {self.user_id}"
