from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="notification_preferences",
        on_delete=models.CASCADE,
    )
    email = models.BooleanField(default=True)
    messages = models.BooleanField(default=True)
    price_changes = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification preferences for {self.user_id}"


class Notification(models.Model):
    class Kind(models.TextChoices):
        MESSAGE = "message", "Message"
        REVIEW = "review", "Review"
        FAVORITE = "favorite", "Favourite"
        AVAILABILITY = "availability", "Availability"
        SYSTEM = "system", "System"
        ACCOUNT_APPROVAL = "account_approval", "Account approval"
        REPORT = "report", "Report"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="notifications",
        on_delete=models.CASCADE,
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)
    title = models.CharField(max_length=160)
    message = models.CharField(max_length=500, blank=True)
    target_id = models.CharField(max_length=80, blank=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at", "created_at"])]

    def __str__(self):
        return f"{self.kind} notification for {self.user_id}"
