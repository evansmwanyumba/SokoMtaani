from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.categories.models import Category
from apps.community.models import Block, Report
from apps.products.models import Product
from apps.profiles.models import SellerProfile

from .models import Conversation, Message


User = get_user_model()


class MessagingApiTests(TestCase):
    def setUp(self):
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
            display_name="Amina Wanjiku",
            phone_number="+254712345678",
            phone_verified_at=timezone.now(),
        )
        self.category = Category.objects.create(name="Books", slug="books")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name="Novel",
            description="A good book.",
            price="500.00",
            condition="new",
            county="Nairobi",
            town="Westlands",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)

    def test_member_can_start_product_conversation_and_send_message(self):
        response = self.client.post(
            reverse("conversation-list"),
            {"recipient": str(self.seller.pk), "product": str(self.product.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        conversation = Conversation.objects.get()
        self.assertEqual(response.data["other_user_id"], str(self.seller.pk))
        message_response = self.client.post(
            reverse("conversation-messages", kwargs={"conversation_id": conversation.pk}),
            {"content": "Is this still available?"},
            format="json",
        )

        self.assertEqual(message_response.status_code, 201, message_response.data)
        self.assertEqual(Message.objects.get().sender, self.buyer)

    def test_non_participant_cannot_read_conversation_or_messages(self):
        conversation = Conversation.objects.create(buyer=self.buyer, seller=self.seller)
        stranger = User.objects.create_user(
            email="stranger@example.com",
            password="Secure-test-Password1",
            is_email_verified=True,
        )
        self.client.force_authenticate(stranger)

        detail = self.client.get(reverse("conversation-detail", kwargs={"conversation_id": conversation.pk}))
        messages = self.client.get(
            reverse("conversation-messages", kwargs={"conversation_id": conversation.pk})
        )

        self.assertEqual(detail.status_code, 404)
        self.assertEqual(messages.status_code, 404)

    def test_blocked_member_cannot_send_message(self):
        conversation = Conversation.objects.create(buyer=self.buyer, seller=self.seller)
        Block.objects.create(blocker=self.seller, blocked=self.buyer)

        response = self.client.post(
            reverse("conversation-messages", kwargs={"conversation_id": conversation.pk}),
            {"content": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Message.objects.exists())

    def test_member_can_report_only_a_message_in_their_conversation(self):
        conversation = Conversation.objects.create(buyer=self.buyer, seller=self.seller)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.seller,
            content="Please contact me.",
        )
        response = self.client.post(
            reverse("report-create"),
            {
                "target_type": Report.TargetType.MESSAGE,
                "target_id": str(message.pk),
                "reason": "harassment",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Report.objects.get().reporter, self.buyer)

        stranger = User.objects.create_user(
            email="stranger@example.com",
            password="Secure-test-Password1",
            is_email_verified=True,
        )
        self.client.force_authenticate(stranger)
        denied = self.client.post(
            reverse("report-create"),
            {
                "target_type": Report.TargetType.MESSAGE,
                "target_id": str(message.pk),
                "reason": "harassment",
            },
            format="json",
        )

        self.assertEqual(denied.status_code, 400)
