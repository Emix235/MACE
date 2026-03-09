from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class PreguntaRespuesta(models.Model):
    ROL_CHOICES = [
        ('padre', 'Padre'),
        ('profesor', 'Profesor'),
        ('servicio', 'Servicio Escolar'),
        ('general', 'General'),
    ]

    rol = models.CharField(max_length=20, choices=ROL_CHOICES)
    pregunta = models.CharField(max_length=255)
    respuesta = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField(default=True)  # NUEVO
    orden = models.IntegerField(default=0)  # NUEVO

    class Meta:
        verbose_name = 'Pregunta y Respuesta'
        verbose_name_plural = 'Preguntas y Respuestas'
        ordering = ['rol', 'orden', 'pregunta']
        unique_together = ('rol', 'pregunta')

    def __str__(self):
        return f"{self.rol}: {self.pregunta[:50]}..."

    # AÑADE ESTOS MÉTODOS:
    @classmethod
    def get_preguntas_por_rol(cls, rol):
        """Obtiene preguntas activas para un rol específico"""
        return cls.objects.filter(rol=rol, activa=True).order_by('orden', 'pregunta')

    @classmethod
    def get_preguntas_generales(cls):
        """Obtiene preguntas generales activas"""
        return cls.objects.filter(rol='general', activa=True).order_by('orden', 'pregunta')


class HistorialAyuda(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='preguntas_ayuda')
    rol_usuario = models.CharField(max_length=50)
    pregunta = models.TextField()
    respuesta = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    fue_util = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Historial de Ayuda'
        verbose_name_plural = 'Historiales de Ayuda'

    def __str__(self):
        return f"{self.usuario} ({self.rol_usuario}): {self.pregunta[:30]}..."
