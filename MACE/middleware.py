# tu_proyecto/middleware.py
# Este archivo va en la misma carpeta que settings.py

from django.shortcuts import redirect
from django.contrib import messages

class DemoModeMiddleware:
    """
    Middleware para manejar modo demo sin modificar vistas
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        """Método obligatorio - procesa cada request"""
        
        # Detectar modo demo desde GET o POST
        is_demo = (
            request.GET.get('modo') == 'demo' or 
            request.GET.get('tutorial') == 'true'
        )
        
        # Guardar flag en request para usar en otros lugares
        request.is_demo_mode = is_demo
        
        # Interceptar POST en modo demo
        if is_demo and request.method == 'POST':
            print(f"🔒 [DEMO] Interceptando POST a: {request.path}")
            
            # Simular mensaje de éxito
            messages.success(request, '✅ MODO DEMO: Operación simulada exitosamente (no se guardó en BD)')
            
            # Redirigir a la página anterior o al dashboard
            next_url = request.META.get('HTTP_REFERER', '/')
            
            # Mantener el flag demo en la redirección
            if 'modo=demo' not in next_url and 'tutorial' not in next_url:
                separator = '&' if '?' in next_url else '?'
                next_url = f"{next_url}{separator}modo=demo"
            
            return redirect(next_url)
        
        # Si no es POST o no es demo, continuar normalmente
        response = self.get_response(request)
        
        # Agregar header para informar al frontend
        if is_demo:
            response['X-Demo-Mode'] = 'true'
        
        return response


# Context processor para templates (mismo archivo)
def demo_context_processor(request):
    """
    Agrega variables de demo a TODOS los templates
    """
    is_demo = (
        request.GET.get('modo') == 'demo' or 
        request.GET.get('tutorial') == 'true'
    )
    
    return {
        'is_demo_mode': is_demo,
        'demo_active': is_demo,
        'demo_banner': '🔒 MODO DEMO - Datos de ejemplo' if is_demo else '',
        'demo_param': '?modo=demo' if is_demo else '',
    }