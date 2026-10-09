from django.urls import path

from . import views

urlpatterns = [
    path('login/',    views.login_view,    name='login'),
    path('logout/',   views.logout_view,   name='logout'),
    path('register/', views.register_view, name='register'),
    path('profile/',          views.profile_view,          name='profile'),
    path('profile/delete/',   views.delete_account_view,   name='delete-account'),
    path('forgot-password/',  views.forgot_password_view,  name='forgot-password'),
    path('reset-password/',   views.reset_password_view,   name='reset-password'),
]
