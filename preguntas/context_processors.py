# preguntas/context_processors.py
from .utils import get_user_role_and_base, get_user_role_display


def faq_context(request):
    """Agrega variables de FAQ a TODOS los templates automáticamente"""
    if request.user.is_authenticated or any(key in request.session for key in ['credenciales', 'credenciales_padre', 'credenciales_profesor']):
        user, role, base_template, _ = get_user_role_and_base(request)
        if role:
            return {
                'rol_actual': role,
                'rol_display': get_user_role_display(role),
            }
    return {
        'rol_actual': None,
        'rol_display': 'Usuario',
    }

