# chat/urls.py
from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_list, name='chat_list'),
    path('<uuid:room_id>/', views.chat_room, name='chat_room'),
    path('<uuid:room_id>/send/', views.send_message, name='send_message'),
    path('test/<uuid:room_id>/', views.test_chat_room, name='test_chat_room'),
    path('update-activity/', views.update_activity, name='update_activity'),
    path('<uuid:room_id>/typing/', views.typing_status, name='typing_status'),
    path('start/<str:username>/', views.start_chat_with_user, name='start_chat'),
]