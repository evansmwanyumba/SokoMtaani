from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Notification, NotificationPreference


User = get_user_model()


class NotificationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="member@example.com",
            password="Secure-test-Password1",
            is_email_verified=True,
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="Secure-test-Password1",
            is_email_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.notification = Notification.objects.create(
            user=self.user,
            kind=Notification.Kind.SYSTEM,
            title="Account update",
            message="Your account is ready.",
        )

    def test_member_only_reads_and_marks_own_notifications(self):
        response = self.client.get(reverse("notification-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["id"], self.notification.pk)

        mark = self.client.post(
            reverse("notification-read", kwargs={"notification_id": self.notification.pk})
        )
        self.assertEqual(mark.status_code, 204)
        self.notification.refresh_from_db()
        self.assertIsNotNone(self.notification.read_at)

        denied = self.client.post(
            reverse("notification-read", kwargs={"notification_id": 999999})
        )
        self.assertEqual(denied.status_code, 404)

    def test_member_can_update_only_notification_preferences(self):
        response = self.client.patch(
            reverse("notification-preferences"),
            {"messages": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        preferences = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(preferences.messages)
        self.assertTrue(preferences.email)
