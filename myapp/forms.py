import re
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from .models import Profile


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['full_name', 'age', 'gender', 'height', 'weight']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'age': forms.NumberInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'height': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
        }

        
class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Enter username'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Enter email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Enter password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm password'}))

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("Username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        username = self.cleaned_data.get('username')

        if not password:
            return password

        # Rule 1: Length check
        if len(password) < 8:
            raise ValidationError("Password must contain at least 8 characters.")

        # Rule 2: Lowercase check
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least 1 lowercase letter.")

        # Rule 3: Uppercase check
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least 1 uppercase letter.")

        # Rule 4: Special character check
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError("Password must contain at least 1 special character.")

        # Rule 5: Should not be similar to username
        if username and username.lower() in password.lower():
            raise ValidationError("Password should not contain your username.")

        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords do not match.")
        return cleaned_data


class LoginForm(forms.Form):
    username_or_email = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Username or Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))


class ForgotPasswordForm(forms.Form):
    username_or_email = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Enter your Username or Email'}))

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Clear default Django help text for clean rendering
        self.fields['old_password'].help_text = None
        self.fields['new_password1'].help_text = None
        self.fields['new_password2'].help_text = None

    def clean_new_password1(self):
        old_password = self.cleaned_data.get('old_password')
        password = self.cleaned_data.get('new_password1')

        if not password:
            return password

        # Rule 1: Length check
        if len(password) < 8:
            raise ValidationError("Password must contain at least 8 characters.")

        # Rule 2: Lowercase check
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least 1 lowercase letter.")

        # Rule 3: Uppercase check
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least 1 uppercase letter.")

        # Rule 4: Special character check
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError("Password must contain at least 1 special character.")

        # Rule 5: Should not be similar to old password
        if old_password and old_password.lower() in password.lower():
            raise ValidationError("Password should not be similar to your current password.")

        return password