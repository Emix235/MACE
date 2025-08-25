from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Nota(models.Model):
    TIPO_NOTA_CHOICES = [
        ('general', 'General'),
        ('academica', 'Académica'),
        ('conducta', 'Conducta'),
        ('administrativa', 'Administrativa'),
    ]

    titulo = models.CharField(max_length=100, verbose_name="Título")
    contenido = models.TextField(verbose_name="Contenido")
    fecha_creacion = models.DateTimeField(default=timezone.now, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    tipo = models.CharField(max_length=20, choices=TIPO_NOTA_CHOICES, default='general', verbose_name="Tipo de nota")

    # Relación con el creador (especificando la app de origen)
    creador_padre = models.ForeignKey('padres.Padre', on_delete=models.SET_NULL,
                                      null=True, blank=True,
                                      related_name='notas_creadas_padre')
    creador_profesor = models.ForeignKey('profesores.Profesor', on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         related_name='notas_creadas_profesor')
    creador_servicio = models.ForeignKey('servicios_escolares.ServicioEscolar',
                                         on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         related_name='notas_creadas_servicio')
    # Campos para archivos adjuntos
    imagen = models.ImageField(upload_to='notas/imagenes/', blank=True, null=True, verbose_name="Imagen adjunta")
    documento = models.FileField(upload_to='notas/documentos/', blank=True, null=True, verbose_name="Documento adjunto")
    audio = models.FileField(upload_to='notas/audios/', blank=True, null=True, verbose_name="Audio adjunto")

    # Relación con destinatarios (especificando la app de origen)
    destinatario_padre = models.ForeignKey('padres.Padre', on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           related_name='notas_recibidas_padre')
    destinatario_profesor = models.ForeignKey('profesores.Profesor', on_delete=models.SET_NULL,
                                              null=True, blank=True,
                                              related_name='notas_recibidas_profesor')
    destinatario_servicio = models.ForeignKey('servicios_escolares.ServicioEscolar',
                                              on_delete=models.SET_NULL,
                                              null=True, blank=True,
                                              related_name='notas_recibidas_servicio')
    class Meta:
        verbose_name = "Nota"
        verbose_name_plural = "Notas"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.titulo} - {self.get_tipo_display()} - {self.fecha_creacion.strftime('%Y-%m-%d')}"

    def get_creador(self):
        """Devuelve la instancia del creador, sin importar su tipo"""
        if self.creador_padre:
            return self.creador_padre
        elif self.creador_profesor:
            return self.creador_profesor
        elif self.creador_servicio:
            return self.creador_servicio
        return None

    def get_creador_display(self):
        """Devuelve una representación legible del creador"""
        creador = self.get_creador()
        if creador:
            tipo = 'Padre' if self.creador_padre else 'Profesor' if self.creador_profesor else 'Servicio Escolar'
            return f"{creador.nombre_completo} ({tipo})"
        return "Desconocido"

    def get_tipo_usuario_creador(self):
        """Devuelve el tipo de usuario que creó la nota"""
        if self.creador_padre:
            return 'padre'
        elif self.creador_profesor:
            return 'profesor'
        elif self.creador_servicio:
            return 'servicio_escolar'
        return None

    def get_destinatario(self):
        if self.destinatario_padre:
            return f"{self.destinatario_padre.nombre_completo} (Padre)"
        elif self.destinatario_profesor:
            return f"{self.destinatario_profesor.nombre_completo} (Profesor)"
        elif self.destinatario_servicio:
            return f"{self.destinatario_servicio.nombre_completo} (Servicio Escolar)"
        return "General"

    @property
    def tipo_css(self):
        return 'primary' if self.tipo == 'academica' else 'secondary'

