from profesores.models import Profesor
from django.apps import apps
from django.contrib.contenttypes.models import ContentType


def notificaciones_profesor(request):
    if not request.session.get('credenciales_profesor'):
        return {}

    try:
        if request.session['credenciales_profesor'].get('rol') != 'Profesor':
            return {}

        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        notificaciones_recientes = profesor.get_notificaciones(limit=10)
        notificaciones_no_leidas = request.session.get('notificaciones_no_leidas', 0)
        contador_no_leidas = request.session.get('contador_no_leidas', 0)
        # notificaciones_no_leidas = profesor.notificaciones.filter(is_read=False).count()

        return {
            'notificaciones_recientes': notificaciones_recientes,
            'notificaciones_no_leidas': notificaciones_no_leidas,
            'contador_no_leidas': contador_no_leidas,
        }

    except Profesor.DoesNotExist:
        return {}
    except Exception as e:
        print(f"Error en context processor notificaciones: {str(e)}")
        return {}


# Context processor específico para Profesores
def profesor_context(request):
    context = {}
    if hasattr(request, 'user_obj') and request.user_obj.__class__.__name__ == 'Profesor':
        context.update({
            'es_profesor': True,
            'profesor': request.user_obj,
            'can_change_theme': apps.get_model('servicios_escolares.ThemeConfig')
            .objects.first()
            .allow_profesors if hasattr(request, 'user_obj') else False
        })
    return context
