import threading
from datetime import date
from .models import ConversationLog, MessageLog, DailyUsage
import logging

logger = logging.getLogger(__name__)

def save_message_async(session_id, role, content, confidence=None, needs_human=False):
    """
    Guarda mensaje en segundo plano para no bloquear la respuesta.
    También actualiza el contador diario.
    """
    def _save():
        try:
            # 1. Guardar conversación y mensaje
            conversation, created = ConversationLog.objects.get_or_create(
                session_id=session_id
            )
            
            msg = MessageLog.objects.create(
                conversation=conversation,
                role=role,
                content=content,
                confidence_score=confidence,
                needs_human=needs_human
            )
            
            conversation.total_messages = conversation.messages.count()
            conversation.save()
            
            # 2. Actualizar uso diario
            today = date.today()
            daily, _ = DailyUsage.objects.get_or_create(date=today)
            
            if role == 'user':
                daily.total_requests += 1
                daily.total_user_messages += 1
            elif role == 'bot':
                daily.total_bot_responses += 1
                daily.total_words_generated += len(content.split())
                
                if confidence is not None:
                    total_responses = daily.total_bot_responses
                    if total_responses > 1:
                        prev_total_confidence = daily.avg_confidence * (total_responses - 1)
                        daily.avg_confidence = round((prev_total_confidence + confidence) / total_responses, 2)
                    else:
                        daily.avg_confidence = confidence
                
                if needs_human:
                    daily.human_escalations += 1
            
            daily.save()
            
        except Exception as e:
            logger.error(f"Error guardando mensaje: {e}")
    
    # Ejecutar en thread separado para no bloquear
    thread = threading.Thread(target=_save, daemon=True)
    thread.start()