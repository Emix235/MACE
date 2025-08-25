from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from padres.models import Padre
from profesores.models import Profesor
from servicios_escolares.models import ServicioEscolar
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

    if request.session.get('credenciales_padre'):
        user = get_object_or_404(Padre, id=request.session['credenciales_padre']['id'])
        role = 'padre'
        base_template = 'padres/base.html'

        # Determinar el tema activo
        personal_theme = getattr(user, 'personal_theme', None)
        active_theme = personal_theme if personal_theme else global_theme

        extra_context.update({
            'es_padre': True,
            'padre': user,
            'can_change_theme': theme_config.allow_padres if theme_config else False,
            'active_theme': active_theme,
            'personal_theme': personal_theme
        })

    elif request.session.get('credenciales_profesor'):
        user = get_object_or_404(Profesor, id=request.session['credenciales_profesor']['id'])
        role = 'profesor'
        base_template = 'profesores/base.html'

        personal_theme = getattr(user, 'personal_theme', None)
        active_theme = personal_theme if personal_theme else global_theme

        extra_context.update({
            'es_profesor': True,
            'profesor': user,
            'can_change_theme': theme_config.allow_profesors if theme_config else False,
            'active_theme': active_theme,
            'personal_theme': personal_theme
        })

    elif request.session.get('credenciales'):
        user = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])
        role = 'servicio'
        base_template = 'servicios_escolares/base.html'

        extra_context.update({
            'es_servicio': True,
            'servicio': user,
            'can_change_theme': True,
            'active_theme': global_theme
        })
    else:
        messages.warning(request, 'Debes iniciar sesión primero')
        return None, None, None, redirect('padres:login_padre')

    return user, role, base_template, None, extra_context
