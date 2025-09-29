from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # Main admin dashboard
    path('', views.admin_dashboard, name='admin_dashboard'),

    # Category management
    path('categories/', views.manage_categories, name='manage_categories'),
    path('categories/delete/<uuid:category_id>/', views.delete_category, name='delete_category'),

    # User management
    path('users/', views.user_management, name='user_management'),
    path('users/register-investor/', views.register_investor, name='register_investor'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),  # Add this line
    path('users/<int:user_id>/verify/', views.verify_user, name='verify_user'),
    path('users/<int:user_id>/suspend/', views.suspend_user, name='suspend_user'),  # Add this line
    path('users/<int:user_id>/unsuspend/', views.unsuspend_user, name='unsuspend_user'),  # Add this line
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),  # Add this line
    path('users/bulk-action/', views.bulk_action, name='bulk_action'),

    # ... rest of your existing URLs remain the same ...
    # Pitch management
    path('pitches/', views.pitch_management, name='pitch_management'),
    path('pitches/<uuid:pitch_id>/review/', views.review_pitch, name='review_pitch'),

    # Payment management
    path('payments/', views.payment_management, name='payment_management'),

    # Enhanced Job Management System
    path('jobs/', views.job_management, name='job_management'),
    path('jobs/<uuid:job_id>/toggle-status/', views.toggle_job_status, name='toggle_job_status'),
    path('jobs/<uuid:job_id>/delete/', views.delete_job, name='delete_job'),
    path('jobs/<uuid:job_id>/feature/', views.feature_job, name='feature_job'),
    path('jobs/bulk-action/', views.bulk_job_action, name='bulk_job_action'),
    path('jobs/export/', views.export_jobs, name='export_jobs'),

    # Enhanced job applications management
    path('jobs/<uuid:job_id>/applications/', views.job_applications_list, name='job_applications'),
    path('applications/<uuid:application_id>/update-status/', views.update_application_status,
         name='update_application_status'),
    path('applications/<uuid:application_id>/details/', views.application_details, name='application_details'),
    path('applications/<uuid:application_id>/delete/', views.delete_application_admin, name='delete_application_admin'),
    path('jobs/<uuid:job_id>/applications/export/', views.export_applications, name='export_applications'),

    # Legacy/existing job management views (keeping for backward compatibility)
    path('jobs/<uuid:job_id>/', views.job_detail_admin, name='job_detail_admin'),
    path('applications/', views.application_management, name='application_management'),
    path('applications/<uuid:application_id>/', views.application_detail_admin, name='application_detail_admin'),

    # Job Analytics
    path('jobs/analytics/', views.job_analytics, name='job_analytics'),

    # Job Seeker Management
    path('job-seekers/', views.job_seeker_management, name='job_seeker_management'),
    path('job-seekers/<int:user_id>/', views.job_seeker_detail, name='job_seeker_detail'),

    # Platform Settings URLs (add these)
    path('settings/', views.platform_settings, name='platform_settings'),
    path('settings/history/', views.view_settings_history, name='settings_history'),
]