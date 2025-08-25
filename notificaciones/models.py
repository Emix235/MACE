from datetime import timezone
from pydoc import resolve

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse, NoReverseMatch
from django.db import models
from servicios_escolares.middleware import logger
from servicios_escolares.models import ServicioEscolar


class Notification(models.Model):
    # Tipos de eventos organizados por rol
    EVENT_TYPES = {
        # Notificaciones para Padres
        'padre_cita_creada': ('padres:mis_citas', 'Nueva cita programada', 'padre'),
        'padre_cita_confirmada': ('citas:cancelar_cita', 'Cita confirmada', 'profesor'),
        'padre_cita_modificada': ('citas:cancelar_cita', 'Cambio en tu cita', 'padre'),
        'padre_cita_cancelada': ('citas:cancelar_cita', 'Cita cancelada', 'padre'),
        'padre_feedback_pendiente': ('feedback:responder', 'Feedback pendiente', 'padre'),
        'padre_feedback_recibido': ('feedback:detalle', 'Respuesta a tu feedback', 'padre'),
        'padre_calificacion': ('academico:detalle_calificacion', 'Nueva calificación', 'padre'),
        'padre_incidencia': ('academico:reportes', 'Incidencia académica', 'padre'),
        'padre_ticket': ('padres:detalle_ticket', 'Nuevo ticket de soporte', 'padre'),
        'servicio_ticket_padre': ('servicios_escolares:detalle_ticket', 'Nuevo ticket de soporte', 'padre'),

        # Notificaciones para Profesores
        'profesor_cita_creada': ('profesores:panel_citas', 'Tienes una nueva cita', 'profesor'),
        'profesor_cita_modificada': ('citas:cancelar_cita', 'Cambio en tu cita', 'profesor'),
        'profesor_cita_cancelada': ('citas:cancelar_cita', 'Cita cancelada', 'profesor'),
        'profesor_feedback_pendiente': ('feedback:responder', 'Feedback pendiente', 'profesor'),
        'profesor_cita_proxima': ('citas:cancelar_cita', 'Recordatorio de cita', 'profesor'),
        'profesor_incidencia': ('academico:reportes', 'Incidencia reportada', 'profesor'),
        'profesor_ticket': ('padres:detalle_ticket', 'Nuevo ticket de soporte', 'profesor'),
        'servicio_ticket_profesor': ('servicios_escolares:todos_tickets', 'Nuevo ticket de soporte', 'padre'),

        # Notificaciones para Servicio Escolar
        'registro_padre': ('servicios_escolares:panel_grupos_padres', 'Nuevo padre registrado', 'servicio'),
        'servicio_nuevo_profesor': ('servicios_escolares:panel-profesores', 'Nuevo profesor registrado', 'servicio'),
        'servicio_ticket': ('servicios_escolares:detalle_ticket', 'Nuevo ticket de soporte', 'servicio'),
        'servicio_cita_confirmada': ('servicios_escolares:detalle_cita', 'Cita confirmada por padre', 'servicio'),
        'servicio_cita_cancelada': ('servicios_escolares:detalle_cita', 'Cita cancelada por el padre', 'servicio'),

        'servicio_ticket_asignado': ('servicios_escolares:detalle_ticket', 'Ticket asignado', 'servicio'),

        # Notificaciones generales
        'recordatorio_general': ('inicio', 'Recordatorio importante', 'todos'),
        'custom': ('notificaciones:detalle', 'Notificación personalizada', 'todos'),
    }

    EVENT_CHOICES = [(key, value[1]) for key, value in EVENT_TYPES.items()]
    ROL_CHOICES = [
        ('padre', 'Padre'),
        ('profesor', 'Profesor'),
        ('servicio', 'Servicio Escolar'),
        ('todos', 'Todos los usuarios')
    ]

    # Emisor (quien envía la notificación)
    sender_ct = models.ForeignKey(
        ContentType,
        related_name='notificaciones_enviadas',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    sender_id = models.PositiveIntegerField(null=True, blank=True)
    sender = GenericForeignKey('sender_ct', 'sender_id')

    # Receptor (quien recibe la notificación)
    recipient_ct = models.ForeignKey(
        ContentType,
        related_name='notificaciones_recibidas',
        on_delete=models.CASCADE
    )
    recipient_id = models.PositiveIntegerField()
    recipient = GenericForeignKey('recipient_ct', 'recipient_id')

    # Contenido
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_CHOICES,
        default='custom'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)  # Corregido aquí
    rol_destinatario = models.CharField(
        max_length=20,
        choices=ROL_CHOICES,
        default='todos'
    )

    # Objeto relacionado (opcional)
    target_ct = models.ForeignKey(
        ContentType,
        related_name='notificaciones_relacionadas',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    target_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey('target_ct', 'target_id')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient_ct', 'recipient_id']),
            models.Index(fields=['sender_ct', 'sender_id']),
            models.Index(fields=['event_type']),
            models.Index(fields=['is_read']),
            models.Index(fields=['created_at']),
            models.Index(fields=['rol_destinatario']),
        ]
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'

    def __str__(self):
        return f"{self.title} para {self.recipient} ({'leída' if self.is_read else 'no leída'})"

    def mark_as_read(self):
        """Marca la notificación como leída"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])

    @property
    def is_unread(self):
        """Indica si la notificación no ha sido leída"""
        return not self.is_read

    @classmethod
    def notificar_nuevo_ticket(cls, ticket, creador):
        """Notifica a los servicios escolares sobre un nuevo ticket"""
        servicios = ServicioEscolar.objects.filter(
            estado_cuenta='Activo',
            recibe_notificaciones=True
        )

        for servicio in servicios:
            cls.crear_notificacion(
                event_type='servicio_ticket',
                sender=creador,
                recipient=servicio,
                target=ticket,
                message=f"Nuevo ticket de {creador.get_tipo_usuario_display()}: {ticket.asunto}"
            )

        # Confirmación al creador (si no es servicio escolar)
        if not isinstance(creador, ServicioEscolar):
            cls.crear_notificacion(
                event_type='custom',
                sender=servicios.first(),  # O el sistema como emisor
                recipient=creador,
                target=ticket,
                title='Ticket creado',
                message=f"Has creado el ticket #{ticket.id}"
            )

    @property
    def is_custom(self):
        return self.event_type == 'custom' or self.template is not None

    @property
    def badge_class(self):
        return 'badge-danger' if not not self.is_read else 'badge-secondary'

    @classmethod
    def crear_notificacion(cls, event_type, recipient, sender=None, target=None, **kwargs):
        """
        Método general para crear notificaciones, con opción de incluir sender y target.
        """
        event_info = cls.EVENT_TYPES.get(event_type, cls.EVENT_TYPES['custom'])

        recipient_ct = ContentType.objects.get_for_model(recipient.__class__)
        recipient_id = recipient.id

        rol = 'servicio' if isinstance(recipient, ServicioEscolar) else (
            event_info[2] if len(event_info) > 2 else 'todos'
        )

        notif = cls(
            recipient_ct=recipient_ct,
            recipient_id=recipient_id,
            event_type=event_type,
            title=kwargs.get('title', event_info[1]),
            message=kwargs.get('message', ''),
            rol_destinatario=rol
        )

        # Opcional: sender
        if sender:
            notif.sender_ct = ContentType.objects.get_for_model(sender.__class__)
            notif.sender_id = sender.id

        # Opcional: target
        if target:
            notif.target_ct = ContentType.objects.get_for_model(target.__class__)
            notif.target_id = target.id

        notif.save()
        return notif

    @classmethod
    def para_rol(cls, rol):
        """Filtra notificaciones para un rol específico"""
        return cls.objects.filter(rol_destinatario__in=[rol, 'todos'])

    @classmethod
    def crear_notificacion_cita(cls, event_type, sender, recipient, **kwargs):
        """Crea una notificación con sender, recipient y target (opcional)."""
        event_info = cls.EVENT_TYPES.get(event_type, cls.EVENT_TYPES['custom'])

        # Rol del destinatario (usamos el definido en EVENT_TYPES)
        rol_destino = event_info[2] if len(event_info) > 2 else 'todos'

        # Creamos la notificación
        notif = cls.objects.create(
            sender_ct=ContentType.objects.get_for_model(sender.__class__),
            sender_id=sender.id,
            recipient_ct=ContentType.objects.get_for_model(recipient.__class__),
            recipient_id=recipient.id,
            event_type=event_type,
            title=kwargs.get('title', event_info[1]),  # Permite personalizar título
            message=kwargs.get('message', event_info[1]),  # Mensaje personalizado
            rol_destinatario=rol_destino,  # Rol correcto (no depende del model_name)
        )

        # Si hay un objeto relacionado (target), lo asignamos
        if 'target' in kwargs and kwargs['target']:
            target = kwargs['target']
            notif.target_ct = ContentType.objects.get_for_model(target.__class__)
            notif.target_id = target.id
            notif.save()

        return notif

    @property
    def url(self):
        """Genera la URL adecuada basada en el tipo de evento y el objeto relacionado"""
        if not hasattr(self, '_url_cache'):
            try:
                event_info = self.EVENT_TYPES.get(self.event_type, self.EVENT_TYPES['custom'])
                url_name = event_info[0]

                # print(f"Generando URL para notificación {self.id} - tipo: {self.event_type}")

                # Casos especiales que no necesitan target
                if self.event_type in ['registro_padre', 'servicio_nuevo_padre']:
                    self._url_cache = reverse('servicios_escolares:panel_grupos_padres')
                    # print(f"URL especial generada: {self._url_cache}")
                    return self._url_cache

                # Construir URL basada en si necesita parámetro o no
                if self.target:
                    try:
                        # Intenta construir la URL con el ID del target
                        self._url_cache = reverse(url_name, kwargs={'pk': self.target.id})
                    except:
                        # Si falla, intenta sin parámetro
                        self._url_cache = reverse(url_name)
                else:
                    self._url_cache = reverse(url_name)

                print(f"URL generada: {self._url_cache}")

            except Exception as e:
                print(f"Error generando URL para notificación {self.id}: {str(e)}")
                self._url_cache = reverse('profesores:dashboard_profesor')

        return self._url_cache


class NotificationTemplate(models.Model):
    TIPOS_DESTINATARIOS = [
        ('padre', 'Padres'),
        ('profesor', 'Profesores'),
        ('servicio', 'Servicio Escolar'),
        ('todos', 'Todos los usuarios')
    ]

    TIPOS_EVENTOS = [
        ('cita', 'Citas'),
        ('feedback', 'Feedback'),
        ('academico', 'Académico'),
        ('soporte', 'Soporte'),
        ('general', 'General'),
        ('custom', 'Personalizado')
    ]

    nombre = models.CharField(max_length=100)
    contenido = models.TextField(help_text="Usa {variable} para marcadores de posición")
    destinatarios = models.CharField(max_length=20, choices=TIPOS_DESTINATARIOS, default='todos')
    tipo_evento = models.CharField(max_length=20, choices=TIPOS_EVENTOS, default='general')
    activa = models.BooleanField(default=True)

    # Relación genérica con el creador
    creador_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    creador_id = models.PositiveIntegerField()
    creador = GenericForeignKey('creador_ct', 'creador_id')

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla de Notificación"
        verbose_name_plural = "Plantillas de Notificación"
        ordering = ['-fecha_creacion']
        unique_together = ('nombre', 'destinatarios', 'tipo_evento')

    def __str__(self):
        return f"{self.nombre} ({self.get_destinatarios_display()})"

    def render(self, context=None):
        """
        Renderiza la plantilla con el contexto proporcionado
        """
        contenido = self.contenido

        # Procesar variables de contexto
        if context:
            for key, value in context.items():
                contenido = contenido.replace(f"{{{key}}}", str(value))

        # Añadir saludo según destinatario
        saludo = {
            'padre': 'Estimado padre/madre',
            'profesor': 'Estimado profesor/a',
            'servicio': 'Estimado equipo',
            'todos': 'Estimado usuario'
        }.get(self.destinatarios, 'Estimado usuario')

        contenido = contenido.replace("{saludo}", saludo)

        return contenido

    def get_absolute_url(self):
        return reverse('notificaciones:detalle_plantilla', args=[self.id])


'''
 @classmethod
    def crear_notificacion(cls, event_type, sender, recipient, **kwargs):
        """Crea una notificación específica entre dos usuarios"""
        event_info = cls.EVENT_TYPES.get(event_type, cls.EVENT_TYPES['custom'])

        notif = cls.objects.create(
            sender_ct=ContentType.objects.get_for_model(sender.__class__),
            sender_id=sender.id,
            recipient_ct=ContentType.objects.get_for_model(recipient.__class__),
            recipient_id=recipient.id,
            event_type=event_type,
            title=kwargs.get('title', event_info[1]),
            message=kwargs.get('message', ''),
            rol_destinatario=recipient._meta.model_name
        )

        if 'target' in kwargs:
            target = kwargs['target']
            notif.target_ct = ContentType.objects.get_for_model(target.__class__)
            notif.target_id = target.id
            notif.save()

        return notif

    def get_absolute_url(self):
        """Obtiene la URL correspondiente al tipo de notificación"""
        try:
            # Casos especiales
            if self.event_type == 'registro_padre':
                return reverse('servicios_escolares:panel_grupos_padres')

            # URL base del evento
            url_name = self.EVENT_TYPES.get(self.event_type, ('inicio',))[0]

            # Si necesita ID del objeto relacionado
            if self.target_id and url_name in [
                'servicios_escolares:detalle_ticket',
                'citas:detalle',
                'feedback:detalle',
                'academico:detalle_calificacion'
            ]:
                return reverse(url_name, kwargs={'pk': self.target_id})

            return reverse(url_name)

        except Exception as e:
            print(f"Error generando URL: {str(e)}")
            return reverse('servicios_escolares:dashboard')

@classmethod
    def notificar_nuevo_ticket(cls, ticket):
        """
        Método específico para notificaciones de tickets
        """
        from django.contrib.contenttypes.models import ContentType

        # 1. Notificar al servicio escolar
        servicio_escolar_ct = ContentType.objects.get_for_model(ServicioEscolar)

        # Puedes filtrar solo a los usuarios que deben recibir notificaciones
        destinatarios = ServicioEscolar.objects.filter(
            estado_cuenta='Activo',
            recibe_notificaciones=True
        )

        for destinatario in destinatarios:
            cls.crear_notificacion(
                event_type='servicio_ticket',
                recipient=destinatario,
                target=ticket,
                message=f"Nuevo ticket de {ticket.get_tipo_usuario_display()}: {ticket.asunto}"
            )

        # 2. Notificar al creador (si no es servicio escolar)
        if ticket.tipo_usuario != 'servicio_escolar':
            creator_ct = ContentType.objects.get_for_model(ticket.usuario.__class__)
            cls.crear_notificacion(
                event_type='custom',
                recipient=ticket.usuario,
                target=ticket,
                title='Ticket registrado',
                message=f"Has creado el ticket #{ticket.id}",
                rol_destinatario=ticket.tipo_usuario
            )
'''
