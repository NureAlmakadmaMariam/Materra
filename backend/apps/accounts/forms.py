from django import forms
from django.contrib.auth import authenticate

from .models import User


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='Електронна пошта',
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('email')
        password = cleaned.get('password')
        if email and password:
            self.user_cache = authenticate(username=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError('Невірна електронна пошта або пароль.')
            if not self.user_cache.is_active:
                raise forms.ValidationError('Цей акаунт деактивовано.')
        return cleaned

    def get_user(self):
        return self.user_cache


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        label='Пароль',
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Мінімум 8 символів',
            'autocomplete': 'new-password',
        }),
    )
    password_confirm = forms.CharField(
        label='Підтвердження пароля',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Повторіть пароль',
            'autocomplete': 'new-password',
        }),
    )

    class Meta:
        model = User
        fields = ['email', 'full_name']
        labels = {
            'email': 'Електронна пошта',
            'full_name': "Повне ім'я",
        }
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
            'full_name': forms.TextInput(attrs={'placeholder': "Ім'я Прізвище"}),
        }

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', 'Паролі не збігаються.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        label='Поточний пароль',
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )
    new_password = forms.CharField(
        label='Новий пароль',
        min_length=8,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    new_password_confirm = forms.CharField(
        label='Підтвердження нового пароля',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        pw = self.cleaned_data.get('current_password')
        if not self.user.check_password(pw):
            raise forms.ValidationError('Невірний поточний пароль.')
        return pw

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password')
        p2 = cleaned.get('new_password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('new_password_confirm', 'Паролі не збігаються.')
        return cleaned

    def save(self):
        self.user.set_password(self.cleaned_data['new_password'])
        self.user.save(update_fields=['password'])
        return self.user


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        label='Електронна пошта',
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autofocus': True}),
    )
    full_name = forms.CharField(
        label="Повне ім'я",
        widget=forms.TextInput(attrs={'placeholder': "Ім'я Прізвище"}),
    )

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('email')
        full_name = (cleaned.get('full_name') or '').strip()
        if email and full_name:
            try:
                user = User.objects.get(email__iexact=email)
                if user.full_name.strip().lower() != full_name.lower():
                    raise forms.ValidationError('Не знайдено акаунт з такими даними.')
                self._user = user
            except User.DoesNotExist:
                raise forms.ValidationError('Не знайдено акаунт з такими даними.')
        return cleaned

    def get_user(self):
        return getattr(self, '_user', None)


class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(
        label='Новий пароль',
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Мінімум 8 символів',
            'autocomplete': 'new-password',
        }),
    )
    new_password_confirm = forms.CharField(
        label='Підтвердження пароля',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Повторіть новий пароль',
            'autocomplete': 'new-password',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password')
        p2 = cleaned.get('new_password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('new_password_confirm', 'Паролі не збігаються.')
        return cleaned


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        pw = self.cleaned_data.get('password')
        if not self.user.check_password(pw):
            raise forms.ValidationError('Невірний пароль.')
        return pw
