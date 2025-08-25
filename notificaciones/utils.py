# utils.py (filtros personalizados)
from django import template
from django.contrib.contenttypes.models import ContentType
from servicios_escolares.models import ServicioEscolar
from .models import Notification


register = template.Library()

@register.filter
def icono_tipo_notificacion(event_type):
    iconos = {
        'cita_creada': 'fa-calendar-plus',
        'cita_modificada': 'fa-calendar-week',
        'cita_cancelada': 'fa-calendar-times',
        'feedback_pendiente': 'fa-comment-dots',
        'feedback_recibido': 'fa-comment-check',
        'nuevo_ticket': 'fa-ticket-alt',
        'respuesta_ticket': 'fa-reply',
        'calificacion_actualizada': 'fa-chart-line',
        'incidencia_academica': 'fa-exclamation-triangle',
        'recordatorio_general': 'fa-bell',
        'custom': 'fa-wrench'
    }
    return iconos.get(event_type, 'fa-bell')


def notificar_registro_padre(padre, estudiante):
    """Notifica a todos los servicios escolares sobre un nuevo registro de padre"""
    servicio_escolar_ct = ContentType.objects.get_for_model(ServicioEscolar)

    for servicio in ServicioEscolar.objects.all():
        Notification.objects.create(
            recipient_ct=servicio_escolar_ct,
            recipient_id=servicio.id,
            event_type='registro_padre',
            title='Nuevo padre registrado',
            message=f'El padre {padre.nombre_completo} se ha registrado para el estudiante {estudiante.nombre_completo}',
            variable_1=padre.nombre_completo,
            variable_2=estudiante.nombre_completo,
            variable_3=padre.fecha_registro.strftime('%d/%m/%Y')
        )

