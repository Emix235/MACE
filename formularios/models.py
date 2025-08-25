from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# -------- ENCUESTAS GLOBALES --------- ####


class Encuesta(models.Model):
    """Modelo principal para las encuestas de satisfacción"""
    titulo = models.CharField(max_length=200, default="Encuesta de Satisfacción")
    descripcion = models.TextField(
        default="Por favor evalúa tu satisfacción con el sistema y las citas escolares"
    )
    creada_por = models.ForeignKey(
        'servicios_escolares.ServicioEscolar',  # Referencia a la app servicio_escolar
        on_delete=models.CASCADE,
        related_name='encuestas_creadas'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    ultima_edicion = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)
    es_plantilla = models.BooleanField(default=True)
    encuesta_base = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='versiones'
    )
    es_default = models.BooleanField(default=True, verbose_name="Es plantilla por defecto")

    class Meta:
        verbose_name = "Encuesta"
        verbose_name_plural = "Encuestas"
        constraints = [
            models.UniqueConstraint(
                fields=['creada_por', 'es_default'],
                condition=models.Q(es_default=True),
                name='unique_default_per_servicio'
            )
        ]

    def save(self, *args, **kwargs):
        """Asegura que solo haya una encuesta default por servicio escolar"""
        if self.es_default:
            # Desmarcar cualquier otra encuesta default para este servicio
            Encuesta.objects.filter(
                creada_por=self.creada_por,
                es_default=True
            ).exclude(pk=self.pk).update(es_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.titulo} (v{self.version})"

    @classmethod
    def obtener_encuesta_default(cls, servicio_escolar):
        """Obtiene la única encuesta default original (nunca versiones editables)"""
        try:
            # Busca específicamente la default original (sin encuesta_base)
            return cls.objects.get(
                es_default=True,
                creada_por=servicio_escolar,
                encuesta_base__isnull=True
            )
        except cls.DoesNotExist:
            # Si no existe, crea la verdadera default original
            encuesta = cls.objects.create(
                titulo="Encuesta de Satisfacción",
                descripcion="Por favor evalúa tu satisfacción con el sistema y las citas escolares",
                es_default=True,  # Solo esta es la verdadera default
                creada_por=servicio_escolar,
                es_plantilla=True,
                # encuesta_base permanece null porque es la original
            )
            encuesta.crear_preguntas_por_defecto()
            return encuesta
        except cls.MultipleObjectsReturned:
            # En caso de múltiples, tomar la más antigua como verdadera default
            return cls.objects.filter(
                es_default=True,
                creada_por=servicio_escolar,
                encuesta_base__isnull=True
            ).earliest('fecha_creacion')

    def crear_nueva_version(self):
        """Crea una nueva versión editable basada en esta encuesta"""
        # La nueva versión NO es default, solo la original lo es
        nueva_version = Encuesta.objects.create(
            titulo=self.titulo,
            descripcion=self.descripcion,
            creada_por=self.creada_por,
            version=self.version + 1,
            es_plantilla=True,
            es_default=False,  # ¡Importante! Las versiones no son defaults
            encuesta_base=self.encuesta_base or self  # Mantener referencia a la original
        )

        # Clonar preguntas
        for pregunta in self.preguntas.all():
            Pregunta.objects.create(
                encuesta=nueva_version,
                texto=pregunta.texto,
                tipo=pregunta.tipo,
                orden=pregunta.orden,
                obligatoria=pregunta.obligatoria
            )
        return nueva_version

    def crear_preguntas_por_defecto(self):
        """Crea preguntas por defecto si es la primera vez"""
        if not self.preguntas.exists():
            preguntas_defecto = [
                ("¿Qué tan fácil fue navegar y usar el sistema de agendamiento de citas?", "escala_5", 1),
                ("¿El sistema te permitió encontrar horarios disponibles de manera clara?", "escala_5", 2),
                ("¿Qué tan intuitivo fue el proceso de selección de profesor/materia para la cita?", "escala_5", 3),
                ("¿Recibiste confirmación clara de la cita agendada (correo/notificación)?", "escala_5", 4),
                ("¿La interfaz para reagendar o cancelar citas es fácil de usar?", "escala_5", 5),
                ("¿El sistema mostró toda la información necesaria sobre la cita (profesor, horario, motivo)?",
                 "escala_5", 6),
                ("¿El tiempo de espera para cargar las páginas del sistema fue adecuado?", "escala_5", 7),
                (
                    "¿El sistema te permitió agendar citas en horarios que se ajustan a tu disponibilidad?", "escala_5",
                    8),
                ("¿Recomendarías este sistema de citas escolares a otros padres/profesores?", "si_no", 9),
                ("¿Tuviste algún problema técnico al usar el sistema? Si es así, descríbelo:", "texto", 10),
                ("¿Qué sugerencias de mejora tienes para el sistema de citas escolares?", "texto", 11)
            ]

            for texto, tipo, orden in preguntas_defecto:
                Pregunta.objects.create(
                    encuesta=self,
                    texto=texto,
                    tipo=tipo,
                    orden=orden
                )


