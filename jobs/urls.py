from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    # Job listings and search
    path('', views.job_list, name='job_list'),
    path('search/', views.job_search, name='job_search'),
    path('<uuid:job_id>/', views.job_detail, name='job_detail'),

    # Job posting (for employers)
    path('post/', views.post_job, name='post_job'),
    path('<uuid:job_id>/edit/', views.edit_job, name='edit_job'),
    path('<uuid:job_id>/delete/', views.delete_job, name='delete_job'),
    path('my-jobs/', views.my_job_postings, name='my_job_postings'),

    # Job applications
    path('<uuid:job_id>/apply/', views.apply_job, name='apply_job'),
    path('applications/', views.my_applications, name='my_applications'),
    path('applications/<uuid:application_id>/', views.application_detail, name='application_detail'),
    path('applications/<uuid:application_id>/withdraw/', views.withdraw_application, name='withdraw_application'),

    # For employers - manage applications
    path('<uuid:job_id>/applications/', views.job_applications, name='job_applications'),
    path('applications/<uuid:application_id>/update-status/', views.update_application_status,
         name='update_application_status'),

    # Saved jobs (for job seekers)
    path('<uuid:job_id>/save/', views.save_job, name='save_job'),
    path('<uuid:job_id>/unsave/', views.unsave_job, name='unsave_job'),
    path('saved/', views.saved_jobs, name='saved_jobs'),

    # Job alerts
    path('alerts/', views.job_alerts, name='job_alerts'),
    path('alerts/create/', views.create_job_alert, name='create_job_alert'),
    path('alerts/<uuid:alert_id>/edit/', views.edit_job_alert, name='edit_job_alert'),
    path('alerts/<uuid:alert_id>/delete/', views.delete_job_alert, name='delete_job_alert'),
    path('alerts/<uuid:alert_id>/toggle/', views.toggle_job_alert, name='toggle_job_alert'),
]