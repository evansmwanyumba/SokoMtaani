from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient, APITestCase

from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts.admin import secure_admin_site
from apps.accounts.forms import AccountCreationForm
from apps.accounts.models import UserRole
from apps.accounts.tokens import make_email_verification_token


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_BASE_URL="https://frontend.example.test",
)
class AuthenticationTests(APITestCase):
    def create_verified_user(self, email="buyer@example.com", password="SafePassword!123"):
        user = User.objects.create_user(
            email=email,
            password=password,
            is_email_verified=True,
        )
        return user, password

    def test_admin_creation_form_accepts_email_without_username(self):
        form = AccountCreationForm(
            data={
                "email": "admin-created@example.com",
                "role": UserRole.BUYER,
                "password1": "SafePassword!123",
                "password2": "SafePassword!123",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, "admin-created@example.com")
        self.assertTrue(user.check_password("SafePassword!123"))

    def test_registration_creates_active_buyer_without_email_verification(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "Buyer@Example.com",
                "password": "SafePassword!123",
                "first_name": "Amina",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="buyer@example.com")
        self.assertEqual(user.role, UserRole.BUYER)
        self.assertFalse(user.is_email_verified)
        self.assertTrue(user.is_admin_approved)
        self.assertEqual(user.account_mode, "general")
        self.assertTrue(user.check_password("SafePassword!123"))
        self.assertTrue(user.password.startswith("argon2"))
        self.assertEqual(len(mail.outbox), 0)

    def test_registration_ignores_conditional_cache_headers_and_returns_created(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "fresh-registration@example.com",
                "password": "SafePassword!123",
            },
            format="json",
            HTTP_IF_NONE_MATCH='"cached-response"',
            HTTP_IF_MODIFIED_SINCE="Thu, 01 Jan 1970 00:00:00 GMT",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("no-store", response["Cache-Control"])

    def test_registration_does_not_require_approval_or_send_approval_notification(self):
        User.objects.create_superuser(
            email="admin@example.com",
            password="SafePassword!123",
        )
        response = self.client.post(
            reverse("register"),
            {
                "email": "buyer@example.com",
                "password": "SafePassword!123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        registered = User.objects.get(email="buyer@example.com")
        self.assertEqual(registered.role, UserRole.BUYER)
        from apps.notifications.models import Notification

        self.assertTrue(registered.is_admin_approved)
        self.assertFalse(Notification.objects.filter(kind="account_approval").exists())

    def test_email_verification_activates_account_verification(self):
        user = User.objects.create_user(email="buyer@example.com", password="SafePassword!123")

        response = self.client.post(
            reverse("verify-email"),
            {"token": make_email_verification_token(user)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

    def test_bad_verification_token_is_rejected(self):
        response = self.client.post(
            reverse("verify-email"),
            {"token": "not-a-valid-token"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_email_verification_is_not_required_for_approved_user_login(self):
        user = User.objects.create_user(email="buyer@example.com", password="SafePassword!123")

        response = self.client.post(
            reverse("login"),
            {"email": user.email, "password": "SafePassword!123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

    def test_unapproved_user_login_waits_for_superuser_approval(self):
        user = User.objects.create_user(
            email="pending@example.com",
            password="SafePassword!123",
            is_admin_approved=False,
        )
        response = self.client.post(
            reverse("login"),
            {"email": user.email, "password": "SafePassword!123"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "account_pending_approval")
        self.assertEqual(response.data["contact_email"], "hello@sokomtaani.co.ke")

    def test_superuser_can_sign_in_without_totp_for_development(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="SafePassword!123",
        )

        login_response = self.client.post(
            reverse("login"),
            {"email": user.email, "password": "SafePassword!123"},
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_privileged_account_can_sign_in_without_totp_during_development(self):
        user = User.objects.create_user(
            email="moderator@example.com",
            password="SafePassword!123",
            role=UserRole.MODERATOR,
            is_email_verified=True,
        )

        response = self.client.post(
            reverse("login"),
            {"email": user.email, "password": "SafePassword!123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 200)

    def test_django_admin_login_does_not_require_totp_during_development(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="SafePassword!123",
        )
        response = self.client.post(
            reverse("admin:login"),
            {
                "username": user.email,
                "password": "SafePassword!123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_admin_login_does_not_start_totp_challenge(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="SafePassword!123",
        )
        login_response = self.client.post(
            reverse("login"),
            {"email": user.email, "password": "SafePassword!123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 200)

    def test_mfa_endpoint_rejects_requests_without_login_challenge(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="SafePassword!123",
        )
        response = self.client.post(
            reverse("mfa-verify"),
            {"code": "000000"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 403)

    def test_mfa_verification_without_challenge_is_rejected(self):
        response = self.client.post(
            reverse("mfa-verify"),
            {"code": "123456"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_admin_session_without_otp_is_allowed_during_development(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="SafePassword!123",
        )
        self.client.force_login(user)
        request = self.client.get(reverse("admin:index")).wsgi_request

        self.assertTrue(secure_admin_site.has_permission(request))
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_login_requires_csrf_and_sets_a_session(self):
        user, password = self.create_verified_user()
        client = APIClient(enforce_csrf_checks=True)
        csrf_response = client.get(reverse("csrf-cookie"))
        self.assertEqual(csrf_response.status_code, 200)
        self.assertIn("no-store", csrf_response["Cache-Control"])
        csrf_token = csrf_response.json()["csrfToken"]
        self.assertIn("csrftoken", client.cookies)

        rejected = client.post(
            reverse("login"),
            {"email": user.email, "password": password},
            format="json",
        )
        self.assertEqual(rejected.status_code, 403)

        accepted = client.post(
            reverse("login"),
            {"email": user.email, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertIn("sessionid", client.cookies)
        self.assertEqual(client.get(reverse("current-user")).status_code, 200)

    def test_login_is_throttled(self):
        cache.clear()
        self.addCleanup(cache.clear)

        for _ in range(10):
            response = self.client.post(
                reverse("login"),
                {"email": "buyer@example.com", "password": "WrongPassword!123"},
                format="json",
            )
            self.assertEqual(response.status_code, 400)

        response = self.client.post(
            reverse("login"),
            {"email": "buyer@example.com", "password": "WrongPassword!123"},
            format="json",
        )
        self.assertEqual(response.status_code, 429)

    def test_logout_invalidates_session(self):
        user, _ = self.create_verified_user()
        self.client.force_login(user)

        response = self.client.post(reverse("logout"))

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 403)

    def test_password_reset_email_and_confirmation(self):
        user, _ = self.create_verified_user()
        request_response = self.client.post(
            reverse("password-reset-request"),
            {"email": user.email},
            format="json",
        )
        self.assertEqual(request_response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        reset_url = next(
            line for line in mail.outbox[0].body.splitlines() if line.startswith("https://")
        )
        parsed_url = urlparse(reset_url)
        self.assertEqual(parsed_url.path, "/")
        self.assertTrue(parsed_url.fragment.startswith("/reset-password?"))
        query = parse_qs(parsed_url.fragment.split("?", 1)[1])
        response = self.client.post(
            reverse("password-reset-confirm"),
            {
                "uid": query["uid"][0],
                "token": query["token"][0],
                "new_password": "AnotherSafePassword!456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("AnotherSafePassword!456"))

    def test_reset_request_does_not_disclose_unknown_email(self):
        response = self.client.post(
            reverse("password-reset-request"),
            {"email": "unknown@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_password_change_keeps_current_session_authenticated(self):
        user, password = self.create_verified_user()
        self.client.force_login(user)

        response = self.client.post(
            reverse("password-change"),
            {
                "old_password": password,
                "new_password": "AnotherSafePassword!456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("AnotherSafePassword!456"))

    def test_password_change_requires_authentication(self):
        response = self.client.post(
            reverse("password-change"),
            {
                "old_password": "SafePassword!123",
                "new_password": "AnotherSafePassword!456",
            },
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_password_change_rejects_weak_password(self):
        user, password = self.create_verified_user()
        self.client.force_login(user)

        response = self.client.post(
            reverse("password-change"),
            {"old_password": password, "new_password": "short"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json())
        user.refresh_from_db()
        self.assertTrue(user.check_password(password))

    def test_password_reset_invalidates_existing_session(self):
        user, _ = self.create_verified_user()
        self.client.force_login(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = self.client.post(
            reverse("password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "AnotherSafePassword!456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("current-user")).status_code, 403)

    def test_password_reset_rejects_weak_password(self):
        user, _ = self.create_verified_user()
        response = self.client.post(
            reverse("password-reset-confirm"),
            {
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": default_token_generator.make_token(user),
                "new_password": "short",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json())
