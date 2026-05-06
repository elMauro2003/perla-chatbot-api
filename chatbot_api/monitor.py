from datetime import date, timedelta
from .models import DailyUsage

class TokenMonitor:
    """
    Monitorea el uso estimado de tokens.
    """
    
    # Estimaciones
    TOKENS_PER_REQUEST = 4000   # System prompt + contexto
    TOKENS_PER_RESPONSE = 800   # Promedio de tokens por respuesta
    MAX_FREE_DAILY_TOKENS = 100000  # Estimado del límite gratuito
    
    @classmethod
    def get_daily_stats(cls, target_date=None):
        """Estadísticas de un día específico (hoy por defecto)"""
        if target_date is None:
            target_date = date.today()
        
        daily, created = DailyUsage.objects.get_or_create(date=target_date)
        
        tokens_used = (daily.total_requests * cls.TOKENS_PER_REQUEST) + \
                      (daily.total_bot_responses * cls.TOKENS_PER_RESPONSE)
        
        tokens_remaining = max(0, cls.MAX_FREE_DAILY_TOKENS - tokens_used)
        
        return {
            'date': str(target_date),
            'requests_today': daily.total_requests,
            'user_messages': daily.total_user_messages,
            'bot_responses': daily.total_bot_responses,
            'tokens_used_estimate': tokens_used,
            'tokens_remaining_estimate': tokens_remaining,
            'tokens_limit': cls.MAX_FREE_DAILY_TOKENS,
            'usage_percent': round((tokens_used / cls.MAX_FREE_DAILY_TOKENS) * 100, 1),
            'avg_confidence': round(daily.avg_confidence, 2),
            'human_escalations': daily.human_escalations,
            'words_generated_today': daily.total_words_generated,
        }
    
    @classmethod
    def get_range_stats(cls, start_date, end_date):
        """Estadísticas para un rango de fechas"""
        daily_stats = DailyUsage.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('-date')
        
        total_requests = 0
        total_bot_responses = 0
        total_tokens = 0
        total_words = 0
        daily_breakdown = []
        
        for day in daily_stats:
            tokens = (day.total_requests * cls.TOKENS_PER_REQUEST) + \
                     (day.total_bot_responses * cls.TOKENS_PER_RESPONSE)
            total_requests += day.total_requests
            total_bot_responses += day.total_bot_responses
            total_tokens += tokens
            total_words += day.total_words_generated
            
            daily_breakdown.append({
                'date': str(day.date),
                'requests': day.total_requests,
                'bot_responses': day.total_bot_responses,
                'tokens_estimated': tokens,
                'words_generated': day.total_words_generated,
                'avg_confidence': round(day.avg_confidence, 2),
                'human_escalations': day.human_escalations,
            })
        
        return {
            'start_date': str(start_date),
            'end_date': str(end_date),
            'total_requests': total_requests,
            'total_bot_responses': total_bot_responses,
            'total_tokens': total_tokens,
            'total_words': total_words,
            'daily_breakdown': daily_breakdown,
        }
    
    @classmethod
    def get_weekly_stats(cls):
        """Últimos 7 días"""
        today = date.today()
        week_ago = today - timedelta(days=6)
        return cls.get_range_stats(week_ago, today)
    
    @classmethod
    def get_monthly_stats(cls):
        """Mes actual"""
        today = date.today()
        month_start = today.replace(day=1)
        return cls.get_range_stats(month_start, today)
    
    @classmethod
    def get_yearly_stats(cls):
        """Año actual"""
        today = date.today()
        year_start = today.replace(month=1, day=1)
        return cls.get_range_stats(year_start, today)