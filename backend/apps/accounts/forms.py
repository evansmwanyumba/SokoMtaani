from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import User


class TOTPAdminAuthenticationForm(AdminAuthenticationForm):
    otp_token = forms.RegexField(
        regex=r"^\d{6}$",
        max_length=6,
        label="Authenticator code",
        error_messages={"invalid": "Enter the 6-digit code from your authenticator app."},
    )

    def clean(self):
        cleaned_data = super().clean()
        user = self.get_user()
        if user is None:
            return cleaned_data

        device = TOTPDevice.objects.filter(user=user, confirmed=True).order_by("pk").first()
        code = cleaned_data.get("otp_token")
        if device is None or code is None or not device.verify_token(int(code)):
            self.add_error("otp_token", "Invalid authenticator code.")
            return cleaned_data

        user.otp_device = device
        return cleaned_data


class AccountCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Password confirmation",
        strip=False,
        widget=forms.PasswordInput,
    )

    class Meta:
        model = User
        fields = ("email", "role")

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two password fields did not match.")
        if password1:
            self.instance.email = cleaned_data.get("email", "")
            validate_password(password1, user=self.instance)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user
