# views.py
from django.shortcuts import redirect
from django.conf import settings
from .google_calendar_utils import get_google_auth_flow, save_google_tokens
from padres.models import Padre
from profesores.models import Profesor
from servicios_escolares.models import ServicioEscolar


def google_auth(request):
    flow = get_google_auth_flow(request)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
    )
    request.session['google_auth_state'] = state
    request.session['google_auth_role'] = request.GET.get('role')  # 'padre', 'profesor', 'servicio'
    return redirect(authorization_url)


def google_auth_callback(request):
    state = request.session.pop('google_auth_state', None)
    role = request.session.pop('google_auth_role', None)

    flow = get_google_auth_flow(request)
    flow.fetch_token(authorization_response=request.build_absolute_uri())

    credentials = flow.credentials
    tokens = {
        'access_token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'expires_in': credentials.expires_in,
    }

    # Guardar tokens según el tipo de usuario
    user_id = request.session.get(f'credenciales_{role}')['id']
    if role == 'padre':
        save_google_tokens(Padre, user_id, tokens)
    elif role == 'profesor':
        save_google_tokens(Profesor, user_id, tokens)
    elif role == 'servicio':
        save_google_tokens(ServicioEscolar, user_id, tokens)

    return redirect('padres:login_padre')  # Redirige a donde necesites


# views.py
def sync_appointment(request, appointment_id):
    role = None
    if 'credenciales_padre' in request.session:
        role = 'padre'
    elif 'credenciales_profesor' in request.session:
        role = 'profesor'
    elif 'credenciales' in request.session:
        role = 'servicio'

    if not role:
        return redirect('servicios_escolares:login')

    # Obtener datos de la cita (ajusta según tu modelo)
    appointment = CitaEscolar.objects.get(id=appointment_id)
    event_data = {
        'summary': f'Cita: {appointment.titulo}',
        'location': appointment.ubicacion,
        'start': {'dateTime': appointment.fecha_inicio.isoformat()},
        'end': {'dateTime': appointment.fecha_fin.isoformat()},
        'description': appointment.descripcion,
    }

    user_id = request.session[f'credenciales_{role}']['id']
    if role == 'padre':
        create_google_calendar_event(Padre, user_id, event_data)
    elif role == 'profesor':
        create_google_calendar_event(Profesor, user_id, event_data)
    elif role == 'servicio':
        create_google_calendar_event(ServicioEscolar, user_id, event_data)

    return redirect('citas')  # Redirige después de sincronizar
