from padres.models import Padre
from django.apps import apps


def notificaciones_padre(request):
    if not request.session.get('credenciales_padre'):
        return {}

    try:
        if request.session['credenciales_padre'].get('rol') != 'Padre':
            return {}

        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
        
        # CAMBIO PRINCIPAL: Usar filter en lugar de get_notificaciones() para tener control
        # Obtener SOLO las no leídas (son las que interesan en el dropdown)
        notificaciones_no_leidas = padre.notificaciones_no_leidas()  # Esto ya filtra is_read=False
        
        # Si quieres mostrar las últimas 50 en lugar de todas (por rendimiento)
        # notificaciones_recientes = notificaciones_no_leidas[:50]
        
        # O si quieres TODAS las no leídas (recomendado)
        notificaciones_recientes = notificaciones_no_leidas
        
        contador_no_leidas = notificaciones_no_leidas.count()

        return {
            'notificaciones_recientes': notificaciones_recientes,
            'notificaciones_no_leidas': contador_no_leidas,
            'contador_no_leidas': contador_no_leidas,
            'notificaciones': notificaciones_recientes,  # Todas las no leídas
            'todas_notificaciones': padre.get_notificaciones(),  # Todas (leídas y no leídas)
        }
    except Padre.DoesNotExist:
        return {}
    except Exception as e:
        print(f"Error en context processor notificaciones padre: {str(e)}")
        return {}


# Context processor específico para Padres
def padre_context(request):
    context = {}
    if hasattr(request, 'user_obj') and request.user_obj.__class__.__name__ == 'Padre':
        context.update({
            'es_padre': True,
            'padre': request.user_obj,
            'can_change_theme': apps.get_model('servicios_escolares.ThemeConfig')
            .objects.first()
            .allow_padres if hasattr(request, 'user_obj') else False
        })
    return context
