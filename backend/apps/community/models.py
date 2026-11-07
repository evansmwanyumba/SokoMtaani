import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="favorites", on_delete=models.CASCADE)
    product = models.ForeignKey("products.Product", related_name="favorites", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="unique_user_favorite")]
        ordering = ["-created_at"]


class Block(models.Model):
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="blocked_members", on_delete=models.CASCADE)
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="blocked_by_members", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_blocked_member"),
            models.CheckConstraint(condition=~Q(blocker=models.F("blocked")), name="cannot_block_self"),
        ]
        ordering = ["-created_at"]


class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="seller_reviews_written", on_delete=models.CASCADE)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="seller_reviews_received", on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    content = models.CharField(max_length=1000)
    is_visible = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["reviewer", "seller"], name="one_review_per_member_seller"),
            models.CheckConstraint(condition=Q(rating__gte=1) & Q(rating__lte=5), name="review_rating_1_to_5"),
            models.CheckConstraint(condition=~Q(reviewer=models.F("seller")), name="cannot_review_self"),
        ]


class HelpfulVote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="helpful_votes", on_delete=models.CASCADE)
    comment = models.ForeignKey("products.Comment", related_name="helpful_votes", null=True, blank=True, on_delete=models.CASCADE)
    review = models.ForeignKey(Review, related_name="helpful_votes", null=True, blank=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(comment__isnull=False, review__isnull=True) | Q(comment__isnull=True, review__isnull=False)),
                name="helpful_vote_has_one_target",
            ),
            models.UniqueConstraint(fields=["user", "comment"], condition=Q(comment__isnull=False), name="unique_helpful_comment_vote"),
            models.UniqueConstraint(fields=["user", "review"], condition=Q(review__isnull=False), name="unique_helpful_review_vote"),
        ]


class Report(models.Model):
    class TargetType(models.TextChoices):
        PRODUCT = "product", "Product"
        COMMENT = "comment", "Product comment"
        REVIEW = "review", "Seller review"
        USER = "user", "Member"
        MESSAGE = "message", "Private message"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="reports_submitted", on_delete=models.PROTECT)
    target_type = models.CharField(max_length=16, choices=TargetType.choices, db_index=True)
    target_id = models.UUIDField(db_index=True)
    reason = models.CharField(max_length=40)
    explanation = models.CharField(max_length=1000, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="assigned_reports", null=True, blank=True, on_delete=models.PROTECT
    )
    resolution = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "target_type", "created_at"])]


class Suspension(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="suspensions", on_delete=models.PROTECT)
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="issued_suspensions",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    report = models.ForeignKey(Report, related_name="suspensions", null=True, blank=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=1000)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    permanent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="audit_actions", on_delete=models.PROTECT)
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=80)
    reason = models.CharField(max_length=1000, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Audit records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit records cannot be deleted.")


class PlatformSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    contact_email = models.EmailField(default="hello@sokomtaani.co.ke")
    contact_phone = models.CharField(max_length=32, blank=True)
    community_hours = models.CharField(max_length=160, blank=True, default="Monday–Friday, 9am–5pm EAT")
    about_title = models.CharField(max_length=180, default="Good things happen close to home.")
    about_intro = models.CharField(max_length=1000, blank=True)
    team_title = models.CharField(max_length=180, default="Our community")
    team_information = models.TextField(max_length=5000, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings


class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="cart_items", on_delete=models.CASCADE)
    product = models.ForeignKey("products.Product", related_name="cart_items", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_user_cart_product"),
        ]


class CategorySuggestion(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="category_suggestions",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, max_length=1000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "name"],
                condition=Q(status="pending"),
                name="unique_pending_category_suggestion",
            ),
        ]


class Announcement(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="announcements", on_delete=models.PROTECT)
    title = models.CharField(max_length=180)
    body = models.TextField(max_length=5000)
    is_published = models.BooleanField(default=True, db_index=True)
    published_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at"]


class SupportConversation(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="support_conversations",
        on_delete=models.CASCADE,
    )
    subject = models.CharField(max_length=180)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class SupportMessage(models.Model):
    conversation = models.ForeignKey(
        SupportConversation,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="support_messages",
        on_delete=models.PROTECT,
    )
    body = models.CharField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]


def audit(actor, action, target, reason="", metadata=None):
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target._meta.label,
        target_id=str(target.pk),
        reason=reason,
        metadata=metadata or {},
    )
