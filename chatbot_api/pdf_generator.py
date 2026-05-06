from io import BytesIO
from datetime import date, timedelta, datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm
from django.utils import timezone
from .models import ConversationLog

def _get_conversations_for_range(start_date=None, end_date=None, specific_date=None):
    """
    Obtiene conversaciones filtradas por fecha.
    
    Args:
        start_date: Fecha inicio (date)
        end_date: Fecha fin (date)
        specific_date: Día específico (date)
    
    Returns:
        QuerySet de ConversationLog
    """
    conversations = ConversationLog.objects.prefetch_related('messages').all()
    
    if specific_date:
        conversations = conversations.filter(
            started_at__date=specific_date
        )
    elif start_date and end_date:
        conversations = conversations.filter(
            started_at__date__gte=start_date,
            started_at__date__lte=end_date
        )
    elif start_date:
        conversations = conversations.filter(started_at__date__gte=start_date)
    elif end_date:
        conversations = conversations.filter(started_at__date__lte=end_date)
    
    return conversations.order_by('-started_at')


def generate_chat_pdf(conversations, title="Registro de Conversaciones"):
    """
    Genera un PDF profesional con las conversaciones.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm,
        leftMargin=1.5*cm,
        rightMargin=1.5*cm
    )
    
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=10,
        textColor=colors.HexColor('#1a1a2e'),
        alignment=1  # Centrado
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=1
    )
    
    conv_header_style = ParagraphStyle(
        'ConvHeader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        spaceBefore=10,
        spaceAfter=5,
        fontName='Helvetica-Bold'
    )
    
    user_style = ParagraphStyle(
        'UserMsg',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=15,
        textColor=colors.HexColor('#0066cc'),
        spaceBefore=2,
        spaceAfter=4
    )
    
    bot_style = ParagraphStyle(
        'BotMsg',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=15,
        textColor=colors.HexColor('#333333'),
        spaceBefore=2,
        spaceAfter=4
    )
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.grey,
        alignment=1
    )
    
    elements = []
    
    # Título principal
    elements.append(Paragraph("PERLA SOLUTIONS", ParagraphStyle(
        'MainTitle', parent=title_style, fontSize=20, textColor=colors.HexColor('#0f3460')
    )))
    elements.append(Paragraph(title, title_style))
    
    # Info del reporte
    now = timezone.now()
    elements.append(Paragraph(
        f"Generado: {now.strftime('%d/%m/%Y %H:%M')} | "
        f"Total conversaciones: {conversations.count()}",
        subtitle_style
    ))
    elements.append(Spacer(1, 15))
    
    if not conversations.exists():
        elements.append(Paragraph(
            "No se encontraron conversaciones en el período seleccionado.",
            ParagraphStyle('Empty', parent=styles['Normal'], alignment=1)
        ))
    else:
        # Por cada conversación
        for i, conv in enumerate(conversations, 1):
            # Encabezado de conversación
            conv_header_text = (
                f"CONVERSACIÓN #{i} | "
                f"Sesión: {conv.session_id[:12]}... | "
                f"Inicio: {conv.started_at.strftime('%d/%m/%Y %H:%M')} | "
                f"Mensajes: {conv.total_messages}"
            )
            elements.append(Paragraph(conv_header_text, conv_header_style))
            
            # Línea separadora
            elements.append(Paragraph(
                "<hr width='100%' color='#e0e0e0' size='0.5'/>",
                styles['Normal']
            ))
            
            # Mensajes
            messages = conv.messages.all()[:50]  # Máximo 50 por conversación
            for msg in messages:
                role_label = "👤 USUARIO" if msg.role == 'user' else "🤖 PERLA BOT"
                
                if msg.role == 'user':
                    msg_text = f"<b>{role_label}:</b> {msg.content[:300]}"
                    elements.append(Paragraph(msg_text, user_style))
                else:
                    confidence_info = ""
                    if msg.confidence_score is not None:
                        confidence_pct = msg.confidence_score * 100
                        confidence_info = f" | <i>Confianza: {confidence_pct:.0f}%</i>"
                        if msg.needs_human:
                            confidence_info += " | ⚠️ Requiere humano"
                    
                    msg_text = f"<b>{role_label}:</b> {msg.content[:300]}{confidence_info}"
                    elements.append(Paragraph(msg_text, bot_style))
            
            # Separador entre conversaciones
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                "<hr width='100%' color='#1a1a2e' size='1'/>",
                styles['Normal']
            ))
            elements.append(Spacer(1, 8))
            
            # Salto de página cada 3 conversaciones
            if i % 3 == 0 and i < conversations.count():
                elements.append(Spacer(1, 20))
    
    # Footer
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        f"Perla Solutions - Chatbot Logs - {now.strftime('%d/%m/%Y')} - "
        f"Este documento es confidencial",
        footer_style
    ))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_stats_pdf(stats, title="Estadísticas de Uso del Chatbot"):
    """
    Genera un PDF con estadísticas de uso.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    elements = []
    
    # Título
    elements.append(Paragraph("PERLA SOLUTIONS", ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0f3460'),
        alignment=1
    )))
    elements.append(Paragraph(title, ParagraphStyle(
        'SubTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a1a2e'),
        alignment=1,
        spaceAfter=20
    )))
    
    # Resumen general
    elements.append(Paragraph("RESUMEN GENERAL", ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#0f3460'),
        spaceBefore=10,
        spaceAfter=10
    )))
    
    summary_data = [
        ['Métrica', 'Valor'],
        ['Período', f"{stats.get('start_date', 'N/A')} → {stats.get('end_date', 'N/A')}"],
        ['Total Requests', str(stats.get('total_requests', 0))],
        ['Total Respuestas Bot', str(stats.get('total_bot_responses', 0))],
        ['Tokens Estimados', f"{stats.get('total_tokens', 0):,}"],
        ['Palabras Generadas', f"{stats.get('total_words', 0):,}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[5*cm, 10*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f3460')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # Desglose diario
    if 'daily_breakdown' in stats and stats['daily_breakdown']:
        elements.append(Paragraph("DESGLOSE DIARIO", ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#0f3460'),
            spaceBefore=10,
            spaceAfter=10
        )))
        
        table_data = [['Fecha', 'Requests', 'Respuestas', 'Tokens Est.', 'Palabras', 'Confianza']]
        
        for day in stats['daily_breakdown']:
            table_data.append([
                day['date'],
                str(day['requests']),
                str(day.get('bot_responses', 0)),
                f"{day['tokens_estimated']:,}",
                f"{day['words_generated']:,}",
                f"{day.get('avg_confidence', 0):.1%}"
            ])
        
        daily_table = Table(table_data, colWidths=[2.5*cm, 2*cm, 2*cm, 2.5*cm, 2.5*cm, 2*cm])
        daily_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fafafa')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4ff')]),
        ]))
        elements.append(daily_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer