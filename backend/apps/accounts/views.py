from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .forms import (
    DeleteAccountForm, ForgotPasswordForm, LoginForm,
    PasswordChangeForm, RegisterForm, ResetPasswordForm,
)
from .models import User


def login_view(request):
    if request.user.is_authenticated:
        logout(request)
        return redirect('login')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get('next') or 'dashboard')
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def profile_view(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    form = PasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        return JsonResponse({'ok': True})
    errors = {field: errs.as_text() for field, errs in form.errors.items()}
    return JsonResponse({'ok': False, 'errors': errors}, status=400)


@login_required
def delete_account_view(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    form = DeleteAccountForm(request.user, request.POST)
    if form.is_valid():
        user = request.user
        logout(request)
        user.delete()
        return JsonResponse({'ok': True})
    errors = {field: errs.as_text() for field, errs in form.errors.items()}
    return JsonResponse({'ok': False, 'errors': errors}, status=400)


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = ForgotPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.session['reset_user_id'] = str(form.get_user().id)
        return redirect('reset-password')
    return render(request, 'accounts/forgot_password.html', {'form': form})


def reset_password_view(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('forgot-password')
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        request.session.pop('reset_user_id', None)
        return redirect('forgot-password')

    form = ResetPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user.set_password(form.cleaned_data['new_password'])
        user.save(update_fields=['password'])
        request.session.pop('reset_user_id', None)
        login(request, user)
        return redirect('dashboard')
    return render(request, 'accounts/reset_password.html', {'form': form, 'email': user.email})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'accounts/register.html', {'form': form})
