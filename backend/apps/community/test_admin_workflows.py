from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.categories.models import Category
from apps.community.models import Report
from apps.messaging.models import Conversation
from apps.notifications.models import Notification
from apps.products.models import Product, ProductStatus
from apps.profiles.models import SellerProfile


User = get_user_model()


class AdminWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="root@example.test",
            password="SecurePass!234",
        )
        self.buyer = User.objects.create_user(
            email="buyer@example.test",
            password="SecurePass!234",
            is_admin_approved=True,
        )
        self.seller = User.objects.create_user(
            email="seller@example.test",
            password="SecurePass!234",
            is_admin_approved=True,
        )
        SellerProfile.objects.create(
            user=self.seller,
            display_name="Neighbour Seller",
            phone_number="+254712345678",
            phone_verified_at=timezone.now(),
        )
        self.category = Category.objects.create(name="Furniture", slug="furniture")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def admin_resource(self, resource):
        return reverse("admin-resource", kwargs={"resource": resource})

    def admin_action(self, resource, object_id):
        return reverse("admin-action", kwargs={"resource": resource, "object_id": str(object_id)})

    def test_superuser_can_create_account_and_account_is_ready_for_login(self):
        response = self.client.post(
            self.admin_resource("users"),
            {"email": "created@example.test", "password": "SecurePass!234"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="created@example.test")
        self.assertTrue(user.is_admin_approved)
        self.assertFalse(user.is_email_verified)
        login = self.client.post(
            reverse("login"),
            {"email": user.email, "password": "SecurePass!234"},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)

    def test_existing_django_superuser_without_admin_role_can_access_admin_api(self):
        legacy_admin = User.objects.create_user(
            email="legacy-root@example.test",
            password="SecurePass!234",
            is_staff=True,
            is_superuser=True,
            is_admin_approved=True,
        )
        self.assertEqual(legacy_admin.admin_role, "")
        self.client.force_authenticate(legacy_admin)
        response = self.client.get(self.admin_resource("analytics"))
        self.assertEqual(response.status_code, 200, response.data)

    def test_existing_superuser_can_login_without_email_verification_or_otp(self):
        User.objects.create_user(
            email="existing-root@example.test",
            password="SecurePass!234",
            is_staff=True,
            is_superuser=True,
            is_admin_approved=True,
        )
        client = APIClient()
        response = client.post(
            reverse("login"),
            {"email": "existing-root@example.test", "password": "SecurePass!234"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["is_email_verified"])
        self.assertEqual(response.data["admin_role"], "super_admin")

    def test_created_superuser_login_returns_super_admin_dashboard_role(self):
        admin = User.objects.create_superuser(
            email="fresh-superuser@example.test",
            password="SecurePass!234",
        )
        client = APIClient()
        login = client.post(
            reverse("login"),
            {"email": admin.email, "password": "SecurePass!234"},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        self.assertEqual(login.data["role"], "administrator")
        self.assertEqual(login.data["admin_role"], "super_admin")
        analytics = client.get(self.admin_resource("analytics"))
        self.assertEqual(analytics.status_code, 200, analytics.data)

    def test_superuser_can_approve_registered_account(self):
        pending = User.objects.create_user(
            email="pending@example.test",
            password="SecurePass!234",
            is_admin_approved=False,
        )
        response = self.client.post(
            self.admin_action("users", pending.pk),
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        pending.refresh_from_db()
        self.assertTrue(pending.is_admin_approved)
        self.assertTrue(Notification.objects.filter(user=pending, title="Your account was approved").exists())

    def test_registration_is_ready_immediately_without_admin_notification(self):
        response = self.client.post(
            reverse("register"),
            {"email": "newmember@example.test", "password": "SecurePass!234", "account_mode": "seller"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        member = User.objects.get(email="newmember@example.test")
        self.assertTrue(member.is_admin_approved)
        self.assertEqual(member.account_mode, "seller")
        self.assertFalse(Notification.objects.filter(
            user=self.admin,
            kind=Notification.Kind.ACCOUNT_APPROVAL,
            target_id=str(member.pk),
        ).exists())

        logged_in = self.client.post(
            reverse("login"),
            {"email": member.email, "password": "SecurePass!234"},
            format="json",
        )
        self.assertEqual(logged_in.status_code, 200, logged_in.data)

    def test_only_superuser_can_create_account_or_update_public_settings(self):
        moderator = User.objects.create_user(
            email="moderator@example.test",
            password="SecurePass!234",
            is_staff=True,
            admin_role="moderator",
        )
        self.client.force_authenticate(moderator)
        response = self.client.post(
            self.admin_resource("users"),
            {"email": "not-allowed@example.test", "password": "SecurePass!234"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_user_delete_action_deactivates_account_when_records_are_protected(self):
        conversation = Conversation.objects.create(buyer=self.buyer, seller=self.seller)
        response = self.client.post(
            self.admin_action("users", self.buyer.pk),
            {"action": "delete"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.buyer.refresh_from_db()
        self.assertTrue(self.buyer.is_active)
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())

    def test_superuser_can_create_admin_listing_and_open_conversation(self):
        product_response = self.client.post(
            self.admin_resource("products"),
            {
                "seller_id": str(self.seller.pk),
                "category": self.category.name,
                "name": "Admin-added table",
                "description": "A table added by the marketplace team.",
                "price": "2500.00",
                "condition": "gently_used",
                "county": "Nairobi",
                "town": "Nairobi",
            },
            format="json",
        )
        self.assertEqual(product_response.status_code, 201, product_response.data)
        product = Product.objects.get(pk=product_response.data["id"])
        self.assertTrue(product.admin_created)
        self.assertEqual(product.status, ProductStatus.ACTIVE)

        response = self.client.post(
            self.admin_resource("conversations"),
            {
                "buyer_id": str(self.buyer.pk),
                "seller_id": str(self.seller.pk),
                "product_id": str(product.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        conversation = Conversation.objects.get(pk=response.data["id"])
        self.assertTrue(conversation.admin_created)
        self.assertEqual(conversation.messages.count(), 0)
        self.assertEqual(Notification.objects.filter(target_id=str(conversation.pk)).count(), 2)

    def test_superuser_can_edit_demo_user_and_listing(self):
        product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name="Editable sample",
            description="Original description.",
            price="1000.00",
            condition="gently_used",
            county="Nairobi",
            town="Nairobi",
            admin_created=True,
        )
        user_response = self.client.patch(
            reverse("admin-resource-detail", kwargs={"resource": "users", "object_id": str(self.buyer.pk)}),
            {"first_name": "Updated", "last_name": "Buyer"},
            format="json",
        )
        self.assertEqual(user_response.status_code, 200, user_response.data)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.first_name, "Updated")

        product_response = self.client.patch(
            reverse("admin-resource-detail", kwargs={"resource": "products", "object_id": str(product.pk)}),
            {"name": "Updated sample", "price": "1200.00"},
            format="json",
        )
        self.assertEqual(product_response.status_code, 200, product_response.data)
        product.refresh_from_db()
        self.assertEqual(product.name, "Updated sample")
        self.assertEqual(str(product.price), "1200.00")

    def test_superuser_can_delete_admin_listing(self):
        product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name="Removable sample",
            description="Sample description.",
            price="1000.00",
            condition="gently_used",
            county="Nairobi",
            town="Nairobi",
            admin_created=True,
        )
        response = self.client.post(
            self.admin_action("products", product.pk),
            {"action": "delete"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    @override_settings(DEBUG=True)
    def test_demo_seed_command_is_idempotent(self):
        call_command("seed_demo_data", stdout=StringIO())
        call_command("seed_demo_data", stdout=StringIO())
        self.assertEqual(
            User.objects.filter(email__in=(
                "buyer.demo@example.test",
                "seller.home@example.test",
                "seller.tech@example.test",
            )).count(),
            3,
        )
        self.assertTrue(User.objects.get(email="buyer.demo@example.test").is_demo_account)
        self.assertEqual(Product.objects.filter(admin_created=True).count(), 3)
        self.assertEqual(Conversation.objects.filter(admin_created=True).count(), 1)

    @override_settings(DEBUG=True)
    def test_superuser_can_delete_seeded_demo_account_and_demo_conversation(self):
        call_command("seed_demo_data", stdout=StringIO())
        demo_buyer = User.objects.get(email="buyer.demo@example.test")
        demo_conversation = Conversation.objects.get(admin_created=True)
        response = self.client.post(
            self.admin_action("users", demo_buyer.pk),
            {"action": "delete"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(User.objects.filter(pk=demo_buyer.pk).exists())
        self.assertFalse(Conversation.objects.filter(pk=demo_conversation.pk).exists())

    def test_report_suspension_disables_account_and_pauses_listings(self):
        product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name="Seller listing",
            description="A listing.",
            price="1000.00",
            condition="new",
            county="Nairobi",
            town="Nairobi",
        )
        report = Report.objects.create(
            reporter=self.buyer,
            target_type=Report.TargetType.USER,
            target_id=self.seller.pk,
            reason="other",
        )
        response = self.client.post(
            self.admin_action("reports", report.pk),
            {"action": "suspend", "reason": "Under investigation"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.seller.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(self.seller.account_status, "temporarily_suspended")
        self.assertEqual(product.status, ProductStatus.PAUSED)

    def test_superuser_can_update_public_contact_and_about_content(self):
        response = self.client.patch(
            self.admin_resource("settings"),
            {
                "contact_email": "support@example.test",
                "about_title": "A marketplace for neighbours",
                "team_information": "Meet the community team.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        public = self.client.get(reverse("public-site-info"))
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.data["contact_email"], "support@example.test")
        self.assertEqual(public.data["about_title"], "A marketplace for neighbours")
