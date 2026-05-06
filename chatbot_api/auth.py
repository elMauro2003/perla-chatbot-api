import os
from functools import wraps
from django.http import JsonResponse

# API Key para endpoints administrativos
ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'perla-admin-secret-key-2024')

def require_admin_api_key(view_func):
    """
    Decorador que requiere API Key para acceder a endpoints administrativos.
    Uso: @require_admin_api_key
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        api_key = request.headers.get('X-Admin-API-Key', '')
        
        if not api_key:
            return JsonResponse({
                'success': False,
                'message': 'Acceso denegado. Se requiere API Key administrativa.',
                'error': 'missing_admin_key'
            }, status=401)
        
        if api_key != ADMIN_API_KEY:
            return JsonResponse({
                'success': False,
                'message': 'API Key administrativa inválida.',
                'error': 'invalid_admin_key'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper