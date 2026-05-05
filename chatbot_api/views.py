from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .ai_service import chatbot_service
import logging
import traceback

logger = logging.getLogger(__name__)

@api_view(['POST'])
def chat_view(request):
    """
    Endpoint principal del chatbot
    
    Espera recibir:
    {
        "message": "texto del usuario",
        "history": [{"role": "user/assistant", "content": "mensaje"}],
        "session_id": "identificador_opcional"
    }
    
    Retorna:
    {
        "success": true/false,
        "message": "respuesta del bot",
        "needs_human": true/false,
        "confidence": 0.0-1.0
    }
    """
    try:
        # Obtener datos del request
        user_message = request.data.get('message', '').strip()
        history = request.data.get('history', [])
        session_id = request.data.get('session_id', None)
        
        # Validar que hay mensaje
        if not user_message:
            return Response(
                {
                    'success': False,
                    'message': 'Por favor, escribe un mensaje.',
                    'error': 'message_required'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validar longitud del mensaje
        if len(user_message) > 500:
            return Response(
                {
                    'success': False,
                    'message': 'El mensaje es demasiado largo. Por favor, resume tu consulta.',
                    'error': 'message_too_long'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Limitar historial a últimos 6 mensajes para no sobrecargar
        limited_history = history[-6:] if history else []
        
        logger.info(f"📨 Mensaje recibido: {user_message[:50]}...")
        
        # Obtener respuesta del chatbot
        result = chatbot_service.chat(user_message, limited_history)
        
        # Agregar session_id si se proporcionó
        if session_id:
            result['session_id'] = session_id
        
        logger.info(f"📤 Respuesta enviada: {result['message'][:50]}...")
        
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ Error en chat_view: {str(e)}")
        logger.error(traceback.format_exc())
        
        return Response(
            {
                'success': False,
                'message': 'Lo siento, ocurrió un error interno. Por favor, intenta de nuevo más tarde.',
                'error': 'internal_error',
                'needs_human': True,
                'confidence': 0.0
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def health_check(request):
    """
    Endpoint para verificar que el servicio esté funcionando
    """
    try:
        knowledge_size = len(chatbot_service.full_context)
        knowledge_loaded = knowledge_size > 100  # Al menos 100 caracteres
        
        return Response({
            'status': 'ok',
            'service': 'Chatbot API con Contexto Directo',
            'model': 'deepseek/deepseek-chat',
            'provider': 'OpenRouter',
            'knowledge_base': {
                'loaded': knowledge_loaded,
                'size_chars': knowledge_size,
                'size_tokens_approx': len(chatbot_service.full_context.split()) * 1.3
            },
            'timestamp': str(__import__('datetime').datetime.now())
        })
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def reload_knowledge(request):
    """
    Endpoint para recargar la base de conocimiento sin reiniciar el servidor
    
    Útil cuando actualizas el archivo conocimiento.txt
    """
    try:
        chatbot_service.reload_knowledge()
        return Response({
            'success': True,
            'message': 'Base de conocimiento recargada exitosamente',
            'size': len(chatbot_service.full_context)
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error al recargar: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)