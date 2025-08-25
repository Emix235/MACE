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

    rol = models.CharField(max_length=20, choices=ROL_CHOICES)  # Este campo debe existir
    pregunta = models.CharField(max_length=255)
    respuesta = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pregunta y Respuesta'
        verbose_name_plural = 'Preguntas y Respuestas'
        ordering = ['rol', 'pregunta']
        unique_together = ('rol', 'pregunta')  # Evita duplicados por rol

    def __str__(self):
        return f"{self.rol}: {self.pregunta[:50]}..."


class HistorialAyuda(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='preguntas_ayuda')
    rol_usuario = models.CharField(max_length=50)  # Guardamos el rol al momento de la pregunta
    pregunta = models.TextField()
    respuesta = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    fue_util = models.BooleanField(null=True, blank=True)  # Para valoración posterior

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Historial de Ayuda'
        verbose_name_plural = 'Historiales de Ayuda'

    def __str__(self):
        return f"{self.usuario} ({self.rol_usuario}): {self.pregunta[:30]}..."