class Pregunta(models.Model):
    """Preguntas que componen la encuesta"""
    TIPO_RESPUESTA_CHOICES = [
        ('escala_5', 'Escala del 1 al 5'),
        ('si_no', 'Sí/No'),
        ('texto', 'Respuesta abierta'),
    ]

    encuesta = models.ForeignKey(
        Encuesta,
        on_delete=models.CASCADE,
        related_name='preguntas'
    )
    texto = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_RESPUESTA_CHOICES)
    orden = models.PositiveIntegerField(default=0)
    obligatoria = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden']
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"

    def __str__(self):
        return f"{self.texto[:50]}... ({self.get_tipo_display()})"


class EncuestaAplicada(models.Model):
    """Registro de cuándo se aplicó una encuesta"""
    encuesta = models.ForeignKey(
        Encuesta,
        on_delete=models.PROTECT,  # ¡Importante! Previene borrado accidental
        related_name='aplicaciones'
    )
    ciclo_escolar = models.ForeignKey(
        'estudiantes.CicloEscolar',  # Asumiendo que CicloEscolar está en la app 'academico'
        on_delete=models.CASCADE
    )
    fecha_aplicacion = models.DateTimeField(default=timezone.now)
    aplicada_por = models.ForeignKey(
        'servicios_escolares.ServicioEscolar',
        on_delete=models.SET_NULL,
        null=True
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Encuesta Aplicada"
        verbose_name_plural = "Encuestas Aplicadas"

    def __str__(self):
        return f"{self.encuesta} - Ciclo {self.ciclo_escolar}"

    def save(self, *args, **kwargs):
        """Asegura que solo se apliquen versiones finales"""
        if self.encuesta.es_plantilla:
            raise ValueError("No se puede aplicar una plantilla, debe ser una versión final")
        super().save(*args, **kwargs)


class Respuesta(models.Model):
    """Respuestas de los usuarios a las encuestas"""
    encuesta_aplicada = models.ForeignKey(
        EncuestaAplicada,
        on_delete=models.PROTECT
    )
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.PROTECT
    )

    # Relaciones con las apps de usuarios
    profesor = models.ForeignKey(
        'profesores.Profesor',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    padre = models.ForeignKey(
        'padres.Padre',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    valor_texto = models.TextField(null=True, blank=True)
    valor_numero = models.IntegerField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Respuesta"
        verbose_name_plural = "Respuestas"

    def __str__(self):
        usuario = self.profesor if self.profesor else self.padre
        return f"Respuesta de {usuario} a {self.pregunta.texto[:30]}..."

    @property
    def respondiente(self):
        """Devuelve el objeto Profesor o Padre que respondió"""
        return self.profesor or self.padre

    @property
    def nombre_respondiente(self):
        """Devuelve el nombre completo del respondiente"""
        if self.profesor:
            return f"Prof. {self.profesor.nombre_completo} {self.profesor.apellidos}"
        elif self.padre:
            return f"{self.padre.nombre_completo} {self.padre.apellidos}"
        return "Anónimo"

    @property
    def tipo_respondiente(self):
        """Devuelve el tipo de usuario (Profesor/Padre)"""
        if self.profesor:
            return "Profesor"
        elif self.padre:
            return "Padre"
        return "Anónimo"

    @property
    def hora_respuesta(self):
        """Devuelve la hora formateada de la respuesta"""
        return self.fecha_respuesta.strftime("%d/%m/%Y %H:%M")


# -------- RETROALIMENTACIÓN --------- ####


class RetroalimentacionCita(models.Model):
    """Modelo para retroalimentación de citas escolares"""
    titulo = models.CharField(max_length=200, default="Retroalimentación de Cita")
    descripcion = models.TextField(
        default="Por favor comparte tu experiencia sobre la cita realizada"
    )
    creada_por = models.ForeignKey(
        'servicios_escolares.ServicioEscolar',
        on_delete=models.CASCADE,
        related_name='retroalimentaciones_creadas'
    )
    es_para_profesor = models.BooleanField(
        default=False,
        verbose_name="¿Es para citas con profesores?"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    ultima_edicion = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)
    es_plantilla = models.BooleanField(default=True)
    retroalimentacion_base = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='versiones'
    )
    es_default = models.BooleanField(default=True, verbose_name="Es plantilla por defecto")

    class Meta:
        verbose_name = "Retroalimentación de Cita"
        verbose_name_plural = "Retroalimentaciones de Citas"

    def __str__(self):
        return f"{self.titulo} (v{self.version})"

    def crear_nueva_version(self):
        """Crea una nueva versión editable manteniendo los datos históricos"""
        # Desmarcar cualquier versión default anterior
        if self.es_default:
            RetroalimentacionCita.objects.filter(
                creada_por=self.creada_por,
                es_default=True
            ).update(es_default=False)

        nueva_version = RetroalimentacionCita.objects.create(
            titulo=self.titulo,
            descripcion=self.descripcion,
            creada_por=self.creada_por,
            version=self.version + 1,
            es_plantilla=True,
            es_default=True,  # La nueva versión se convierte en la default
            retroalimentacion_base=self.retroalimentacion_base or self
        )

        # Clonar preguntas manteniendo referencia al original
        for pregunta in self.preguntas.all():
            PreguntaRetroalimentacion.objects.create(
                retroalimentacion=nueva_version,
                texto=pregunta.texto,
                tipo=pregunta.tipo,
                orden=pregunta.orden,
                obligatoria=pregunta.obligatoria,
                permite_explicacion=pregunta.permite_explicacion
            )

        return nueva_version

    def historial(self):
        base = self.retroalimentacion_base or self
        return base.versiones.order_by('version')

    @classmethod
    def obtener_retroalimentacion_default(cls, servicio_escolar, para_profesor=False):
        """Obtiene la plantilla default, asegurando que solo exista una"""
        if para_profesor:
            print("Buscando plantilla default PARA PROFESOR...")

            primera = cls.objects.filter(
                creada_por=servicio_escolar,
                es_para_profesor=True,
                es_default=True
            ).first()

            if primera:
                cls.objects.filter(
                    creada_por=servicio_escolar,
                    es_para_profesor=True,
                    es_default=True
                ).exclude(pk=primera.pk).update(es_default=False)

                print("Plantilla profesor ya existente:", primera)
                return primera

            # Si no existe, se crea una
            retro, creado = cls.objects.get_or_create(
                es_default=True,
                es_para_profesor=True,
                creada_por=servicio_escolar,
                defaults={
                    'titulo': "Retroalimentación de Cita con Profesor",
                    'descripcion': "Por favor evalúe su experiencia con el profesor",
                }
            )
            print("Plantilla PROFESOR creada:", retro, "¿Fue creada?", creado)
            if creado:
                retro.crear_preguntas_para_profesor()
            return retro

        # --- MISMO CÓDIGO PARA SERVICIO ESCOLAR (ya funcionaba bien) ---
        print("Buscando plantilla default para SERVICIO ESCOLAR...")

        primera = cls.objects.filter(
            creada_por=servicio_escolar,
            es_para_profesor=False,
            es_default=True
        ).first()

        if primera:
            cls.objects.filter(
                creada_por=servicio_escolar,
                es_para_profesor=False,
                es_default=True
            ).exclude(pk=primera.pk).update(es_default=False)

        retro, created = cls.objects.get_or_create(
            es_default=True,
            es_para_profesor=False,
            creada_por=servicio_escolar,
            defaults={
                'titulo': "Retroalimentación de Cita",
                'descripcion': "Por favor comparte tu experiencia sobre la cita realizada",
            }
        )

        print("Plantilla SERVICIO ESCOLAR:", retro, "¿Fue creada?", created)

        if created:
            print("Plantilla default recién creada. Generando preguntas por defecto...")
            retro.crear_preguntas_por_defecto()
        else:
            print("La plantilla ya existía. No se generan preguntas.")

        return retro

    def crear_preguntas_por_defecto(self):
        """Crea preguntas por defecto si es la primera vez"""
        print(f"Llamado a crear_preguntas_por_defecto para retroalimentación ID {self.id}")
        if not self.preguntas.exists():
            print("No existen preguntas asociadas. Creando preguntas por defecto...")
            preguntas_defecto = [
                ("¿La cita resolvió tu necesidad o inquietud?", "si_no", 1, True, False),
                ("¿Te sentiste escuchado y atendido adecuadamente?", "escala_5", 2, True, False),
                ("¿La duración de la cita fue suficiente?", "escala_5", 3, False, False),
                ("¿Hubo algún problema técnico (si fue virtual)?", "si_no_explicacion", 4, False, True),
                ("¿Recomendarías este servicio a otros padres?", "si_no", 5, True, False),
                ("Comentarios o sugerencias (opcional):", "texto", 6, False, False),
            ]

            for texto, tipo, orden, obligatoria, permite_explicacion in preguntas_defecto:
                print(f"Creando pregunta: {texto} (tipo={tipo})")
                PreguntaRetroalimentacion.objects.create(
                    retroalimentacion=self,
                    texto=texto,
                    tipo=tipo,
                    orden=orden,
                    obligatoria=obligatoria,
                    permite_explicacion=permite_explicacion
                )
        else:
            print("Ya existen preguntas asociadas. No se crearán duplicados.")

    @classmethod
    def obtener_plantilla_para_profesor(cls, profesor):
        from servicios_escolares.models import ServicioEscolar

        # Obtener el primer ServicioEscolar registrado
        servicio_escolar = ServicioEscolar.objects.first()
        if not servicio_escolar:
            raise ValueError("No hay ningún Servicio Escolar registrado")

        retro, created = cls.objects.get_or_create(
            es_default=True,
            es_para_profesor=True,
            creada_por=servicio_escolar,
            defaults={
                'titulo': "Retroalimentación de Cita con Profesor",
                'descripcion': "Por favor evalúe su experiencia con el profesor",
            }
        )
        if created:
            retro.crear_preguntas_para_profesor()
        return retro

    def crear_preguntas_para_profesor(self):
        """Preguntas específicas para citas con profesores"""
        if self.preguntas.exists():
            return

        preguntas = [
            ("¿El profesor brindó la atención necesaria?", "si_no_explicacion", 1, True, False),
            ("¿Las explicaciones fueron claras y comprensibles?", "escala_5", 2, True, False),
            ("¿El profesor mostró interés en resolver tus dudas?", "escala_5", 3, True, False),
            ("¿Recomendarías este profesor a otros padres?", "si_no", 4, True, True),
            ("Comentarios adicionales:", "texto", 5, False, False)
        ]

        for texto, tipo, orden, obligatoria, permite_explicacion in preguntas:
            PreguntaRetroalimentacion.objects.create(
                retroalimentacion=self,
                texto=texto,
                tipo=tipo,
                orden=orden,
                obligatoria=obligatoria,
                permite_explicacion=permite_explicacion
            )


class PreguntaRetroalimentacion(models.Model):
    """Preguntas para la retroalimentación de citas"""
    TIPO_RESPUESTA_CHOICES = [
        ('escala_5', 'Escala del 1 al 5'),
        ('si_no', 'Sí/No'),
        ('si_no_explicacion', 'Sí/No con explicación'),
        ('texto', 'Respuesta abierta'),
    ]

    retroalimentacion = models.ForeignKey(
        RetroalimentacionCita,
        on_delete=models.CASCADE,
        related_name='preguntas'
    )
    texto = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_RESPUESTA_CHOICES)
    orden = models.PositiveIntegerField(default=0)
    obligatoria = models.BooleanField(default=True)
    permite_explicacion = models.BooleanField(
        default=False,
        help_text="Si es Sí/No, ¿permite explicación adicional?"
    )
    pregunta_original = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nuevas_versiones',
        verbose_name="Pregunta original"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    fecha_modificacion = models.DateTimeField(auto_now=True, blank=True, null=True)
    activa = models.BooleanField(default=True, help_text="¿Esta pregunta está activa en el formulario?")

    class Meta:
        ordering = ['orden']
        verbose_name = "Pregunta de Retroalimentación"
        verbose_name_plural = "Preguntas de Retroalimentación"

    class Meta:
        ordering = ['orden']
        verbose_name = "Pregunta de Retroalimentación"
        verbose_name_plural = "Preguntas de Retroalimentación"

    def __str__(self):
        return f"{self.texto[:50]}... ({self.get_tipo_display()})"

    def clean(self):
        """Asegura coherencia entre tipo y permite_explicacion"""
        if self.tipo == 'si_no_explicacion' and not self.permite_explicacion:
            self.permite_explicacion = True
        elif self.tipo in ['si_no', 'escala_5'] and self.permite_explicacion:
            self.permite_explicacion = False

    def delete(self, *args, **kwargs):
        """Sobrescribir delete para manejar eliminación segura"""
        if RespuestaRetroalimentacion.objects.filter(pregunta=self).exists():
            # En lugar de eliminar, marcamos como inactiva
            self.activa = False
            self.save()
        else:
            super().delete(*args, **kwargs)


