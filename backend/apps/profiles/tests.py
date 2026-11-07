from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import SellerProfile, UserProfile
from .services import normalize_kenyan_phone


User = get_user_model()


class SellerActivationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="SafePassword!123",
            is_email_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_phone_number_normalization(self):
        self.assertEqual(normalize_kenyan_phone("0712 345 678"), "+254712345678")
        self.assertEqual(normalize_kenyan_phone("254712345678"), "+254712345678")
        with self.assertRaises(Exception):
            normalize_kenyan_phone("12345")

    def test_seller_activation_requires_verified_phone(self):
        response = self.client.post(
            reverse("seller-activate"),
            {"display_name": "Amina"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SellerProfile.objects.filter(user=self.user).exists())

    @patch("apps.profiles.services._deliver_sms")
    def test_phone_verification_and_seller_activation(self, deliver_sms):
        codes = []
        deliver_sms.side_effect = lambda phone, code: codes.append((phone, code))
        request = self.client.post(
            reverse("phone-verification"),
            {"phone_number": "0712345678"},
            format="json",
        )
        self.assertEqual(request.status_code, 202)
        self.assertEqual(codes[0][0], "+254712345678")
        verification = self.client.post(
            reverse("phone-verification-confirm"),
            {"phone_number": "0712345678", "code": codes[0][1]},
            format="json",
        )
        self.assertEqual(verification.status_code, 200, verification.data)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.phone_number, "+254712345678")
        self.assertIsNotNone(profile.phone_verified_at)

        activation = self.client.post(
            reverse("seller-activate"),
            {"display_name": "Amina Wanjiku"},
            format="json",
        )
        self.assertEqual(activation.status_code, 200, activation.data)
        self.assertTrue(SellerProfile.objects.filter(user=self.user, is_active=True).exists())

    @patch("apps.profiles.services._deliver_sms")
    def test_only_one_verification_attempt_is_used_for_wrong_code(self, deliver_sms):
        deliver_sms.return_value = None
        self.client.post(
            reverse("phone-verification"),
            {"phone_number": "0712345678"},
            format="json",
        )
        response = self.client.post(
            reverse("phone-verification-confirm"),
            {"phone_number": "0712345678", "code": "000000"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        from .models import PhoneVerification

        verification = PhoneVerification.objects.get(user=self.user)
        self.assertEqual(verification.attempts, 1)
