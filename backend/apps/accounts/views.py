import binascii

from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import status
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiResponse, extend_schema

from .email import send_password_reset_email, send_verification_email
from .services import account_is_active
from .models import User, UserRole
from .serializers import (
    CsrfTokenSerializer,
    DetailSerializer,
    EmailSerializer,
    EmailVerificationSerializer,
    LoginSerializer,
    MfaCodeSerializer,
    MfaRequiredSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    RegistrationSerializer,
    UserSerializer,
)
from .tokens import user_from_email_verification_token
from apps.community.models import AuditLog, PlatformSettings


MFA_SESSION_USER_KEY = "accounts_mfa_user_id"
MFA_SESSION_DEVICE_KEY = "accounts_mfa_device_id"
MFA_SESSION_ENROLLMENT_KEY = "accounts_mfa_enrollment"
MFA_REQUIRED_ROLES = {
    UserRole.ADMINISTRATOR,
    UserRole.MODERATOR,
    UserRole.SUPPORT_ADMINISTRATOR,
    UserRole.ANALYTICS_VIEWER,
}
MFA_REQUIRED_ADMIN_ROLES = {"moderator", "support_admin", "super_admin"}


def requires_mfa(user):
    return (
        user.is_staff
        or user.is_superuser
        or user.role in MFA_REQUIRED_ROLES
        or user.admin_role in MFA_REQUIRED_ADMIN_ROLES
    )


def begin_mfa_challenge(request, user):
    device = TOTPDevice.objects.filter(user=user, confirmed=True).order_by("pk").first()
    enrollment_required = device is None
    if enrollment_required:
        device = TOTPDevice.objects.filter(user=user, confirmed=False).order_by("pk").first()
        if device is None:
            device = TOTPDevice.objects.create(
                user=user,
                name="SokoMtaani authenticator",
                confirmed=False,
            )

    request.session[MFA_SESSION_USER_KEY] = str(user.pk)
    request.session[MFA_SESSION_DEVICE_KEY] = str(device.pk)
    request.session[MFA_SESSION_ENROLLMENT_KEY] = enrollment_required
    request.session.set_expiry(300)

    result = {
        "mfa_required": True,
        "enrollment_required": enrollment_required,
    }
    if enrollment_required:
        result["provisioning_uri"] = device.config_url
    return result


def complete_mfa_login(request, user, device):
    login(request, user)
    otp_login(request, device)
    request.session.pop(MFA_SESSION_USER_KEY, None)
    request.session.pop(MFA_SESSION_DEVICE_KEY, None)
    request.session.pop(MFA_SESSION_ENROLLMENT_KEY, None)
    request.session.set_expiry(None)


@method_decorator([ensure_csrf_cookie, never_cache], name="dispatch")
class CsrfTokenView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(responses=CsrfTokenSerializer)
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(never_cache, name="dispatch")
class RegistrationView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle, ScopedRateThrottle)
    throttle_scope = "register"

    @extend_schema(
        request=RegistrationSerializer,
        responses={
            201: UserSerializer,
            400: OpenApiResponse(description="Invalid registration data."),
        },
    )
    @transaction.atomic
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        AuditLog.objects.create(
            actor=user,
            action="account.registered",
            target_type=user._meta.label,
            target_id=str(user.pk),
            metadata={"ip_address": self.client_ip(request), "account_mode": user.account_mode},
        )
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def client_ip(request):
        return request.META.get("REMOTE_ADDR", "")[:64]


