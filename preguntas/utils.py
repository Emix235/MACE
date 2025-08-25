from django.shortcuts import get_object_or_404
from padres.models import Padre
from profesores.models import Profesor
from servicios_escolares.models import ServicioEscolar


def get_user_role_and_base(request):
    """
    Obtiene el usuario actual, su rol y la plantilla base correspondiente.
    Devuelve (user, role, base_template) o (None, None, redirect) si no está autenticado.
    """
    user = None
    role = None
    base_template = None

    if 'credenciales_padre' in request.session:
        user = get_object_or_404(Padre, id=request.session['credenciales_padre']['id'])
        role = 'padre'
        base_template = 'padres/base.html'
    elif 'credenciales_profesor' in request.session:
        user = get_object_or_404(Profesor, id=request.session['credenciales_profesor']['id'])
        role = 'profesor'
        base_template = 'profesores/base.html'
    elif 'credenciales' in request.session:
        user = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])
        role = 'servicio'
        base_template = 'servicios_escolares/base.html'
    else:
        return None, None, None

    return user, role, base_template, None
