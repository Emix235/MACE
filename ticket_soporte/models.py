from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from notificaciones.models import Notification  # Asegúrate de importar correctamente


class TicketSoporte(models.Model):
    ESTADOS_TICKET = [
        ('abierto', 'Abierto'),
        ('en_progreso', 'En progreso'),
        ('cerrado', 'Cerrado')
    ]

    TIPO_USUARIO_CHOICES = [
        ('padre', 'Padre'),
        ('profesor', 'Profesor'),
        ('servicio_escolar', 'Servicio Escolar')
    ]

    tipo_usuario = models.CharField(max_length=20, choices=TIPO_USUARIO_CHOICES)
    usuario_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    usuario_id = models.PositiveIntegerField()
    usuario = GenericForeignKey('usuario_ct', 'usuario_id')

    asunto = models.CharField(max_length=200)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADOS_TICKET, default='abierto')

    # Nuevo campo para la URL de la página donde ocurrió el problema
    url_pagina = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="URL de la página donde ocurrió el problema (opcional)"
    )

    # Campo para capturar información adicional del navegador
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Información del navegador del usuario"
    )

    asignado_a = models.ForeignKey(
        'servicios_escolares.ServicioEscolar',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='tickets_asignados'
    )

    respuesta = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"Ticket #{self.id} - {self.asunto}"


def notificar_creacion_ticket(self):

    # Notificar al servicio escolar
    if self.asignado_a:
        Notification.crear_notificacion(
            event_type='servicio_ticket_asignado',
            recipient=self.asignado_a,
            target=self,
            message=f"Nuevo ticket asignado: {self.asunto}",
            variable_1=self.url_pagina  # Pasamos la URL como variable
        )
    else:
        # Notificar a todos los miembros del servicio escolar que puedan recibir tickets
        servicio_escolar_ct = ContentType.objects.get(app_label='servicios_escolares', model='servicioescolar')
        for miembro in servicio_escolar_ct.model_class().objects.filter(recibe_tickets=True):
            Notification.crear_notificacion(
                event_type='servicio_ticket',
                recipient=miembro,
                target=self,
                message=f"Nuevo ticket de soporte creado: {self.asunto}",
                variable_1=self.url_pagina
            )
