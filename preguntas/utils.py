import traceback

from django.shortcuts import get_object_or_404
from padres.models import Padre
from profesores.models import Profesor
from servicios_escolares.models import ServicioEscolar
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect


from django.apps import apps

def get_user_role_and_base(request):
    user = None
    role = None
    base_template = None
    extra_context = {}

    ThemeConfig = apps.get_model('servicios_escolares.ThemeConfig')
    theme_config = ThemeConfig.objects.first()

    default_theme = 'css/themes/default.css'
    global_theme = theme_config.global_theme if theme_config else default_theme

    if 'credenciales_padre' in request.session:
        user = get_object_or_404(Padre, id=request.session['credenciales_padre']['id'])
        role = 'padre'
        base_template = 'padres/base.html'

        personal_theme = getattr(user, 'personal_theme', None)
        active_theme = personal_theme if personal_theme else global_theme

        extra_context.update({
            'active_theme': active_theme
        })

    elif 'credenciales_profesor' in request.session:
        user = get_object_or_404(Profesor, id=request.session['credenciales_profesor']['id'])
        role = 'profesor'
        base_template = 'profesores/base.html'

        personal_theme = getattr(user, 'personal_theme', None)
        active_theme = personal_theme if personal_theme else global_theme

        extra_context.update({
            'active_theme': active_theme
        })

    elif 'credenciales' in request.session:
        user = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])
        role = 'servicio'
        base_template = 'servicios_escolares/base.html'

        extra_context.update({
            'active_theme': global_theme
        })

    else:
        return None, None, None, None, None

    return user, role, base_template, None, extra_context


def get_user_role_display(role):
    """
    Devuelve el nombre legible del rol
    """
    role_display = {
        'padre': 'Padre/Madre de Familia',
        'profesor': 'Profesor',
        'servicio': 'Servicio Escolar',
        'general': 'General',
    }
    return role_display.get(role, role.capitalize())


def check_role_permission(request, allowed_roles):
    """
    Verifica si el usuario tiene permiso para acceder basado en su rol
    """
    user, role, base_template, redirect_response = get_user_role_and_base(request)

    if redirect_response:
        return None, None, None, redirect_response

    if role not in allowed_roles and 'general' not in allowed_roles:
        messages.error(request, 'No tienes permiso para acceder a esta sección')
        return user, role, base_template, redirect('login')  # Ajusta esto

    return user, role, base_template, None
