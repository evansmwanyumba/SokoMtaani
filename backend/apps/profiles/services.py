import hashlib
import hmac
import json
import re
import secrets
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from .models import PhoneVerification


class SmsDeliveryUnavailable(APIException):
    status_code = 503
    default_detail = "Phone verification is temporarily unavailable."
    default_code = "sms_unavailable"


def normalize_kenyan_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("254") and len(digits) == 12 and digits[3] in "17":
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 10 and digits[1] in "17":
        return f"+254{digits[1:]}"
    if len(digits) == 9 and digits[0] in "17":
        return f"+254{digits}"
    raise ValidationError({"phone_number": "Enter a valid Kenyan mobile number."})


def _code_digest(user_id, phone_number, code):
    message = f"{user_id}:{phone_number}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _deliver_sms(phone_number, code):
    endpoint = getattr(settings, "SMS_PROVIDER_URL", "")
    api_key = getattr(settings, "SMS_PROVIDER_API_KEY", "")
    sender_id = getattr(settings, "SMS_SENDER_ID", "")
    if not endpoint or not api_key or not sender_id:
        raise SmsDeliveryUnavailable(
            "Phone verification is not configured. Set SMS_PROVIDER_URL, SMS_PROVIDER_API_KEY, and SMS_SENDER_ID."
        )
    if not endpoint.startswith("https://") and not settings.DEBUG:
        raise ImproperlyConfigured("The production SMS provider endpoint must use HTTPS.")

    payload = json.dumps({
        "to": phone_number,
        "from": sender_id,
        "message": f"Your SokoMtaani verification code is {code}. It expires in 5 minutes.",
    }).encode()
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if not 200 <= response.status < 300:
                raise SmsDeliveryUnavailable()
    except (urllib.error.URLError, TimeoutError) as error:
        raise SmsDeliveryUnavailable() from error


def issue_phone_verification(user, phone_number):
    phone_number = normalize_kenyan_phone(phone_number)
    if PhoneVerification.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timedelta(minutes=1),
    ).exists():
        raise ValidationError({"detail": "Wait one minute before requesting another code."})

    code = f"{secrets.randbelow(1_000_000):06d}"
    now = timezone.now()
    PhoneVerification.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=now)
    verification = PhoneVerification.objects.create(
        user=user,
        phone_number=phone_number,
        code_digest=_code_digest(user.pk, phone_number, code),
        expires_at=now + timedelta(minutes=5),
    )
    _deliver_sms(phone_number, code)
    return verification


@transaction.atomic
def verify_phone_code(user, phone_number, code):
    phone_number = normalize_kenyan_phone(phone_number)
    verification = PhoneVerification.objects.select_for_update().filter(
        user=user,
        phone_number=phone_number,
        consumed_at__isnull=True,
    ).order_by("-created_at").first()
    if verification is None or not verification.is_valid:
        raise ValidationError({"code": "The verification code is invalid or expired."})

    verification.attempts += 1
    valid_digest = _code_digest(user.pk, phone_number, code)
    if not hmac.compare_digest(verification.code_digest, valid_digest):
        verification.save(update_fields=["attempts"])
        return None
    verification.consumed_at = timezone.now()
    verification.save(update_fields=["attempts", "consumed_at"])
    return phone_number
