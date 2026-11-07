from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AdminRole
from apps.community.models import AuditLog, Report
from apps.messaging.models import Conversation, Message
from apps.profiles.models import SellerProfile


User = get_user_model()


class AdminApiPrivacyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="moderator@example.com",
            password="Secure-test-Password1",
            is_email_verified=True,
            is_staff=True,
            admin_role=AdminRole.MODERATOR,
        )
        self.admin.is_verified = lambda: True
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            password="Secure-test-Password1",
            is_email_verified=True,
        )
        self.seller = User.objects.create_user(
            email="seller@example.com",
            password="Secure-test-Password1",
            is_email_verified=True,
        )
        SellerProfile.objects.create(
            user=self.seller,
            display_name="Seller",
            phone_number="+254712345678",
            phone_verified_at=timezone.now(),
        )
        conversation = Conversation.objects.create(buyer=self.buyer, seller=self.seller)
        self.message = Message.objects.create(
            conversation=conversation,
            sender=self.buyer,
            content="Private reported message.",
        )
        self.report = Report.objects.create(
            reporter=self.seller,
            target_type=Report.TargetType.MESSAGE,
            target_id=self.message.pk,
            reason="harassment",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_only_assigned_moderator_can_access_reported_message_and_access_is_audited(self):
        evidence_url = reverse("admin-message-evidence", kwargs={"report_id": self.report.pk})
        self.assertEqual(self.client.get(evidence_url).status_code, 404)

        self.report.status = Report.Status.ASSIGNED
        self.report.assigned_to = self.admin
        self.report.save()
        response = self.client.get(evidence_url)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["message"]["content"], "Private reported message.")
        self.assertEqual(AuditLog.objects.filter(action="admin.message_evidence.accessed").count(), 1)

    def test_member_without_admin_role_cannot_access_admin_api(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.get(reverse("admin-resource", kwargs={"resource": "reports"}))
        self.assertEqual(response.status_code, 403)

    def test_moderator_can_assign_report_to_self_and_audit_action(self):
        response = self.client.post(
            reverse("admin-action", kwargs={"resource": "reports", "object_id": str(self.report.pk)}),
            {"action": "review"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.ASSIGNED)
        self.assertEqual(self.report.assigned_to, self.admin)
        self.assertTrue(AuditLog.objects.filter(actor=self.admin, action="admin.review").exists())
