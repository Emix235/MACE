import os
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.validators import FileExtensionValidator
from django.db import models
from notificaciones.models import Notification
from servicios_escolares.models import ThemeConfig


# nombre_usuario = models.CharField(max_length=100)


def user_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid4().hex}.{ext}"
    return os.path.join('users', 'padres', str(instance.id), filename)


User = get_user_model()


class Padre(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='padre', null=True, blank=True)
    nombre_completo = models.CharField(max_length=200)
    apellidos = models.CharField(max_length=200)
    correo_electronico = models.EmailField()
    contraseña = models.CharField(max_length=100)
    telefono_principal = models.CharField(max_length=20)
    telefono_respaldo = models.CharField(max_length=20, blank=True, null=True)
    rol_usuario = models.CharField(max_length=50, default='Padre')
    estado_cuenta = models.CharField(max_length=50)
    fecha_registro = models.DateField()
    ultima_fecha_sesion = models.DateField(blank=True, null=True)
    imagen_usuario = models.ImageField(
        upload_to=user_image_path,
        blank=True,
        null=True,
        verbose_name="Imagen de perfil",
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png'])]  # Agregar campo de imagen
    )
    datos_personales = models.TextField(blank=True, null=True)

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
        return f"{self.nombre_completo} {self.apellidos}"

    def get_notificaciones(self):
        content_type = ContentType.objects.get_for_model(self)
        return Notification.objects.filter(
            recipient_ct=content_type,
            recipient_id=self.id
        ).order_by('-created_at')

    def notificaciones_no_leidas(self):
        return self.get_notificaciones().filter(is_read=False)
