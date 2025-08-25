# notificaciones/templatetags/notificaciones_tags.py
from django import template

register = template.Library()


@register.filter
def icono_tipo_notificacion(event_type):
    """Asigna iconos de Bootstrap Icons según el tipo de notificación"""
    icon_map = {
        # Registros
        'registro_padre': 'person-plus',
        'servicio_nuevo_padre': 'person-plus',

        # Citas
        'padre_cita_creada': 'calendar-plus',
        'padre_cita_modificada': 'calendar-week',
        'padre_cita_cancelada': 'calendar-x',
        'profesor_cita_creada': 'calendar-plus',
        'profesor_cita_proxima': 'calendar-event',

        # Tickets
        'servicio_ticket': 'ticket-detailed',
        'respuesta_ticket': 'reply',

        # Feedback
        'padre_feedback_pendiente': 'chat-left-dots',
        'padre_feedback_recibido': 'chat-left-check',
        'profesor_feedback_pendiente': 'chat-left-dots',

        # Académico
        'padre_calificacion': 'journal-check',
        'padre_incidencia': 'exclamation-triangle',
        'profesor_incidencia': 'exclamation-triangle',

        # General
        'recordatorio_general': 'bell',
        'custom': 'gear'
    }

    icon_class = icon_map.get(event_type, 'bell')
    return f'bi-{icon_class}'

# feedback_pendiente
# feedback_recibido