@method_decorator([csrf_protect, never_cache], name="dispatch")
class LoginView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle, ScopedRateThrottle)
    throttle_scope = "login"

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="Invalid credentials or request data."),
            403: OpenApiResponse(description="Account is pending administrator approval or is unavailable."),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.user.is_authenticated:
            logout(request._request)
        user = authenticate(
            request,
            email=User.objects.normalize_address(serializer.validated_data["email"]),
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not account_is_active(user):
            if user.account_status == "temporarily_suspended":
                return Response(
                    {
                        "code": "account_suspended",
                        "detail": "This account is suspended. Contact the SokoMtaani team for assistance.",
                        "contact_email": PlatformSettings.get_solo().contact_email,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            return Response(
                {
                    "code": "account_unavailable",
                    "detail": "This account is currently unavailable. Contact support for assistance.",
                    "contact_email": PlatformSettings.get_solo().contact_email,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not user.is_admin_approved:
            return Response(
                {
                    "code": "account_pending_approval",
                    "detail": "Your account is pending administrator approval. If this is taking time, please contact admin.",
                    "contact_email": PlatformSettings.get_solo().contact_email,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        login(request, user)
        AuditLog.objects.create(
            actor=user,
            action="account.signed_in",
            target_type=user._meta.label,
            target_id=str(user.pk),
            metadata={
                "ip_address": RegistrationView.client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
            },
        )
        return Response(UserSerializer(user).data)


@method_decorator([csrf_protect, never_cache], name="dispatch")
class MfaVerificationView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle, ScopedRateThrottle)
    throttle_scope = "mfa"

    @extend_schema(
        request=MfaCodeSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="Missing or invalid MFA challenge/code."),
        },
    )
    def post(self, request):
        serializer = MfaCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = request.session.get(MFA_SESSION_USER_KEY)
        device_id = request.session.get(MFA_SESSION_DEVICE_KEY)
        enrollment_required = request.session.get(MFA_SESSION_ENROLLMENT_KEY)
        if not user_id or not device_id or enrollment_required is None:
            return Response(
                {"detail": "No active MFA challenge. Sign in again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(
            pk=user_id,
            is_active=True,
            is_email_verified=True,
            account_status="active",
        ).first()
        if user is None or not requires_mfa(user):
            return Response(
                {"detail": "No active MFA challenge. Sign in again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        device = TOTPDevice.objects.filter(
            pk=device_id,
            user=user,
            confirmed=not enrollment_required,
        ).first()
        if device is None or not device.verify_token(
            int(serializer.validated_data["code"])
        ):
            return Response(
                {"code": ["Invalid or expired authenticator code."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if enrollment_required:
            device.confirmed = True
            device.save(update_fields=("confirmed",))
        complete_mfa_login(request._request, user, device)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=None,
        responses={204: OpenApiResponse(description="Session invalidated.")}
    )
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class EmailVerificationView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle, ScopedRateThrottle)
    throttle_scope = "email_verification"

    @extend_schema(
        request=EmailVerificationSerializer,
        responses={
            200: DetailSerializer,
            400: OpenApiResponse(description="Invalid or expired verification token."),
        },
    )
    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = user_from_email_verification_token(serializer.validated_data["token"])
        except (
            signing.BadSignature,
            signing.SignatureExpired,
            User.DoesNotExist,
            ValueError,
        ):
            return Response(
                {"token": ["Invalid or expired verification token."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=("is_email_verified", "updated_at"))
        return Response({"detail": "Email address verified."})


class ResendVerificationView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle, ScopedRateThrottle)
    throttle_scope = "email_verification"

    @extend_schema(request=EmailSerializer, responses=DetailSerializer)
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = User.objects.normalize_address(serializer.validated_data["email"])
        user = User.objects.filter(email__iexact=email, is_email_verified=False).first()
        if user is not None:
            send_verification_email(user)
        return Response(
            {"detail": "If the account needs verification, an email will be sent."}
        )


class PasswordResetRequestView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle, ScopedRateThrottle)
    throttle_scope = "password_reset"

    @extend_schema(request=EmailSerializer, responses=DetailSerializer)
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = User.objects.normalize_address(serializer.validated_data["email"])
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            send_password_reset_email(user)
        return Response(
            {"detail": "If an active account uses this email, reset instructions will be sent."}
        )


class PasswordResetConfirmView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle, ScopedRateThrottle)
    throttle_scope = "password_reset_confirm"

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={
            200: DetailSerializer,
            400: OpenApiResponse(description="Invalid data or expired reset token."),
        },
    )
    @transaction.atomic
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user_id = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except (
            binascii.Error,
            UnicodeDecodeError,
            ValueError,
            TypeError,
            User.DoesNotExist,
        ):
            return Response(
                {"token": ["Invalid or expired password reset token."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token = serializer.validated_data["token"]
        if not default_token_generator.check_token(user, token):
            return Response(
                {"token": ["Invalid or expired password reset token."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        password = serializer.validated_data["new_password"]
        try:
            validate_password(password, user=user)
        except DjangoValidationError as error:
            raise APIValidationError({"new_password": error.messages}) from error
        user.set_password(password)
        user.save(update_fields=("password", "updated_at"))
        AuditLog.objects.create(
            actor=user,
            action="account.password_reset",
            target_type=user._meta.label,
            target_id=str(user.pk),
            metadata={"ip_address": RegistrationView.client_ip(request)},
        )
        return Response({"detail": "Password has been reset."})


class PasswordChangeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={
            200: DetailSerializer,
            400: OpenApiResponse(description="Invalid current or new password."),
        },
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": ["Current password is incorrect."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        password = serializer.validated_data["new_password"]
        try:
            validate_password(password, user=request.user)
        except DjangoValidationError as error:
            raise APIValidationError({"new_password": error.messages}) from error
        request.user.set_password(password)
        request.user.save(update_fields=("password", "updated_at"))
        AuditLog.objects.create(
            actor=request.user,
            action="account.password_changed",
            target_type=request.user._meta.label,
            target_id=str(request.user.pk),
            metadata={"ip_address": RegistrationView.client_ip(request)},
        )
        update_session_auth_hash(request, request.user)
        return Response({"detail": "Password has been changed."})
