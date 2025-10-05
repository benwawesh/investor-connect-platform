# accounts/urls.py
from django.urls import path
from django.contrib.auth.views import LoginView
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup_with_payment, name='signup_with_payment'),
    path('login/', LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Profile Management URLs
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/settings/', views.profile_settings_menu, name='profile_settings_menu'),
    path('profile/delete-picture/', views.delete_profile_picture, name='delete_profile_picture'),

    # NEW: Separate CV Management Page
    path('cv/manage/', views.manage_cv, name='manage_cv'),

    path('settings/password/', views.change_password, name='change_password'),
    path('settings/notifications/', views.notification_settings, name='notification_settings'),
    path('contact-admin/', views.contact_admin, name='contact_admin'),

    # GENERIC PATTERN LAST
    path('profile/<str:username>/', views.profile_detail_view, name='profile_detail'),

    # M-Pesa Payment Integration
    path('payments/status/', views.check_payment_status, name='check_payment_status'),
]