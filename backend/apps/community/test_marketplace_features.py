from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.categories.models import Category
from apps.community.models import CartItem, CategorySuggestion, Report, SupportConversation, Suspension
from apps.notifications.models import Notification
from apps.products.models import Product, ProductStatus


User = get_user_model()


class MarketplaceFeatureTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(
            email="member@example.test",
            password="SecurePass!234",
            is_admin_approved=True,
        )
        self.admin = User.objects.create_superuser(
            email="admin@example.test",
            password="SecurePass!234",
        )
        self.category = Category.objects.create(name="Furniture", slug="furniture")
        self.product = Product.objects.create(
            seller=self.member,
            category=self.category,
            name="Table",
            description="Wooden table",
            price="1000.00",
            condition="gently_used",
            county="Nairobi",
            town="Nairobi",
        )
        self.client = APIClient()

    def test_cart_is_member_scoped_and_supports_create_list_and_remove(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            reverse("cart"),
            {"product_id": str(self.product.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(CartItem.objects.filter(user=self.member).count(), 1)
        self.assertEqual(self.client.get(reverse("cart")).data[0]["product"]["id"], str(self.product.pk))

        other_client = APIClient()
        other_client.force_authenticate(self.admin)
        self.assertEqual(other_client.get(reverse("cart")).data, [])
        self.assertEqual(
            self.client.delete(reverse("cart-delete", kwargs={"product_id": self.product.pk})).status_code,
            204,
        )
        self.assertFalse(CartItem.objects.exists())

    def test_support_conversation_is_owner_scoped_and_admin_can_reply(self):
        self.client.force_authenticate(self.member)
        created = self.client.post(
            reverse("support-conversations"),
            {"subject": "Listing help", "message": "I need help with my listing."},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        conversation_id = created.data["id"]
        conversation = SupportConversation.objects.get(pk=conversation_id)
        self.assertEqual(conversation.messages.count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.admin, title="New customer support message").exists())

        self.client.force_authenticate(self.admin)
        reply = self.client.post(
            reverse("support-messages", kwargs={"conversation_id": conversation_id}),
            {"body": "We can help with that."},
            format="json",
        )
        self.assertEqual(reply.status_code, 201, reply.data)
        self.assertEqual(conversation.messages.count(), 2)

        another_member = User.objects.create_user(
            email="other@example.test",
            password="SecurePass!234",
            is_admin_approved=True,
        )
        self.client.force_authenticate(another_member)
        denied = self.client.get(reverse("support-messages", kwargs={"conversation_id": conversation_id}))
        self.assertEqual(denied.status_code, 403)

    def test_super_admin_can_create_published_announcement(self):
        self.client.force_authenticate(self.admin)
        created = self.client.post(
            reverse("admin-resource", kwargs={"resource": "announcements"}),
            {"title": "Community update", "body": "A verified update."},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)

        public = APIClient().get(reverse("announcements"))
        rows = public.data["results"] if isinstance(public.data, dict) else public.data
        self.assertEqual(rows[0]["title"], "Community update")

    def test_member_can_request_category_and_admin_approval_publishes_it(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            reverse("category-suggestions"),
            {"name": "Musical instruments", "description": "Instruments and accessories"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        suggestion = CategorySuggestion.objects.get(pk=response.data["id"])
        self.client.force_authenticate(self.admin)
        reviewed = self.client.post(
            reverse("admin-action", kwargs={
                "resource": "category-suggestions",
                "object_id": str(suggestion.pk),
            }),
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.data)
        self.assertTrue(Category.objects.filter(name="Musical instruments", is_active=True).exists())
        self.assertTrue(
            Notification.objects.filter(
                user=self.member,
                title="Your category request was approved",
            ).exists()
        )

    def test_account_report_suspends_target_and_notifies_superuser(self):
        reported = User.objects.create_user(
            email="reported@example.test",
            password="SecurePass!234",
            is_admin_approved=True,
        )
        listing = Product.objects.create(
            seller=reported,
            category=self.category,
            name="Reported listing",
            description="Listing owned by reported account",
            price="500.00",
            condition="gently_used",
            county="Nairobi",
            town="Nairobi",
        )
        self.client.force_authenticate(self.member)
        response = self.client.post(
            reverse("report-create"),
            {
                "target_type": Report.TargetType.USER,
                "target_id": str(reported.pk),
                "reason": "suspicious_account",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        reported.refresh_from_db()
        listing.refresh_from_db()
        self.assertEqual(reported.account_status, "temporarily_suspended")
        self.assertIsNone(reported.suspension_expires_at)
        self.assertEqual(listing.status, ProductStatus.PAUSED)
        self.assertTrue(Suspension.objects.filter(user=reported, moderator__isnull=True).exists())
        self.assertTrue(
            Notification.objects.filter(
                user=self.admin,
                title="A reported account was suspended",
            ).exists()
        )
        login = APIClient().post(
            reverse("login"),
            {"email": reported.email, "password": "SecurePass!234"},
            format="json",
        )
        self.assertEqual(login.status_code, 403)
        self.assertEqual(login.data["code"], "account_suspended")

    def test_account_report_does_not_suspend_administrators(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(
            reverse("report-create"),
            {
                "target_type": Report.TargetType.USER,
                "target_id": str(self.admin.pk),
                "reason": "other",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.account_status, "active")
        self.assertFalse(Suspension.objects.filter(user=self.admin).exists())
        self.assertTrue(
            Notification.objects.filter(
                user=self.admin,
                title="A community report needs review",
            ).exists()
        )

    def test_admin_owned_listing_is_active_and_displays_team_name(self):
        self.client.force_authenticate(self.admin)
        created = self.client.post(
            reverse("admin-resource", kwargs={"resource": "products"}),
            {
                "category": self.category.name,
                "name": "Team listing",
                "description": "A marketplace team listing.",
                "price": "2500.00",
                "condition": "new",
                "county": "Nairobi",
                "town": "Nairobi",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        product = Product.objects.get(pk=created.data["id"])
        self.assertTrue(product.admin_created)
        self.assertEqual(product.status, "active")
        self.assertEqual(created.data["seller"]["display_name"], "SokoMtaani Team")

    def test_admin_analytics_uses_real_listing_data_and_marks_orders_unavailable(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            reverse("admin-resource", kwargs={"resource": "analytics"}) + "?period=7d"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["orders_available"])
        self.assertFalse(response.data["revenue_available"])
        self.assertEqual(len(response.data["trend_labels"]), 7)
        self.assertEqual(len(response.data["user_growth"]), 7)
        self.assertEqual(response.data["category_distribution"][0], {
            "category__name": "Furniture",
            "count": 1,
        })
        self.assertEqual(response.data["county_distribution"][0], {
            "county": "Nairobi",
            "count": 1,
        })

    def test_moderator_has_moderation_metrics_but_not_platform_analytics(self):
        User.objects.create(
            email="moderation-report@example.test",
            password="!",
            is_admin_approved=True,
        )
        reporter = User.objects.create_user(
            email="reporter@example.test",
            password="SecurePass!234",
            is_admin_approved=True,
        )
        Report.objects.create(
            reporter=reporter,
            target_type=Report.TargetType.USER,
            target_id=User.objects.get(email="moderation-report@example.test").pk,
            reason="other",
        )
        moderator = User.objects.create_user(
            email="moderator@example.test",
            password="SecurePass!234",
            is_staff=True,
            admin_role="moderator",
            is_admin_approved=True,
        )
        self.client.force_authenticate(moderator)
        moderation = self.client.get(
            reverse("admin-resource", kwargs={"resource": "moderation-analytics"})
        )
        self.assertEqual(moderation.status_code, 200, moderation.data)
        self.assertEqual(moderation.data["pending_reports"], 1)
        platform = self.client.get(reverse("admin-resource", kwargs={"resource": "analytics"}))
        self.assertEqual(platform.status_code, 403)
