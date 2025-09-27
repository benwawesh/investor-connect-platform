from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('subscribe/', views.subscribe, name='subscribe'),
    path('callback/', views.mpesa_callback, name='mpesa_callback'),
    path('success/', views.payment_success, name='payment_success'),
    path('cancel/', views.payment_cancel, name='payment_cancel'),
    path('simulate-success/<int:payment_id>/', views.simulate_payment_success, name='simulate_payment_success'),  # For testing only
]