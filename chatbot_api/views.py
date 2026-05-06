from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.utils import timezone
from datetime import date, timedelta, datetime
from .ai_service import chatbot_service
from .auth import require_admin_api_key
from .logging_service import save_message_async
from .monitor import TokenMonitor
from .pdf_generator import generate_chat_pdf, generate_stats_pdf, _get_conversations_for_range
from .models import ConversationLog
import logging
import uuid
import traceback

logger = logging.getLogger(__name__)

# ============================================
# ENDPOINTS PÚBLICOS
# ============================================

@api_view(['POST'])
def chat_view(request):
    """
    Endpoint principal del chatbot
    """
    try:
        user_message = request.data.get('message', '').strip()
        history = request.data.get('history', [])
        session_id = request.data.get('session_id', str(uuid.uuid4()))
        
        if not user_message:
            return Response(
                {'success': False, 'message': 'Por favor, escribe un mensaje.', 'error': 'message_required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(user_message) > 500:
            return Response(
                {'success': False, 'message': 'El mensaje es demasiado largo.', 'error': 'message_too_long'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        limited_history = history[-6:] if history else []
        
        # ⭐ GUARDAR PREGUNTA DEL USUARIO
        logger.info(f"📨 Mensaje recibido: {user_message[:50]}...")
        save_message_async(
            session_id=session_id,
            role='user',
            content=user_message
        )
        
        # Obtener respuesta del chatbot
        result = chatbot_service.chat(user_message, limited_history)
        
        # ⭐ GUARDAR RESPUESTA DEL BOT
        save_message_async(
            session_id=session_id,
            role='bot',
            content=result['message'],
            confidence=result.get('confidence', 0),
            needs_human=result.get('needs_human', False)
        )
        
        result['session_id'] = session_id
        logger.info(f"📤 Respuesta enviada: {result['message'][:50]}...")
        
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ Error en chat_view: {str(e)}")
        logger.error(traceback.format_exc())
        
        return Response(
            {
                'success': False,
                'message': 'Lo siento, ocurrió un error interno.',
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
        
        
        
        

# ============================================
# ENDPOINTS ADMINISTRATIVOS (REQUIEREN API KEY)
# ============================================

@api_view(['GET'])
@require_admin_api_key
def admin_token_usage(request):
    """
    GET /api/admin/tokens/
    Header: X-Admin-API-Key: <admin_key>
    
    Retorna uso de tokens y stats del día actual
    """
    stats = TokenMonitor.get_daily_stats()
    return Response({'success': True, 'data': stats})

@api_view(['GET'])
@require_admin_api_key
def admin_stats(request):
    """
    GET /api/admin/stats/?period=today|week|month|year|range&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    Header: X-Admin-API-Key: <admin_key>
    """
    period = request.GET.get('period', 'today')
    
    if period == 'today':
        stats = TokenMonitor.get_daily_stats()
    elif period == 'week':
        stats = TokenMonitor.get_weekly_stats()
    elif period == 'month':
        stats = TokenMonitor.get_monthly_stats()
    elif period == 'year':
        stats = TokenMonitor.get_yearly_stats()
    elif period == 'range':
        start_str = request.GET.get('start_date', '')
        end_str = request.GET.get('end_date', '')
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            stats = TokenMonitor.get_range_stats(start_date, end_date)
        except (ValueError, TypeError):
            return Response(
                {'success': False, 'message': 'Formato de fecha inválido. Use YYYY-MM-DD'},
                status=400
            )
    else:
        return Response(
            {'success': False, 'message': f'Período no válido: {period}. Use: today, week, month, year, range'},
            status=400
        )
    
    return Response({'success': True, 'data': stats})

@api_view(['GET'])
@require_admin_api_key
def admin_export_chat_pdf(request):
    """
    GET /api/admin/export/chat/pdf/?period=today|week|month|year|range&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    Header: X-Admin-API-Key: <admin_key>
    
    Retorna PDF con conversaciones filtradas por fecha
    """
    period = request.GET.get('period', 'today')
    title = "Registro de Conversaciones"
    
    if period == 'today':
        specific_date = date.today()
        conversations = _get_conversations_for_range(specific_date=specific_date)
        title = f"Conversaciones del Día - {specific_date.strftime('%d/%m/%Y')}"
    
    elif period == 'week':
        today = date.today()
        week_ago = today - timedelta(days=6)
        conversations = _get_conversations_for_range(start_date=week_ago, end_date=today)
        title = f"Conversaciones de la Semana - {week_ago.strftime('%d/%m/%Y')} al {today.strftime('%d/%m/%Y')}"
    
    elif period == 'month':
        today = date.today()
        month_start = today.replace(day=1)
        conversations = _get_conversations_for_range(start_date=month_start, end_date=today)
        title = f"Conversaciones del Mes - {month_start.strftime('%B %Y')}"
    
    elif period == 'year':
        today = date.today()
        year_start = today.replace(month=1, day=1)
        conversations = _get_conversations_for_range(start_date=year_start, end_date=today)
        title = f"Conversaciones del Año {today.year}"
    
    elif period == 'range':
        start_str = request.GET.get('start_date', '')
        end_str = request.GET.get('end_date', '')
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            conversations = _get_conversations_for_range(start_date=start_date, end_date=end_date)
            title = f"Conversaciones del {start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')}"
        except (ValueError, TypeError):
            return Response(
                {'success': False, 'message': 'Formato de fecha inválido. Use YYYY-MM-DD'},
                status=400
            )
    
    elif period == 'all':
        conversations = _get_conversations_for_range()
        title = "Todas las Conversaciones"
    
    else:
        return Response(
            {'success': False, 'message': f'Período no válido: {period}'},
            status=400
        )
    
    pdf_buffer = generate_chat_pdf(conversations, title)
    
    # Nombre de archivo descriptivo
    filename = f"perla_chat_{period}_{date.today().strftime('%Y%m%d')}.pdf"
    
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@api_view(['GET'])
@require_admin_api_key
def admin_export_stats_pdf(request):
    """
    GET /api/admin/export/stats/pdf/?period=today|week|month|year|range&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    Header: X-Admin-API-Key: <admin_key>
    """
    period = request.GET.get('period', 'week')
    
    if period == 'today':
        stats = TokenMonitor.get_daily_stats()
        title = f"Estadísticas del Día - {date.today().strftime('%d/%m/%Y')}"
    elif period == 'week':
        stats = TokenMonitor.get_weekly_stats()
        title = "Estadísticas de la Semana"
    elif period == 'month':
        stats = TokenMonitor.get_monthly_stats()
        title = f"Estadísticas del Mes - {date.today().strftime('%B %Y')}"
    elif period == 'year':
        stats = TokenMonitor.get_yearly_stats()
        title = f"Estadísticas del Año {date.today().year}"
    elif period == 'range':
        start_str = request.GET.get('start_date', '')
        end_str = request.GET.get('end_date', '')
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            stats = TokenMonitor.get_range_stats(start_date, end_date)
            title = f"Estadísticas del {start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')}"
        except (ValueError, TypeError):
            return Response({'success': False, 'message': 'Formato de fecha inválido'}, status=400)
    else:
        return Response({'success': False, 'message': 'Período no válido'}, status=400)
    
    pdf_buffer = generate_stats_pdf(stats, title)
    filename = f"perla_stats_{period}_{date.today().strftime('%Y%m%d')}.pdf"
    
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@api_view(['GET'])
@require_admin_api_key
def admin_list_conversations(request):
    """
    GET /api/admin/conversations/?period=today&limit=50
    """
    period = request.GET.get('period', 'today')
    limit = int(request.GET.get('limit', 50))
    
    if period == 'today':
        conversations = ConversationLog.objects.filter(started_at__date=date.today())
    elif period == 'week':
        conversations = ConversationLog.objects.filter(started_at__date__gte=date.today() - timedelta(days=7))
    elif period == 'all':
        conversations = ConversationLog.objects.all()
    else:
        conversations = ConversationLog.objects.filter(started_at__date=date.today())
    
    conversations = conversations.order_by('-started_at')[:limit]
    
    data = [{
        'session_id': conv.session_id,
        'started_at': conv.started_at,
        'total_messages': conv.total_messages,
        'preview': conv.messages.first().content[:100] if conv.messages.exists() else ''
    } for conv in conversations]
    
    return Response({'success': True, 'count': len(data), 'data': data})

@api_view(['GET'])
@require_admin_api_key
def admin_conversation_detail(request, session_id):
    """
    GET /api/admin/conversations/<session_id>/
    """
    try:
        conv = ConversationLog.objects.prefetch_related('messages').get(session_id=session_id)
        messages = [{
            'role': msg.role,
            'content': msg.content,
            'timestamp': msg.timestamp,
            'confidence': msg.confidence_score,
            'needs_human': msg.needs_human
        } for msg in conv.messages.all()]
        
        return Response({
            'success': True,
            'data': {
                'session_id': conv.session_id,
                'started_at': conv.started_at,
                'total_messages': conv.total_messages,
                'messages': messages
            }
        })
    except ConversationLog.DoesNotExist:
        return Response({'success': False, 'message': 'Conversación no encontrada'}, status=404)