class RetroalimentacionAplicada(models.Model):
    """Registro de retroalimentación aplicada a una cita específica"""
    cita = models.OneToOneField(
        'citas.Cita',
        on_delete=models.CASCADE,
        related_name='retroalimentacion',
        verbose_name="Cita asociada"
    )
    profesor = models.ForeignKey(
        'profesores.Profesor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='retroalimentaciones_recibidas'
    )
    retroalimentacion = models.ForeignKey(
        RetroalimentacionCita,
        on_delete=models.PROTECT,
        related_name='aplicaciones',
        verbose_name="Plantilla de retroalimentación"
    )
    fecha_aplicacion = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha de envío"
    )
    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de respuesta"
    )
    completada = models.BooleanField(
        default=False,
        verbose_name="¿Completada?"
    )

    class Meta:
        verbose_name = "Retroalimentación Aplicada"
        verbose_name_plural = "Retroalimentaciones Aplicadas"
        ordering = ['-fecha_aplicacion']

    def __str__(self):
        return f"Retroalimentación para cita #{self.cita.id} ({self.cita.solicitante})"

    @property
    def padre(self):
        """Acceso directo al padre asociado"""
        return self.cita.solicitante

    @property
    def titulo_cita(self):
        """Título de la cita asociada"""
        return self.cita.titulo

    @property
    def fecha_cita(self):
        """Fecha de la cita asociada"""
        return self.cita.fecha_hora_inicio

    @property
    def estado_retroalimentacion(self):
        """Estado legible de la retroalimentación"""
        return "Completada" if self.completada else "Pendiente"

    def marcar_como_completada(self):
        """Marca la retroalimentación como completada"""
        if not self.completada:
            self.completada = True
            self.fecha_respuesta = timezone.now()
            self.save(update_fields=['completada', 'fecha_respuesta'])
            return True
        return False

    def obtener_respuestas(self):
        """Devuelve todas las respuestas asociadas"""
        return self.respuestas.all().select_related('pregunta')

