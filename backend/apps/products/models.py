import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.categories.models import Category


MAX_PRODUCT_IMAGES = 6
MAX_IMAGE_SIZE = 5 * 1024 * 1024


def validate_image_size(image):
    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError("Each image must be no larger than 5 MB.")


class ProductCondition(models.TextChoices):
    NEW = "new", "New"
    LIKE_NEW = "like_new", "Like new"
    GENTLY_USED = "gently_used", "Gently used"


class ProductStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PAUSED = "paused", "Paused"
    SOLD = "sold", "Sold"
    DRAFT = "draft", "Draft"


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="products",
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        Category,
        related_name="products",
        on_delete=models.PROTECT,
    )
    name = models.CharField(max_length=140)
    description = models.TextField(max_length=5000)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    old_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    negotiable = models.BooleanField(default=False)
    condition = models.CharField(
        max_length=16,
        choices=ProductCondition.choices,
        db_index=True,
    )
    county = models.CharField(max_length=80, db_index=True)
    town = models.CharField(max_length=100)
    neighbourhood = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=12,
        choices=ProductStatus.choices,
        default=ProductStatus.ACTIVE,
        db_index=True,
    )
    admin_created = models.BooleanField(default=False)
    seller_name_override = models.CharField(max_length=120, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "county", "condition"]),
            models.Index(fields=["status", "price"]),
            models.Index(fields=["status", "published_at"]),
        ]

    def __str__(self):
        return self.name


def product_image_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"products/{instance.product_id}/{uuid.uuid4().hex}{extension}"


class ProductImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        related_name="product_images",
        on_delete=models.CASCADE,
    )
    image = models.ImageField(
        upload_to=product_image_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"]),
            validate_image_size,
        ],
    )
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "created_at"]

    def __str__(self):
        return f"Image for {self.product}"


class ProductView(models.Model):
    product = models.ForeignKey(Product, related_name="view_events", on_delete=models.CASCADE)
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="product_views",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["product", "created_at"])]


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        related_name="comments",
        on_delete=models.CASCADE,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="product_comments",
        on_delete=models.CASCADE,
    )
    content = models.CharField(max_length=1000)
    is_visible = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.product}"
