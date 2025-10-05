from django.urls import path
from . import views

app_name = 'pitches'

urlpatterns = [
    path('', views.pitch_list, name='pitch_list'),
    path('create/', views.create_pitch, name='create_pitch'),
    path('<uuid:pitch_id>/', views.pitch_detail, name='pitch_detail'),
    path('investor/browse/', views.investor_pitch_list, name='investor_pitch_list'),
    path('<uuid:pitch_id>/interest/', views.add_interest, name='add_interest'),
    path('<uuid:pitch_id>/remove-interest/', views.remove_interest, name='remove_interest'),
    path('file/<uuid:file_id>/download/', views.download_file, name='download_file'),  # ADD THIS LINE
    path('posts/', views.investor_posts_feed, name='investor_posts_feed'),
    path('posts/create/', views.create_investor_post, name='create_investor_post'),
    path('posts/<uuid:post_id>/', views.investor_post_detail, name='investor_post_detail'),
    path('guidelines/', views.pitch_guidelines, name='pitch_guidelines'),
]