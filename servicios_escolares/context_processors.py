# servicios_escolares/context_processors.py
import json

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from citas.models import Cita
from profesores.models import Profesor
from servicios_escolares.models import ServicioEscolar
from django.db.models import Q
from django.utils.timezone import localtime


def theme_context(request):
    default_theme = 'css/themes/default.css'
    theme_config = apps.get_model('servicios_escolares.ThemeConfig').objects.first()

    # Tema base (global o default)
    active_theme = theme_config.global_theme if theme_config else default_theme

    # Verificar tema personal si el usuario está autenticado
    if hasattr(request, 'user_obj') and request.user_obj:
        user_model = request.user_obj.__class__.__name__

        # Solo aplicar tema personal si no es Servicio Escolar
        if user_model in ['Profesor', 'Padre'] and hasattr(request.user_obj, 'personal_theme'):
            active_theme = request.user_obj.personal_theme or active_theme

    # Determinar si puede cambiar el tema
    can_change = False
    if hasattr(request, 'user_obj') and request.user_obj:
        if theme_config:
            user_model = request.user_obj.__class__.__name__
            if user_model == 'ServicioEscolar':
                can_change = True
            elif user_model == 'Profesor' and theme_config.allow_profesors:
                can_change = True
            elif user_model == 'Padre' and theme_config.allow_padres:
                can_change = True

    return {
        'active_theme': active_theme,
        'can_change_theme': can_change
    }


def eventos_servicio_escolar(request):
    usuario = getattr(request, 'user_obj', None)  # <-- Cambiado aquí
    eventos = []

    if usuario and usuario.__class__.__name__ == 'ServicioEscolar':
        servicio_ct = ContentType.objects.get_for_model(ServicioEscolar)
        profesor_ct = ContentType.objects.get_for_model(Profesor)

        estado = request.GET.get('estado')

        citas_creadas = Cita.objects.filter(
            creador_tipo=servicio_ct,
            creador_id=usuario.id
        )
        citas_como_agendador = Cita.objects.filter(
            servicio_escolar=usuario
        )
        citas_como_asistente = Cita.objects.filter(
            asistentes_servicio=usuario
        ).exclude(
            Q(creador_tipo=servicio_ct, creador_id=usuario.id) |
            Q(servicio_escolar=usuario)
        )
        citas_solicitadas_por_padres = Cita.objects.filter(
            solicitante__isnull=False,
            asistentes_servicio=usuario
        ).exclude(
            creador_tipo=servicio_ct
        )
        citas_de_profesores = Cita.objects.filter(
            creador_tipo=profesor_ct,
            asistentes_servicio=usuario
        )

        if estado and estado in dict(Cita.ESTADOS):
            citas_creadas = citas_creadas.filter(estado=estado)
            citas_como_agendador = citas_como_agendador.filter(estado=estado)
            citas_como_asistente = citas_como_asistente.filter(estado=estado)
            citas_solicitadas_por_padres = citas_solicitadas_por_padres.filter(estado=estado)
            citas_de_profesores = citas_de_profesores.filter(estado=estado)

        todas = (
                list(citas_creadas) +
                list(citas_como_agendador) +
                list(citas_como_asistente) +
                list(citas_solicitadas_por_padres) +
                list(citas_de_profesores)
        )

        citas_unicas = list({cita.id: cita for cita in todas}.values())

        for cita in citas_unicas:
            eventos.append({
                'id': cita.id,
                'title': cita.titulo,
                'start': localtime(cita.fecha_hora_inicio).isoformat(),
                'end': localtime(cita.fecha_hora_fin).isoformat(),
                'backgroundColor': estado_color(cita.estado),
                'borderColor': estado_color(cita.estado),
                'textColor': 'white',
                'extendedProps': {
                    'estado': cita.get_estado_display(),
                    'tipo': cita.get_tipo_display(),
                    'descripcion': cita.motivo,
                    'ubicacion': cita.ubicacion,
                    'solicitante': str(cita.solicitante),
                    'estudiantes': cita.estudiantes_list()
                }
            })

    return {
        'eventos_servicio_escolar': json.dumps(eventos)
    }


def estado_color(estado):
    colores = {
        'pendiente': '#f1c40f',  # amarillo
        'confirmada': '#2ecc71',  # verde
        'completada': '#3498db',  # azul
        'cancelada': '#e74c3c',  # rojo
        'reprogramada': '#e67e22',  # naranja
    }
    return colores.get(estado, '#95a5a6')  # gris por defecto
