# preguntas/context_processors.py
from .utils import get_user_role_and_base, get_user_role_display


def faq_context(request):
    if any(key in request.session for key in ['credenciales', 'credenciales_padre', 'credenciales_profesor']):
        user, role, base_template, _, extra_context = get_user_role_and_base(request)

        print("[DEBUG] extra_context:", extra_context)
        print("[DEBUG] active_theme:", extra_context.get('active_theme'))

        if role:
            return {
                'rol_actual': role,
                'rol_display': get_user_role_display(role),
                **extra_context   # 🔥 IMPORTANTE
            }

    return {
        'rol_actual': None,
        'rol_display': 'Usuario',
    }

