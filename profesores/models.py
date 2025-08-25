import os
from uuid import uuid4

from django.db.models import Q
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.urls import reverse, NoReverseMatch
from django.utils.translation import gettext_lazy as _
from estudiantes.models import CicloEscolar, Estudiante
from formularios.models import RetroalimentacionCita, RetroalimentacionAplicada, RespuestaRetroalimentacion
from notificaciones.models import Notification
from servicios_escolares.middleware import logger
from servicios_escolares.models import ThemeConfig


# nombre_usuario = models.CharField(max_length=100)

def user_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid4().hex}.{ext}"
    return os.path.join('users', 'profesores', str(instance.id), filename)


class Profesor(models.Model):
    nombre_completo = models.CharField(max_length=200)
    apellidos = models.CharField(max_length=200)
    correo_electronico = models.EmailField(unique=True)
    contraseña = models.CharField(max_length=100)
    telefono_principal = models.CharField(max_length=20)
    telefono_respaldo = models.CharField(max_length=20, blank=True, null=True)
    rol_usuario = models.CharField(max_length=50, default='Profesor')
    estado_cuenta = models.CharField(max_length=50, default='Activo')
    fecha_registro = models.DateField(auto_now_add=True)
    ultima_fecha_sesion = models.DateField(blank=True, null=True)
    imagen_usuario = models.ImageField(
        upload_to=user_image_path,
        blank=True,
        null=True,
        verbose_name="Imagen de perfil",
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png'])]  # Agregar campo de imagen
    )

    # Campos que pueden añadirse después (no en el registro inicial)
    datos_personales = models.TextField(blank=True, null=True)
    asignaturas_impartidas = models.TextField(blank=True, null=True)
    datos_contacto = models.TextField(blank=True, null=True)

    google_calendar_enabled = models.BooleanField(default=False)
    google_access_token = models.CharField(max_length=512, blank=True, null=True)
    google_refresh_token = models.CharField(max_length=512, blank=True, null=True)
    google_token_expiry = models.DateTimeField(blank=True, null=True)
    personal_theme = models.CharField(
        max_length=100,
        choices=ThemeConfig.THEME_CHOICES if hasattr(ThemeConfig, 'THEME_CHOICES') else [],
        blank=True,
        null=True
    )

    def __str__(self):
        return f"Prof. {self.nombre_completo} {self.apellidos}"

    @property
    def calificacion_promedio(self):
        from django.db.models import Avg
        promedio = self.retroalimentaciones_recibidas.filter(
            completada=True
        ).aggregate(
            promedio=Avg('respuestas__valor_numero', filter=Q(respuestas__pregunta__tipo='escala_5'))
        )['promedio']
        return promedio or 0.0

    @property
    def cantidad_evaluaciones(self):
        return self.retroalimentaciones_recibidas.filter(completada=True).count()

    @property
    def ultima_evaluacion(self):
        return self.retroalimentaciones_recibidas.filter(completada=True).order_by('-fecha_respuesta').first()

    def get_notificaciones(self, limit=5):
        """Obtiene las notificaciones recientes para mostrar en el dropdown"""
        content_type = ContentType.objects.get_for_model(Profesor)
        notificaciones = Notification.objects.filter(
            recipient_ct=content_type,
            recipient_id=self.id
        ).order_by('-created_at').values(
            'id', 'title', 'message', 'is_read', 'created_at', 'event_type', 'target_id'
        )[:limit]  # Limitar según lo que necesites en el dropdown

        notificaciones_list = []
        for notif in notificaciones:
            try:
                notif_dict = {
                    'id': notif['id'],
                    'title': notif['title'],
                    'message': notif['message'],
                    'is_read': notif['is_read'],
                    'created_at': notif['created_at'].strftime('%Y-%m-%d %H:%M'),  # Formato más corto para el dropdown
                    'url': self._get_notification_url(
                        notif['event_type'],
                        notif['target_id'] if notif['target_id'] else None
                    )
                }
                notificaciones_list.append(notif_dict)
            except Exception as e:
                logger.error(f"Error procesando notificación {notif.get('id')}: {str(e)}")
                continue

        return notificaciones_list

    import logging

    logger = logging.getLogger(__name__)

    def _get_notification_url(self, event_type, target_id=None):
        """Versión unificada que replica el comportamiento de la propiedad url del modelo"""
        from django.urls import reverse
        from django.urls.exceptions import NoReverseMatch
        from notificaciones.models import Notification  # Importación local para evitar circularidad

        try:
            # Usamos el EVENT_TYPES del modelo para consistencia
            event_info = Notification.EVENT_TYPES.get(event_type, Notification.EVENT_TYPES['custom'])
            url_name = event_info[0]

            logger.debug(f"Generando URL para '{event_type}' usando url_name='{url_name}'")

            # Casos especiales que no necesitan target
            if event_type in ['registro_padre', 'servicio_nuevo_padre']:
                url = reverse('servicios_escolares:panel_grupos_padres')
                logger.debug(f"URL especial generada: {url}")
                return url

            # Construcción de URL con manejo de errores
            if target_id:
                try:
                    url = reverse(url_name, kwargs={'pk': target_id})
                    logger.debug(f"URL con parámetro generada: {url}")
                    return url
                except NoReverseMatch:
                    logger.debug("Fallando a URL sin parámetro")
                    url = reverse(url_name)
                    return url
            else:
                url = reverse(url_name)
                logger.debug(f"URL simple generada: {url}")
                return url

        except Exception as e:
            logger.error(f"Error generando URL: {str(e)}", exc_info=True)
            return reverse('profesores:dashboard_profesor')

    def notificaciones_no_leidas(self):
        """Obtiene solo el conteo de notificaciones no leídas (optimizado)"""
        content_type = ContentType.objects.get_for_model(Profesor)
        return Notification.objects.filter(
            recipient_ct=content_type,
            recipient_id=self.id,
            is_read=False
        ).count()

    def marcar_cita_como_completada_con_retroalimentacion(self, cita):
        """
        Marca una cita como completada y asigna el formulario de retroalimentación.

        Returns:
            (bool, str, RetroalimentacionAplicada|None):
                Éxito o fallo, mensaje, y retroalimentación aplicada si procede.
        """
        if not cita.puede_marcar_como_completada:
            return False, "Esta cita no puede marcarse como completada", None

        if not cita.puede_ser_completada_por(self):
            return False, "No tienes permiso para completar esta cita", None

        try:
            with transaction.atomic():
                # 1. Marcar cita como completada
                cita.estado = 'completada'
                cita.save(update_fields=['estado'])

                # 2. Obtener plantilla de retroalimentación
                retro_default = RetroalimentacionCita.obtener_plantilla_para_profesor(self)
                if not retro_default:
                    return False, "No se encontró plantilla de retroalimentación predeterminada", None

                # 3. Crear retroalimentación aplicada
                retro_app = RetroalimentacionAplicada.objects.create(
                    cita=cita,
                    retroalimentacion=retro_default,
                    fecha_aplicacion=timezone.now(),
                    profesor=cita.profesor  # Asume que la cita tiene relación con Profesor
                )

                # 4. Crear respuestas asociadas a cada pregunta
                respuestas = [
                    RespuestaRetroalimentacion(
                        retroalimentacion_aplicada=retro_app,
                        pregunta=pregunta,
                        padre=cita.solicitante
                    )
                    for pregunta in retro_default.preguntas.all()
                ]

                RespuestaRetroalimentacion.objects.bulk_create(respuestas)

                return True, "Cita completada y retroalimentación asignada", retro_app

        except Exception as e:
            logger.error(f"Error al completar cita {cita.id}: {str(e)}", exc_info=True)
            return False, f"Error al procesar la operación: {str(e)}", None