# 👈 Agrega esto
class RespuestaRetroalimentacion(models.Model):
    """Respuestas a la retroalimentación de citas"""
    retroalimentacion_aplicada = models.ForeignKey(
        RetroalimentacionAplicada,
        on_delete=models.CASCADE,
        related_name='respuestas',
        verbose_name="Retroalimentación aplicada"
    )
    pregunta = models.ForeignKey(
        PreguntaRetroalimentacion,
        on_delete=models.PROTECT,
        verbose_name="Pregunta",
        related_name='respuestas', #<-
    )
    padre = models.ForeignKey(
        'padres.Padre',
        on_delete=models.CASCADE,
        related_name='respuestas_retroalimentacion',
        verbose_name="Padre que respondió"
    )

    # Campos para diferentes tipos de respuesta
    valor_numero = models.IntegerField(
        null=True,
        blank=True,
        help_text="Valor numérico para preguntas de escala"
    )
    respuesta_si_no = models.BooleanField(
        null=True,
        blank=True,
        help_text="Respuesta Sí/No"
    )
    explicacion = models.TextField(
        null=True,
        blank=True,
        help_text="Explicación adicional para respuestas Sí/No"
    )
    respuesta_texto = models.TextField(
        null=True,
        blank=True,
        help_text="Respuesta de texto libre"
    )
    fecha_respuesta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Respuesta de Retroalimentación"
        verbose_name_plural = "Respuestas de Retroalimentación"
        unique_together = ('retroalimentacion_aplicada', 'pregunta', 'padre')
        ordering = ['pregunta__orden']

    def __str__(self):
        padre = getattr(self, 'padre', None)
        pregunta = getattr(self, 'pregunta', None)

        if padre and pregunta:
            return f"Respuesta de {padre.nombre_completo} a pregunta #{pregunta.id}"
        return "Respuesta incompleta"

    def clean(self):
        """Valida que solo el padre solicitante de la cita pueda responder"""
        super().clean()

        if not self.padre or not self.retroalimentacion_aplicada or not self.pregunta:
            return  # Evita validación si aún no se asignaron relaciones completas

        if self.padre != self.retroalimentacion_aplicada.cita.solicitante:
            raise ValidationError("Solo el padre solicitante de la cita puede completar esta retroalimentación")

        """Valida que la respuesta coincida con el tipo de pregunta"""
        if self.pregunta.tipo == 'escala_5':
            if self.valor_numero is None:
                raise ValidationError("Esta pregunta requiere una valoración del 1 al 5")
            if not (1 <= self.valor_numero <= 5):
                raise ValidationError("La valoración debe estar entre 1 y 5")

        elif self.pregunta.tipo == 'si_no' and self.respuesta_si_no is None:
            raise ValidationError("Esta pregunta requiere una respuesta Sí/No")

        elif self.pregunta.tipo == 'si_no_explicacion':
            if self.respuesta_si_no is None:
                raise ValidationError("Esta pregunta requiere una respuesta Sí/No")
            if self.pregunta.permite_explicacion and not self.explicacion:
                raise ValidationError("Esta pregunta requiere una explicación")

        elif self.pregunta.tipo == 'texto' and not self.respuesta_texto:
            raise ValidationError("Esta pregunta requiere una respuesta de texto")

    @property
    def respuesta_completa(self):
        """Devuelve la respuesta formateada según el tipo de pregunta"""
        if self.pregunta.tipo == 'escala_5':
            return f"{self.valor_numero}/5"
        elif self.pregunta.tipo == 'si_no':
            return "Sí" if self.respuesta_si_no else "No"
        elif self.pregunta.tipo == 'si_no_explicacion':
            return f"{'Sí' if self.respuesta_si_no else 'No'}: {self.explicacion}"
        return self.respuesta_texto

    @property
    def cita_asociada(self):
        """Acceso directo a la cita asociada"""
        return self.retroalimentacion_aplicada.cita

    @property
    def tipo_cita(self):
        """Tipo de cita asociada"""
        return self.retroalimentacion_aplicada.cita.get_tipo_display()

    def marcar_como_respondida(self, texto_respuesta):
        self.respuesta = texto_respuesta
        self.fecha_respuesta = timezone.now()
        self.save(update_fields=['respuesta', 'fecha_respuesta'])





