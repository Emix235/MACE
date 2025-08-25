from django.core.validators import MinValueValidator, FileExtensionValidator, MaxValueValidator
from datetime import timedelta, time
import uuid
import os
import json

from django.db.models import Q
from django.forms import forms

from formularios.models import RetroalimentacionAplicada, RetroalimentacionCita
from notificaciones.models import Notification
from profesores.models import Clase, Profesor
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from servicios_escolares.models import ServicioEscolar
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from datetime import timedelta
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


def evidencia_upload_path(instance, filename):
    """Genera una ruta única y ordenada para archivos de evidencia."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('citas', 'evidencias', str(instance.cita.id), filename)


class Cita(models.Model):
    ESTADOS = [
        ('pendiente', '🟡 Pendiente'),
        ('confirmada', '🟢 Confirmada'),
        ('completada', '🔵 Completada'),
        ('cancelada', '🔴 Cancelada'),
        ('reprogramada', '🟠 Reprogramada'),
    ]

    TIPOS = [
        ('academica', '📚 Académica'),
        ('administrativa', '📋 Administrativa'),
        ('orientacion', '🧭 Orientación'),
        ('emergencia', '🚨 Emergencia'),
        ('otra', '❔ Otra'),
    ]

    # Relaciones
    solicitante = models.ForeignKey(
        'padres.Padre',
        on_delete=models.CASCADE,
        related_name='citas_solicitadas'
    )
    profesor = models.ForeignKey(
        'profesores.Profesor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='citas_asignadas'
    )
    servicio_escolar = models.ForeignKey(
        'servicios_escolares.ServicioEscolar',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='citas_agendadas'
    )

    # Detalles principales
    titulo = models.CharField(max_length=100, default="Reunión", help_text="Ej: Reunión sobre rendimiento académico")
    tipo = models.CharField(max_length=50, choices=TIPOS, default='academica')
    fecha_hora_inicio = models.DateTimeField()
    duracion = models.PositiveIntegerField(default=30, help_text="Duración en minutos (mínimo 15)")
    fecha_hora_fin = models.DateTimeField(editable=False)

    # Ubicación y estado
    ubicacion = models.CharField(max_length=100, default="Escuela", blank=True)
    estado = models.CharField(max_length=50, choices=ESTADOS, default='pendiente')

    # Descripción
    motivo = models.TextField(help_text="Describa el propósito de la cita")
    observaciones = models.TextField(blank=True, null=True, help_text="Notas adicionales")

    # Integración con calendarios
    evento_google_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="ID Evento Google Calendar")
    evento_microsoft_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="ID Evento Outlook")
    evento_url = models.URLField(blank=True, null=True, verbose_name="Enlace al Evento")

    # Relaciones ManyToMany
    estudiantes = models.ManyToManyField('estudiantes.Estudiante', related_name='citas',
                                         verbose_name='Estudiantes involucrados')
    asistentes_padres = models.ManyToManyField('padres.Padre', blank=True, related_name='citas_como_asistente')
    asistentes_profesores = models.ManyToManyField('profesores.Profesor', blank=True,
                                                   related_name='citas_como_asistente')
    asistentes_servicio = models.ManyToManyField('servicios_escolares.ServicioEscolar', blank=True,
                                                 related_name='citas_como_asistente')

    # Metadata
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    creador_tipo = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    creador_id = models.PositiveIntegerField(null=True)
    creado_por = GenericForeignKey('creador_tipo', 'creador_id')

    class Meta:
        ordering = ['fecha_hora_inicio']
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        indexes = [
            models.Index(fields=['fecha_hora_inicio']),
            models.Index(fields=['estado']),
            models.Index(fields=['solicitante', 'profesor']),
        ]
        permissions = [
            ("cancelar_cita", "Puede cancelar cualquier cita"),
            ("reprogramar_cita", "Puede reprogramar citas"),
            ("ver_calendario_propio", "Puede ver su propio calendario de citas"),
            ("ver_calendario_general", "Puede ver el calendario general de citas"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.solicitante} ({self.get_estado_display()})"

    def clean(self):
        super().clean()

        if not self.fecha_hora_inicio or not self.duracion:
            raise ValidationError("La fecha y la duración son obligatorias para validar la cita.")

        # Calcular fecha_hora_fin para las validaciones
        self.fecha_hora_fin = self.fecha_hora_inicio + timedelta(minutes=self.duracion)

        # Validación 1: No en el pasado
        if self.fecha_hora_inicio <= timezone.now():
            raise ValidationError("No se pueden agendar citas en el pasado")

        # Validación 2: Margen mínimo de 15 minutos
        margen_minimo = timezone.now() + timedelta(minutes=15)
        if self.fecha_hora_inicio < margen_minimo:
            raise ValidationError(
                f"La cita debe programarse con al menos 15 minutos de anticipación. "
                f"Hora mínima: {margen_minimo.strftime('%H:%M')}"
            )

        # Validación 3: No fines de semana
        if self.fecha_hora_inicio.weekday() >= 5:
            raise ValidationError("No se pueden agendar citas los fines de semana")

        # Validación 4: Horario laboral (inicio)
        hora_inicio = self.fecha_hora_inicio.time()
        if hora_inicio < self.HORA_INICIO_OFICIAL or hora_inicio > self.HORA_FIN_OFICIAL:
            raise ValidationError(
                f"El horario de atención es de {self.HORA_INICIO_OFICIAL.strftime('%H:%M')} "
                f"a {self.HORA_FIN_OFICIAL.strftime('%H:%M')}"
            )

        # Validación 5: No exceder horario al finalizar
        hora_fin = self.fecha_hora_fin.time()
        if hora_fin > self.HORA_FIN_OFICIAL:
            raise ValidationError(
                f"La cita no puede terminar después de las {self.HORA_FIN_OFICIAL.strftime('%H:%M')}"
            )

    def save(self, *args, **kwargs):
        """Calcula automáticamente la fecha de fin antes de guardar"""
        if self.fecha_hora_inicio and self.duracion:
            self.fecha_hora_fin = self.fecha_hora_inicio + timedelta(minutes=self.duracion)
        super().save(*args, **kwargs)

    def get_estudiantes(self):
        """Obtiene todos los estudiantes relacionados con esta cita"""
        return self.estudiantes.all()

    def estudiantes_list(self):
        return [str(est) for est in self.estudiantes.all()]

    @property
    def tiene_retroalimentacion(self):
        """Verifica si la cita ya tiene retroalimentación aplicada"""
        return hasattr(self, 'retroalimentacion') and self.retroalimentacion is not None

    @property
    def retroalimentacion_completada(self):
        """Verifica si la retroalimentación fue completada"""
        return self.tiene_retroalimentacion and self.retroalimentacion.completada

    # Propiedades y métodos útiles
    @property
    def en_progreso(self):
        """Verifica si la cita está ocurriendo ahora"""
        ahora = timezone.now()
        return self.fecha_hora_inicio <= ahora <= self.fecha_hora_fin

    @property
    def creada_por_padre(self):
        return not self.profesor and not self.servicio_escolar

    @property
    def creada_por_profesor(self):
        return bool(self.profesor)

    @property
    def creada_por_servicio_escolar(self):
        return bool(self.servicio_escolar)

    def tipo_creador(self):
        if self.creada_por_servicio_escolar:
            return "servicio_escolar"
        return "profesor" if self.creada_por_profesor else "padre"

    def get_badge_color(self):
        colors = {
            'pendiente': 'warning',
            'confirmada': 'success',
            'completada': 'info',
            'cancelada': 'danger',
            'reprogramada': 'primary',
        }
        return colors.get(self.estado, 'secondary')

    def estudiantes_list(self):
        return ", ".join([str(e) for e in self.estudiantes.all()])

    def confirmar_por_padre(self, padre):
        """Confirma la cita por el padre y genera notificación"""
        if self.estado != 'pendiente' or self.solicitante != padre:
            return False, None

        self.estado = 'confirmada'
        self.save()

        return True, {
            'titulo': f"Cita confirmada: {self.titulo}",
            'mensaje': f"El padre {padre.nombre_completo} ha confirmado la cita programada para {self.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}",
            'tipo_evento': 'padre_cita_confirmada',
            'destinatario': self.profesor,
            'target': self
        }

    def puede_ser_completada_por(self, usuario):
        """
            Versión simplificada que solo verifica el tipo de usuario
            Asume que 'usuario' es una instancia de:
            - ServicioEscolar (acceso total)
            - Profesor (solo sus citas)
        """
        if isinstance(usuario, ServicioEscolar):
            return usuario == self.servicio_escolar or usuario in self.asistentes_servicio.all()
        elif isinstance(usuario, Profesor):
            return usuario == self.profesor
        # Cualquier otro caso no tiene permiso
        return False

    @property
    def retroalimentacion_pendiente(self):
        """Verifica si hay retroalimentación pendiente para esta cita"""
        if not hasattr(self, '_retroalimentacion_pendiente'):
            self._retroalimentacion_pendiente = hasattr(self,
                                                        'retroalimentacion') and not self.retroalimentacion.completada
        return self._retroalimentacion_pendiente

    @property
    def puede_marcar_como_completada(self):
        """Determina si la cita puede marcarse como completada"""
        return (self.estado in ['confirmada', 'pendiente', 'reprogramada'] and
                self.fecha_hora_fin < timezone.now())

    '''
    return (self.estado == 'confirmada' and
                self.fecha_hora_fin < timezone.now())
    '''

    def enviar_notificacion_retroalimentacion(self):
        """Envía notificación al padre sobre la retroalimentación pendiente"""
        # Implementación depende de tu sistema de notificaciones
        # Ejemplo básico:
        from django.core.mail import send_mail
        subject = f"Retroalimentación de cita: {self.titulo}"
        message = f"""Hola {self.solicitante.nombre_completo},\n\n
        Por favor completa la retroalimentación de tu cita del {self.fecha_hora_inicio.strftime('%d/%m/%Y')}\n
        Accede aquí: [ENLACE]"""

        send_mail(
            subject,
            message,
            'no-reply@escuela.com',
            [self.solicitante.correo_electronico],
            fail_silently=False,
        )

    @classmethod
    def citas_pasadas_pendientes(cls, servicio_escolar):
        """Obtiene citas pasadas que deberían marcarse como completadas"""
        ahora = timezone.now()
        return cls.objects.filter(
            Q(servicio_escolar=servicio_escolar) |
            Q(asistentes_servicio=servicio_escolar),
            estado__in=['confirmada', 'pendiente'],
            fecha_hora_fin__lt=ahora
        ).exclude(estado='completada').order_by('-fecha_hora_inicio')

    def generar_notificacion_confirmacion(self, confirmador, user_type):
        """
        Crea notificaciones de confirmación de cita para los involucrados
        según el tipo de usuario que confirma.

        Args:
            confirmador: Instancia del modelo que confirma (Padre, Profesor o ServicioEscolar)
            user_type: Tipo de usuario ('padre', 'profesor' o 'servicio')
        """
        from django.contrib.contenttypes.models import ContentType
        from django.apps import apps

        # Verificar si el confirmador es válido
        if not confirmador or not hasattr(confirmador, '_meta'):
            return False

        # Mapeo de tipos de evento por rol
        event_type_mapping = {
            'padre': {
                'profesor': 'padre_cita_confirmada',
                'servicio': 'servicio_cita_confirmada',
                'padre': 'padre_cita_confirmada'
            },
            'profesor': {
                'padre': 'profesor_cita_confirmada',
                'servicio': 'servicio_cita_confirmada'
            },
            'servicio': {
                'padre': 'servicio_cita_confirmada',
                'profesor': 'servicio_cita_confirmada'
            }
        }

        try:
            # Configuración común
            cita_content_type = ContentType.objects.get_for_model(self)
            sender_content_type = ContentType.objects.get_for_model(confirmador.__class__)
            fecha_cita = self.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')
            confirmador_nombre = getattr(confirmador, 'nombre_completo', str(confirmador))

            # 1. Notificación para el profesor (si aplica)
            if self.profesor:  # Verificación explícita de que profesor no es None
                profesor_event_type = event_type_mapping[user_type].get('profesor')
                if profesor_event_type:
                    Notification.objects.create(
                        recipient_ct=ContentType.objects.get_for_model(self.profesor),
                        recipient_id=self.profesor.id,
                        event_type=profesor_event_type,
                        title=f"Cita confirmada por {confirmador_nombre}",
                        message=f"La cita '{self.titulo}' para {fecha_cita} ha sido confirmada",
                        rol_destinatario='profesor',
                        target_ct=cita_content_type,
                        target_id=self.id,
                        sender_ct=sender_content_type,
                        sender_id=confirmador.id
                    )

            # 2. Notificación para servicio escolar
            servicio_event_type = event_type_mapping[user_type].get('servicio')
            if servicio_event_type:
                ServicioEscolar = apps.get_model('servicios_escolares', 'ServicioEscolar')
                servicio_escolar_ct = ContentType.objects.get_for_model(ServicioEscolar)

                # Solo notificar a servicios escolares activos
                for servicio_user in ServicioEscolar.objects.filter(estado_cuenta='Activo'):
                    profesor_nombre = getattr(self.profesor, 'nombre_completo',
                                              'el usuario') if self.profesor else 'el usuario'

                    Notification.objects.create(
                        recipient_ct=servicio_escolar_ct,
                        recipient_id=servicio_user.id,
                        event_type=servicio_event_type,
                        title=f"Cita confirmada ({self.get_estado_display()})",
                        message=f"{confirmador_nombre} ha confirmado la cita con {profesor_nombre}",
                        rol_destinatario='servicio',
                        target_ct=cita_content_type,
                        target_id=self.id,
                        sender_ct=sender_content_type,
                        sender_id=confirmador.id
                    )

            # 3. Notificación para el solicitante (si no es quien confirma)
            if user_type != 'padre' and self.solicitante and self.solicitante != confirmador:
                padre_event_type = event_type_mapping[user_type].get('padre')
                if padre_event_type:
                    profesor_nombre = getattr(self.profesor, 'nombre_completo',
                                              'el destinatario') if self.profesor else 'el destinatario'

                    Notification.objects.create(
                        recipient_ct=ContentType.objects.get_for_model(self.solicitante),
                        recipient_id=self.solicitante.id,
                        event_type=padre_event_type,
                        title=f"Tu cita ha sido confirmada",
                        message=f"La cita con {profesor_nombre} fue confirmada para {fecha_cita}",
                        rol_destinatario='padre',
                        target_ct=cita_content_type,
                        target_id=self.id,
                        sender_ct=sender_content_type,
                        sender_id=confirmador.id
                    )

            return True

        except Exception as e:
            # Loggear el error si es necesario
            return False

    HORA_INICIO_OFICIAL = time(8, 0)  # 8:00 am
    HORA_FIN_OFICIAL = time(18, 0)  # 6:00 pm


class ModificacionCita(models.Model):
    cita = models.ForeignKey(Cita, on_delete=models.CASCADE, related_name='modificaciones')

    # Campos para GenericForeignKey
    creator_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    creator_object_id = models.PositiveIntegerField()
    usuario = GenericForeignKey('creator_content_type', 'creator_object_id')

    fecha_modificacion = models.DateTimeField(auto_now_add=True)
    campo_modificado = models.CharField(max_length=100)
    valor_anterior = models.TextField()
    valor_nuevo = models.TextField()
    motivo = models.TextField()

    class Meta:
        ordering = ['-fecha_modificacion']


class CitaPrioritaria(Cita):
    PRIORIDAD_CHOICES = [
        ('critica', '🔴 Crítica (Requiere acción inmediata)'),
        ('alta', '🟠 Alta (Urgente - Resolver en 24h)'),
        ('media', '🟡 Media (Importante - Resolver en 72h)'),
    ]

    TIPOS_URGENCIA = [
        ('disciplinaria', '⚖️ Situación disciplinaria'),
        ('academica', '📚 Crisis académica'),
        ('salud', '🏥 Emergencia de salud'),
        ('seguridad', '🚨 Incidente de seguridad'),
        ('otra', '❗ Otra urgencia'),
    ]

    # Campos de prioridad como campos separados
    nivel_prioridad = models.CharField(
        max_length=20,
        choices=PRIORIDAD_CHOICES,
        default='alta'
    )

    motivo_prioridad = models.TextField(
        blank=True,
        null=True,
        help_text="Explicación detallada de la prioridad asignada"
    )

    autor_prioridad = models.CharField(
        max_length=100,
        blank=True,
        help_text="Quién marcó la prioridad"
    )

    fecha_marcado_prioridad = models.DateTimeField(
        auto_now_add=True,
        blank=True,
        null=True,
        help_text="Fecha cuando se marcó la prioridad"
    )

    # Resto de tus campos...
    autoridades_notificadas = models.ManyToManyField(
        'profesores.Profesor',
        blank=True,
        related_name='citas_prioritarias_notificadas'
    )

    evidencia_archivo = models.FileField(
        upload_to='evidencias_citas/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png', 'docx', 'xlsx'])],
        help_text="Archivo de evidencia adjunto (opcional)"
    )

    class Meta:
        verbose_name = "Cita Prioritaria"
        verbose_name_plural = "Citas Prioritarias"
        ordering = ['nivel_prioridad', 'fecha_hora_inicio']
        permissions = [
            ("escalar_prioridad", "Puede escalar citas a prioridad crítica"),
            ("ver_todas_prioritarias", "Puede ver todas las citas prioritarias"),
        ]

    def __str__(self):
        return f"{self.get_nivel_prioridad_display()} - {self.titulo}"

    def clean(self):
        super().clean()

    def save(self, *args, **kwargs):
        # Actualizar observaciones en el modelo base
        if not self.observaciones:
            self.observaciones = ""

        super().save(*args, **kwargs)

    @property
    def color_prioridad(self):
        return {
            'critica': 'danger',
            'alta': 'warning',
            'media': 'info'
        }.get(self.nivel_prioridad, 'secondary')

    def estudiantes_list(self):
        # Devuelve lista de strings con nombres de estudiantes
        return [str(estudiante) for estudiante in self.estudiantes.all()]

    def notificar_urgencia(self):
        """Notifica a las autoridades correspondientes según la prioridad"""
        if self.nivel_prioridad == 'critica':
            self._notificar_autoridades_criticas()
        elif self.nivel_prioridad == 'alta':
            self._notificar_responsables()

        Notification.objects.create(
            tipo='prioridad_cita',
            nivel=self.nivel_prioridad,
            contenido=f"Cita prioritaria creada: {self.titulo}",
            relacion_contenido=ContentType.objects.get_for_model(self),
            relacion_id=self.id
        )

    def _notificar_autoridades_criticas(self):
        """Notificación especial para casos críticos"""
        pass

    def _notificar_responsables(self):
        """Notificación estándar para prioridades altas"""
        pass


class EvidenciaCita(models.Model):
    """Modelo para archivos adjuntos a citas"""
    cita = models.ForeignKey(
        Cita,
        on_delete=models.CASCADE,
        related_name='evidencias'
    )
    archivo = models.FileField(
        upload_to=evidencia_upload_path,
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png', 'pdf', 'docx', 'xlsx'])
        ]
    )
    descripcion = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)

    # Puedes cambiar esto si tienes un modelo común de usuario
    subido_por_profesor = models.ForeignKey(
        'profesores.Profesor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    subido_por_servicio = models.ForeignKey(
        'servicios_escolares.ServicioEscolar',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    subido_por_padre = models.ForeignKey(
        'padres.Padre',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Evidencia"
        verbose_name_plural = "Evidencias"

    def __str__(self):
        return f"Evidencia {self.id} - {self.cita.titulo}"


class ReprogramacionCita(models.Model):
    """
    Registra todos los cambios de reprogramación manteniendo un historial completo
    sin modificar los datos originales de la cita.
    """
    cita_original = models.ForeignKey(
        Cita,
        on_delete=models.CASCADE,
        related_name='reprogramaciones'
    )
    fecha_hora_original = models.DateTimeField()
    fecha_hora_nueva = models.DateTimeField()
    motivo = models.TextField(help_text="Motivo de la reprogramación")
    realizado_por_tipo = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    realizado_por_id = models.PositiveIntegerField(null=True)
    realizado_por = GenericForeignKey('realizado_por_tipo', 'realizado_por_id')
    fecha_reprogramacion = models.DateTimeField(auto_now_add=True)

    # Campos para almacenar los datos originales (en lugar de JSONField)
    titulo_original = models.CharField(max_length=100, blank=True)
    tipo_original = models.CharField(max_length=50, blank=True)
    duracion_original = models.PositiveIntegerField(null=True)
    ubicacion_original = models.CharField(max_length=100, blank=True)
    motivo_original = models.TextField(blank=True)
    estado_original = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "Reprogramación de Cita"
        verbose_name_plural = "Reprogramaciones de Citas"
        ordering = ['-fecha_reprogramacion']

    def __str__(self):
        return f"Reprogramación #{self.id} - Cita #{self.cita_original_id}"

    def save(self, *args, **kwargs):
        # Guardar datos originales si es una nueva reprogramación
        if not self.pk:
            self.titulo_original = self.cita_original.titulo
            self.tipo_original = self.cita_original.tipo
            self.duracion_original = self.cita_original.duracion
            self.ubicacion_original = self.cita_original.ubicacion
            self.motivo_original = self.cita_original.motivo
            self.estado_original = self.cita_original.estado

            # Guardar IDs de relaciones ManyToMany en texto
            self.estudiantes_original = ", ".join(map(str, self.cita_original.estudiantes.values_list('id', flat=True)))
            self.asistentes_padres_original = ", ".join(
                map(str, self.cita_original.asistentes_padres.values_list('id', flat=True)))
            self.asistentes_profesores_original = ", ".join(
                map(str, self.cita_original.asistentes_profesores.values_list('id', flat=True)))
            self.asistentes_servicio_original = ", ".join(
                map(str, self.cita_original.asistentes_servicio.values_list('id', flat=True)))

        super().save(*args, **kwargs)

    @property
    def estudiantes_original_ids(self):
        """Devuelve lista de IDs de estudiantes originales"""
        return [int(id) for id in self.estudiantes_original.split(", ") if id] if self.estudiantes_original else []

    @property
    def asistentes_padres_original_ids(self):
        """Devuelve lista de IDs de padres asistentes originales"""
        return [int(id) for id in self.asistentes_padres_original.split(", ") if
                id] if self.asistentes_padres_original else []

    @property
    def asistentes_profesores_original_ids(self):
        """Devuelve lista de IDs de profesores asistentes originales"""
        return [int(id) for id in self.asistentes_profesores_original.split(", ") if
                id] if self.asistentes_profesores_original else []

    @property
    def asistentes_servicio_original_ids(self):
        """Devuelve lista de IDs de servicios asistentes originales"""
        return [int(id) for id in self.asistentes_servicio_original.split(", ") if
                id] if self.asistentes_servicio_original else []


'''
class CitaPrioritariaForm(forms.ModelForm):
    PRIORIDAD_CHOICES = [
        ('', '----'),
        ('alta', '🔴 Alta (Urgente)'),
        ('media', '🟡 Media (Importante)'),
        ('baja', '🔵 Baja (Relevante)'),
    ]

    es_prioritaria = forms.BooleanField(
        required=False,
        label="Marcar como prioritaria",
        widget=forms.CheckboxInput(attrs={'class': 'prioridad-checkbox'})
    )

    nivel_prioridad = forms.ChoiceField(
        choices=PRIORIDAD_CHOICES,
        required=False,
        label="Nivel de prioridad",
        widget=forms.Select(attrs={'class': 'form-select prioridad-select', 'disabled': True})
    )

    motivo_prioridad = forms.CharField(
        required=False,
        label="Razón de prioridad",
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control prioridad-motivo', 'disabled': True}),
        help_text="Describa brevemente por qué requiere prioridad"
    )

    class Meta:
        model = Cita
        fields = ['titulo', 'tipo', 'fecha_hora_inicio', 'duracion', 'motivo', 'ubicacion']

'''
