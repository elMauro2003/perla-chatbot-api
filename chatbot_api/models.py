from django.db import models

class ConversationLog(models.Model):
    """Registro de cada conversación"""
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_messages = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-started_at']
        verbose_name = "Conversación"
        verbose_name_plural = "Conversaciones"
    
    def __str__(self):
        return f"Conv {self.session_id[:8]}... - {self.started_at.strftime('%d/%m/%Y %H:%M')}"

class MessageLog(models.Model):
    """Registro de cada mensaje individual"""
    conversation = models.ForeignKey(
        ConversationLog, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    role = models.CharField(
        max_length=10, 
        choices=[('user', 'Usuario'), ('bot', 'Chatbot')]
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    confidence_score = models.FloatField(null=True, blank=True)
    needs_human = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['role']),
        ]
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"
    
    def __str__(self):
        return f"[{self.role}] {self.content[:60]}..."

class DailyUsage(models.Model):
    """Uso diario del LLM"""
    date = models.DateField(auto_now_add=True, unique=True, db_index=True)
    total_requests = models.IntegerField(default=0)
    total_user_messages = models.IntegerField(default=0)
    total_bot_responses = models.IntegerField(default=0)
    total_tokens_used = models.IntegerField(default=0)
    total_words_generated = models.IntegerField(default=0)
    avg_confidence = models.FloatField(default=0.0)
    human_escalations = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-date']
        verbose_name = "Uso Diario"
        verbose_name_plural = "Usos Diarios"
    
    def __str__(self):
        return f"Uso {self.date}: {self.total_requests} reqs, {self.total_tokens_used} tokens"