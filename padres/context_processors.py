from padres.models import Padre
from django.apps import apps


def notificaciones_padre(request):
    if not request.session.get('credenciales_padre'):
        return {}

    try:
        if request.session['credenciales_padre'].get('rol') != 'Padre':
            return {}

        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
        notificaciones_recientes = padre.get_notificaciones()
        notificaciones_no_leidas = request.session.get('notificaciones_padre_no_leidas', 0)
        contador_no_leidas = request.session.get('contador_padre_no_leidas', 0)

        return {
            'notificaciones_recientes': notificaciones_recientes,
            'notificaciones_no_leidas': notificaciones_no_leidas,
            'contador_no_leidas': contador_no_leidas,
            'notificaciones': padre.get_notificaciones()[:5]  # Por ejemplo, las 5 más recientes
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
