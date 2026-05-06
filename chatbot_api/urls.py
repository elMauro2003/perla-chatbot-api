from django.urls import path
from . import views

urlpatterns = [
    # Endpoints públicos
    path('chat/', views.chat_view, name='chat'),
    path('health/', views.health_check, name='health'),
    
    # Endpoints administrativos (requieren X-Admin-API-Key)
    path('admin/tokens/', views.admin_token_usage, name='admin_tokens'),
    path('admin/stats/', views.admin_stats, name='admin_stats'),
    path('admin/export/chat/pdf/', views.admin_export_chat_pdf, name='admin_export_chat_pdf'),
    path('admin/export/stats/pdf/', views.admin_export_stats_pdf, name='admin_export_stats_pdf'),
    path('admin/conversations/', views.admin_list_conversations, name='admin_conversations'),
    path('admin/conversations/<str:session_id>/', views.admin_conversation_detail, name='admin_conversation_detail'),
]