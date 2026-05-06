from django.contrib import admin
from .models import ConversationLog, MessageLog, DailyUsage

@admin.register(ConversationLog)
class ConversationLogAdmin(admin.ModelAdmin):
    list_display = ('session_id_short', 'started_at', 'total_messages')
    search_fields = ('session_id',)
    list_filter = ('started_at',)
    
    def session_id_short(self, obj):
        return obj.session_id[:16] + '...'

@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ('role', 'content_preview', 'timestamp', 'confidence_score')
    list_filter = ('role', 'timestamp')
    search_fields = ('content',)
    
    def content_preview(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content

@admin.register(DailyUsage)
class DailyUsageAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_requests', 'total_bot_responses', 'avg_confidence')
    list_filter = ('date',)