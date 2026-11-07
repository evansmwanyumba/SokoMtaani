import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserRole(models.TextChoices):
    # Legacy marketplace role values are retained for existing database rows;
    # new authorization uses AdminRole and profile capabilities instead.
    BUYER = "buyer", "Buyer"
    SELLER = "seller", "Seller"
    ADMINISTRATOR = "administrator", "Administrator"
    MODERATOR = "moderator", "Moderator"
    SUPPORT_ADMINISTRATOR = "support_administrator", "Support administrator"
    ANALYTICS_VIEWER = "analytics_viewer", "Analytics viewer"


class AdminRole(models.TextChoices):
    NONE = "", "No administrative role"
    MODERATOR = "moderator", "Moderator"
    SUPPORT_ADMIN = "support_admin", "Support administrator"
    SUPER_ADMIN = "super_admin", "Super administrator"


class AccountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    TEMPORARILY_SUSPENDED = "temporarily_suspended", "Temporarily suspended"
    PERMANENTLY_BANNED = "permanently_banned", "Permanently banned"
    DEACTIVATED = "deactivated", "Deactivated"


class AccountMode(models.TextChoices):
    BUYER = "buyer", "Buyer"
    SELLER = "seller", "Seller"
    GENERAL = "general", "Buyer and seller"


class UserManager(BaseUserManager):
    use_in_migrations = True

    @staticmethod
    def normalize_address(email):
        if not email:
            raise ValueError("An email address is required.")
        return email.strip().casefold()

    def _create_user(self, email, password, **extra_fields):
        email = self.normalize_address(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", UserRole.BUYER)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", UserRole.ADMINISTRATOR)
        extra_fields.setdefault("admin_role", AdminRole.SUPER_ADMIN)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_email_verified", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.BUYER,
        db_index=True,
    )
    admin_role = models.CharField(
        max_length=24,
        choices=AdminRole.choices,
        default=AdminRole.NONE,
        db_index=True,
    )
    account_mode = models.CharField(
        max_length=12,
        choices=AccountMode.choices,
        default=AccountMode.GENERAL,
        db_index=True,
    )
    account_status = models.CharField(
        max_length=32,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
        db_index=True,
    )
    suspension_expires_at = models.DateTimeField(null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    is_admin_approved = models.BooleanField(default=True)
    is_demo_account = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-date_joined"]

    def save(self, *args, **kwargs):
        self.email = UserManager.normalize_address(self.email)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
