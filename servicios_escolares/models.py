from django.utils import timezone  # Asegúrate de tener esta importación
from django.db import models, transaction
from django.contrib.auth.hashers import make_password, check_password
import os
from uuid import uuid4
from django.contrib.contenttypes.models import ContentType
from formularios.models import RetroalimentacionCita, RetroalimentacionAplicada, RespuestaRetroalimentacion
import logging

logger = logging.getLogger(__name__)  # Esto crea un logger con el nombre del módulo actual


def user_image_path(instance, filename):
    # Obtiene la extensión del archivo (ej: .jpg, .png)
    ext = filename.split('.')[-1]
    # Genera un nombre único para el archivo
    filename = f"{uuid4().hex}.{ext}"
    # Retorna la ruta completa dentro de 'media/users/servicios_escolares/id_usuario/'
    return os.path.join('users', 'servicios_escolares', str(instance.id), filename)


class ServicioEscolar(models.Model):
    nombre_completo = models.CharField(max_length=200, unique=True)
    apellidos = models.CharField(max_length=200)
    correo_electronico = models.EmailField(unique=True)
    contraseña = models.CharField(max_length=128)  # Campo original como lo tenías
    telefono_principal = models.CharField(max_length=20)
    telefono_respaldo = models.CharField(max_length=20, blank=True, null=True)
    rol_usuario = models.CharField(max_length=50, default='Servicio Escolar')
    estado_cuenta = models.CharField(max_length=50, default='Activo')
    fecha_registro = models.DateField(auto_now_add=True)
    ultima_fecha_sesion = models.DateField(blank=True, null=True)
    imagen_usuario = models.ImageField(
        upload_to=user_image_path,
        blank=True,
        null=True,
        verbose_name="Imagen de perfil"
    )
    datos_personales = models.TextField(blank=True, null=True)
    horario_atencion = models.TextField(blank=True, null=True)
    estado_disponibilidad = models.CharField(max_length=50, default='Disponible')
    google_calendar_enabled = models.BooleanField(default=False)
    google_access_token = models.CharField(max_length=512, blank=True, null=True)
    google_refresh_token = models.CharField(max_length=512, blank=True, null=True)
    google_token_expiry = models.DateTimeField(blank=True, null=True)

    def has_google_auth(self):
        return bool(self.google_access_token)

    def set_password(self, raw_password):
        self.contraseña = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.contraseña)

    def save(self, *args, **kwargs):
        # Si es un nuevo usuario o la contraseña cambió, hashearla
        if not self.pk or 'contraseña' in kwargs.get('update_fields', []):
            self.set_password(self.contraseña)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre_completo} (Servicio Escolar)"

    @property
    def notificaciones(self):
        """Obtiene todas las notificaciones para este servicio escolar"""
        from django.contrib.contenttypes.models import ContentType
        from notificaciones.models import Notification

        ct = ContentType.objects.get_for_model(ServicioEscolar)
        return Notification.objects.filter(
            recipient_ct=ct,
            recipient_id=self.id
        ).order_by('-created_at')

    def get_notificaciones_servicio(self):
        return self.notificaciones.filter(
            rol_destinatario='servicio',
            is_read=False
        ).order_by('-created_at')

    def contar_notificaciones_no_leidas(self):
        """Cuenta las notificaciones no leídas"""
        return self.notificaciones.filter(is_read=False).count()

    def notificaciones_recientes(self, limit=5):
        """Obtiene notificaciones recientes"""
        return self.notificaciones.all()[:limit]

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
                retro_default = RetroalimentacionCita.obtener_retroalimentacion_default(self)
                if not retro_default:
                    return False, "No se encontró plantilla de retroalimentación predeterminada", None

                # 3. Crear retroalimentación aplicada
                retro_app = RetroalimentacionAplicada.objects.create(
                    cita=cita,
                    retroalimentacion=retro_default,
                    fecha_aplicacion=timezone.now()
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


class ThemeConfig(models.Model):
    THEME_CHOICES = [
        ('css/themes/default.css', 'Tema Default'),
        ('css/themes/dark.css', 'Tema Oscuro'),
        ('css/themes/light.css', 'Tema Claro'),
    ]

    # Configuración global
    global_theme = models.CharField(
        max_length=100,
        choices=THEME_CHOICES,
        default='css/themes/default.css'
    )

    # Permisos para otros usuarios
    allow_profesors = models.BooleanField(default=False)
    allow_padres = models.BooleanField(default=False)

    # Última modificación
    last_updated_by_id = models.PositiveIntegerField(null=True, blank=True)
    last_updated_by_type = models.CharField(max_length=20, null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de Tema"

    @property
    def last_updated_by(self):
        if not self.last_updated_by_id or not self.last_updated_by_type:
            return None

        # Mapeo dinámico sin imports circulares
        model_map = {
            'servicio': 'servicios_escolares.ServicioEscolar',
            'profesor': 'profesores.Profesor',
            'padre': 'padres.Padre'
        }

        try:
            from django.apps import apps
            model = apps.get_model(model_map[self.last_updated_by_type])
            return model.objects.filter(id=self.last_updated_by_id).first()
        except (LookupError, ImportError):
            return None

    def set_last_updated_by(self, user_obj):
        type_map = {
            'ServicioEscolar': 'servicio',
            'Profesor': 'profesor',
            'Padre': 'padre'
        }

        model_name = user_obj.__class__.__name__
        if model_name in type_map:
            self.last_updated_by_type = type_map[model_name]
            self.last_updated_by_id = user_obj.id

    @classmethod
    def can_user_change_theme(cls, user_obj):
        if user_obj is None:
            return False

        config = cls.objects.first()
        if not config:
            return False

        # Usamos el nombre de la clase para evitar isinstance
        user_class = user_obj.__class__.__name__

        if user_class == 'ServicioEscolar':
            return True
        elif user_class == 'Profesor':
            return config.allow_profesors
        elif user_class == 'Padre':
            return config.allow_padres
        return False


'''
    def marcar_cita_como_completada(self, cita):
        """Marca una cita como completada con validación robusta de fechas"""
        with transaction.atomic():
            try:
                # Validación de permisos
                if not (cita.servicio_escolar == self or self in cita.asistentes_servicio.all()):
                    return False, "No tienes permiso", None

                if cita.estado == 'completada':
                    return False, "Ya está completada", None

                # Validación EXTRA ROBUSTA de fecha_hora_fin
                if not isinstance(cita.fecha_hora_fin, datetime):  # Usa datetime directamente
                    # Si no es datetime, forzar recálculo
                    if cita.fecha_hora_inicio and cita.duracion:
                        cita.fecha_hora_fin = cita.fecha_hora_inicio + timedelta(minutes=int(cita.duracion))
                        cita.save()
                    else:
                        return False, "Fecha inválida", None

                # Comparación SEGURA con timezone.now()
                if cita.fecha_hora_fin > timezone.now():
                    return False, "No puedes completar citas futuras", None

                # Marcar como completada
                cita.estado = 'completada'
                cita.save()

                # Crear retroalimentación si no existe
                if not hasattr(cita, 'retroalimentacion'):
                    from formularios.models import RetroalimentacionAplicada
                    retro = RetroalimentacionAplicada.objects.create(
                        cita=cita,
                        retroalimentacion=RetroalimentacionCita.obtener_retroalimentacion_default(self),
                        fecha_aplicacion=timezone.now(),
                        completada=False
                    )
                    return True, "Cita completada", retro

                return True, "Cita actualizada", None

            except Exception as e:
                return False, f"Error: {str(e)}", None
'''