class Clase(models.Model):
    NIVELES_EDUCATIVOS = [
        ('PRI', 'Primaria'),
        ('SEC', 'Secundaria'),
        ('BAC', 'Bachillerato'),
    ]

    TIPOS_ASIGNATURA = [
        ('OBL', 'Obligatoria'),
        ('OPT', 'Optativa'),
        ('EXT', 'Extracurricular'),
    ]

    nombre = models.CharField(max_length=100, verbose_name="Nombre de la materia")
    nivel_educativo = models.ForeignKey('estudiantes.NivelEducativo', null=True, on_delete=models.PROTECT)
    tipo_asignatura = models.CharField(max_length=3, choices=TIPOS_ASIGNATURA, default='OBL',
                                       verbose_name="Tipo de asignatura")

    # Relaciones con modelos externos usando 'app.Modelo'
    profesor = models.ForeignKey(
        'profesores.Profesor',
        on_delete=models.CASCADE,
        related_name='clases',
        verbose_name="Profesor titular"
    )

    grupo = models.ForeignKey(
        'estudiantes.Grupo',
        on_delete=models.CASCADE,
        related_name='clases',
        verbose_name="Grupo asignado"
    )

    ciclo_escolar = models.ForeignKey(
        'estudiantes.CicloEscolar',
        on_delete=models.CASCADE,
        related_name='clases',
        verbose_name="Ciclo escolar"
    )

    class Meta:
        verbose_name = "Materia"
        verbose_name_plural = "Materias"
        ordering = ['nombre']
        unique_together = ('nombre', 'grupo', 'ciclo_escolar')

    def __str__(self):
        return f"{self.nombre} - {self.grupo}"


