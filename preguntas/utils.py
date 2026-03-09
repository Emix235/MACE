import traceback

from django.shortcuts import get_object_or_404
from padres.models import Padre
from profesores.models import Profesor
from servicios_escolares.models import ServicioEscolar
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect


def get_user_role_and_base(request):
    """Obtiene el usuario actual, su rol y la plantilla base correspondiente."""
    print(f"\n[UTILS DEBUG] get_user_role_and_base llamado")
    print(f"[UTILS DEBUG] Sesión: {dict(request.session)}")

    user = None
    role = None
    base_template = None
    redirect_response = None

    try:
        if 'credenciales_padre' in request.session:
            print(f"[UTILS DEBUG] Detectado padre: {request.session['credenciales_padre']}")
            user = get_object_or_404(Padre, id=request.session['credenciales_padre']['id'])
            role = 'padre'
            base_template = 'padres/base.html'

        elif 'credenciales_profesor' in request.session:
            print(f"[UTILS DEBUG] Detectado profesor: {request.session['credenciales_profesor']}")
            user = get_object_or_404(Profesor, id=request.session['credenciales_profesor']['id'])
            role = 'profesor'
            base_template = 'profesores/base.html'

        elif 'credenciales' in request.session:
            print(f"[UTILS DEBUG] Detectado servicio: {request.session['credenciales']}")
            user = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])
            role = 'servicio'
            base_template = 'servicios_escolares/base.html'

        else:
            print("[UTILS DEBUG] No hay sesión activa")
            return None, None, None, None

        print(f"[UTILS DEBUG] Usuario encontrado: {user}")
        print(f"[UTILS DEBUG] Rol: {role}")
        print(f"[UTILS DEBUG] Tipo usuario: {type(user)}")

        return user, role, base_template, None

    except Exception as e:
        print(f"[UTILS DEBUG] ERROR: {e}")
        traceback.print_exc()
        return None, None, None, None


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