class HorarioClase(models.Model):
    DIAS_SEMANA = [
        (1, 'Lunes'),
        (2, 'Martes'),
        (3, 'Miércoles'),
        (4, 'Jueves'),
        (5, 'Viernes'),
        (6, 'Sábado'),
    ]

    clase = models.ForeignKey(
        Clase,
        on_delete=models.CASCADE,
        related_name='horarios'
    )

    dia_semana = models.PositiveSmallIntegerField(choices=DIAS_SEMANA, verbose_name="Día de la semana")
    hora_inicio = models.TimeField(verbose_name="Hora de inicio")
    hora_fin = models.TimeField(verbose_name="Hora de finalización")
    aula = models.CharField(max_length=20, verbose_name="Aula asignada")

    class Meta:
        verbose_name = "Horario de clase"
        verbose_name_plural = "Horarios de clases"
        ordering = ['dia_semana', 'hora_inicio']
        unique_together = ('clase', 'dia_semana', 'hora_inicio')

    def __str__(self):
        return f"{self.get_dia_semana_display()} {self.hora_inicio}-{self.hora_fin} | {self.clase}"

    def clean(self):
        # Validación básica de horas
        if self.hora_fin <= self.hora_inicio:
            raise ValidationError("La hora de finalización debe ser posterior a la de inicio")

        # Solo validar solapamiento si la clase ya tiene grupo
        if hasattr(self.clase, 'grupo') and self.clase.grupo:
            horarios_solapados = HorarioClase.objects.filter(
                clase__grupo=self.clase.grupo,
                dia_semana=self.dia_semana,
                hora_inicio__lt=self.hora_fin,
                hora_fin__gt=self.hora_inicio
            ).exclude(pk=self.pk if self.pk else None)

            if horarios_solapados.exists():
                raise ValidationError("Este horario se solapa con otra clase del mismo grupo")


class Calificacion(models.Model):
    estudiante = models.ForeignKey(
        'estudiantes.Estudiante',
        on_delete=models.CASCADE,
        related_name='calificaciones'
    )

    clase = models.ForeignKey(
        Clase,
        on_delete=models.CASCADE,
        related_name='calificaciones'
    )

    periodo = models.ForeignKey(
        'estudiantes.PeriodoEscolar',
        on_delete=models.CASCADE,
        related_name='calificaciones',
        verbose_name="Periodo escolar"
    )

    calificacion = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        verbose_name="Calificación"
    )

    faltas = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Faltas acumuladas"
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )

    class Meta:
        verbose_name = "Calificación"
        verbose_name_plural = "Calificaciones"
        unique_together = ('estudiante', 'clase', 'periodo')
        ordering = ['periodo', 'clase', 'estudiante']

    def __str__(self):
        return f"{self.estudiante} - {self.clase} - {self.calificacion}"

    def clean(self):
        # Validar que el estudiante pertenezca al grupo de la clase
        if self.estudiante.grupo_actual != self.clase.grupo:
            raise ValidationError("El estudiante no pertenece al grupo de esta clase")

        # Validar que la fecha esté dentro de algún periodo del ciclo
        periodo_valido = False
        for periodo in self.clase.ciclo_escolar.obtener_periodos():
            if periodo['fecha_inicio'] <= self.fecha_registro.date() <= periodo['fecha_fin']:
                periodo_valido = True
                break

        if not periodo_valido:
            raise ValidationError("La fecha de registro no corresponde a ningún periodo del ciclo escolar")


class PeriodoEscolar(models.Model):
    ciclo = models.ForeignKey(
        'estudiantes.CicloEscolar',
        on_delete=models.CASCADE,
        related_name='periodos',
        verbose_name="Ciclo escolar"
    )
    nombre = models.CharField(max_length=50, verbose_name="Nombre del periodo")
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de término")

    class Meta:
        verbose_name = "Periodo Escolar"
        verbose_name_plural = "Periodos Escolares"
        ordering = ['fecha_inicio']
        unique_together = ('ciclo', 'nombre')

    def __str__(self):
        return f"{self.nombre} - {self.ciclo.nombre}"


class TiempoLibreProfesor(models.Model):
    profesor = models.ForeignKey(
        Profesor,
        on_delete=models.CASCADE,
        related_name='tiempos_libres'
    )
    dia_semana = models.PositiveSmallIntegerField(choices=HorarioClase.DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    motivo = models.CharField(max_length=100, blank=True, null=True)
    ciclo_escolar = models.ForeignKey(
        CicloEscolar,
        on_delete=models.CASCADE,
        related_name='tiempos_libres_profesores'
    )

    class Meta:
        verbose_name = "Tiempo libre del profesor"
        verbose_name_plural = "Tiempos libres de profesores"
        ordering = ['dia_semana', 'hora_inicio']
        unique_together = ('profesor', 'dia_semana', 'hora_inicio', 'ciclo_escolar')

    def clean(self):
        if self.hora_fin <= self.hora_inicio:
            raise ValidationError("La hora de finalización debe ser posterior a la de inicio")

        # Verificar que no se solape con clases existentes
        horarios_solapados = HorarioClase.objects.filter(
            clase__profesor=self.profesor,
            dia_semana=self.dia_semana,
            hora_inicio__lt=self.hora_fin,
            hora_fin__gt=self.hora_inicio,
            clase__ciclo_escolar=self.ciclo_escolar
        )

        if horarios_solapados.exists():
            raise ValidationError("Este horario se solapa con una clase existente")
