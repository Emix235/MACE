import uuid
from datetime import date
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
import os
from uuid import uuid4
from padres.models import Padre
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
import datetime
import math


def user_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid4().hex}.{ext}"
    return os.path.join('users', 'padres', str(instance.id), filename)


# ('LIC', 'Licenciatura'),


class NivelEducativo(models.Model):
    NIVELES = [
        ('PRI', 'Primaria'),
        ('SEC', 'Secundaria'),
        ('BAC', 'Bachillerato'),
    ]

    codigo = models.CharField(
        max_length=3,
        choices=NIVELES,
        default='SEC',  # Primaria seleccionada por defecto
        unique=True
    )
    nombre = models.CharField(max_length=50, editable=False)  # Se autocompleta
    orden = models.PositiveSmallIntegerField(unique=True)

    class Meta:
        verbose_name = "Nivel Educativo"
        verbose_name_plural = "Niveles Educativos"
        ordering = ['orden']

    def save(self, *args, **kwargs):
        # Autocompletar el nombre basado en el código
        self.nombre = dict(self.NIVELES).get(self.codigo, '')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

    @property
    def grados_disponibles(self):
        """Devuelve los grados asociados a este nivel ordenados"""
        return self.grados.all().order_by('numero')

    def crear_grados_automaticamente(self):
        """Crea los grados típicos según el nivel educativo"""
        if self.codigo == 'PRI':  # Primaria: 6 grados
            for i in range(1, 7):
                Grado.objects.get_or_create(nivel=self, numero=i, nombre=f"{i}° de Primaria")
        elif self.codigo == 'SEC':  # Secundaria: 3 grados
            for i in range(1, 4):
                Grado.objects.get_or_create(nivel=self, numero=i, nombre=f"{i}° de Secundaria")
        # ... otros niveles


class PeriodoEscolar(models.Model):
    PERIODOS = [
        ('SEM', 'Semestral'),
        ('TRI', 'Trimestral'),
        ('CUA', 'Cuatrimestral'),
        ('ANL', 'Anual'),
    ]

    codigo = models.CharField(
        max_length=3,
        choices=PERIODOS,
        unique=True,
        verbose_name="Código",
        help_text="Código de 3 letras para el tipo de periodo"
    )
    nombre = models.CharField(
        max_length=20,
        editable=False,
        verbose_name="Nombre completo"
    )
    meses_duracion = models.PositiveSmallIntegerField(
        verbose_name="Duración en meses",
        editable=False
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción",
        help_text="Información adicional sobre este tipo de periodo"
    )

    class Meta:
        verbose_name = "Periodo Escolar"
        verbose_name_plural = "Periodos Escolares"
        ordering = ['meses_duracion']

    # db_table = 'periodos_escolares'
    def clean(self):
        """Validación adicional para el modelo"""
        if self.codigo not in dict(self.PERIODOS).keys():
            raise ValidationError({
                'codigo': "Código de periodo no válido"
            })

    def save(self, *args, **kwargs):
        """Autocompleta campos derivados antes de guardar"""
        self.nombre = dict(self.PERIODOS).get(self.codigo, '')

        # Asignar duración en meses según código
        duraciones = {
            'SEM': 6,
            'TRI': 3,
            'CUA': 4,
            'ANL': 12
        }
        self.meses_duracion = duraciones.get(self.codigo, 0)

        # Validación de consistencia
        if self.meses_duracion == 0:
            raise ValidationError("Duración no válida para el código especificado")

        super().save(*args, **kwargs)

    @property
    def nombre_completo(self):
        """Propiedad para obtener nombre con duración"""
        return f"{self.nombre} ({self.meses_duracion} meses)"

    def __str__(self):
        return self.nombre_completo


class CicloEscolar(models.Model):
    TIPO_DURACION_CHOICES = [
        ('TRAD', 'Tradicional (10 meses)'),
        ('CUAT', 'Cuatrimestral (12 meses)'),
        ('TRIM', 'Trimestral (12 meses)'),
        ('SEM', 'Semestral (12 meses)'),
        ('PERS', 'Personalizado'),
    ]

    nombre = models.CharField(
        max_length=9,
        unique=True,
        verbose_name="Nombre del ciclo",
        help_text="Formato: AAAA-AAAA (ej: 2023-2024)"
    )
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de término")
    tipo_duracion = models.CharField(
        max_length=4,
        choices=TIPO_DURACION_CHOICES,
        default='TRAD',
        verbose_name="Tipo de duración"
    )
    activo = models.BooleanField(
        default=False,
        verbose_name="¿Ciclo activo?"
    )
    nivel = models.ForeignKey(
        'NivelEducativo',
        on_delete=models.PROTECT,
        verbose_name="Nivel Educativo"
    )
    actual = models.BooleanField(
        default=False,
        verbose_name="¿Ciclo actual?",
        help_text="Ciclo que se está trabajando actualmente"
    )
    meses_duracion = models.PositiveSmallIntegerField(
        editable=False,
        verbose_name="Duración en meses",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Ciclo Escolar"
        verbose_name_plural = "Ciclos Escolares"
        ordering = ['-fecha_inicio']
        constraints = [
            models.UniqueConstraint(
                fields=['fecha_inicio', 'fecha_fin'],
                name='unique_fechas_ciclo'
            ),
            models.UniqueConstraint(
                fields=['actual'],
                condition=Q(actual=True),
                name='unique_ciclo_actual'
            )
        ]

    def clean(self):
        # Validación de formato del nombre
        if len(self.nombre) != 9 or self.nombre[4] != '-':
            raise ValidationError({
                'nombre': _("Formato incorrecto. Use: AAAA-AAAA (ej: 2023-2024)")
            })

        año_inicio, año_fin = self.nombre.split('-')

        # Validación de años consecutivos
        if int(año_fin) - int(año_inicio) != 1:
            raise ValidationError({
                'nombre': _("El año final debe ser exactamente 1 año después del inicial")
            })

        # Ajustar fecha_fin según tipo_duracion si no es personalizado
        if self.tipo_duracion != 'PERS':
            self.fecha_fin = self.calcular_fecha_fin()

        # Validación de coincidencia con fechas
        if self.fecha_inicio.year != int(año_inicio) or self.fecha_fin.year != int(año_fin):
            raise ValidationError({
                'nombre': _("Los años deben coincidir con las fechas de inicio/término")
            })

        # Validación de duración mínima
        if (self.fecha_fin - self.fecha_inicio).days < 180:
            raise ValidationError({
                'fecha_fin': _("La duración mínima debe ser de 6 meses")
            })

    def calcular_fecha_fin(self):
        """Calcula la fecha de fin según el tipo de duración"""
        if not self.fecha_inicio or self.tipo_duracion == 'PERS':
            return self.fecha_fin

        meses_duracion = {
            'TRAD': 10,
            'CUAT': 12,
            'TRIM': 12,
            'SEM': 12
        }.get(self.tipo_duracion, 12)

        year = self.fecha_inicio.year
        month = self.fecha_inicio.month + meses_duracion
        day = self.fecha_inicio.day

        # Ajustar año si pasamos de diciembre
        while month > 12:
            month -= 12
            year += 1

        # Asegurarnos que el día no exceda los días del mes
        # Calculamos el último día del mes
        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year

        last_day_of_month = (datetime.date(next_year, next_month, 1) - datetime.timedelta(days=1)).day
        day = min(day, last_day_of_month)

        return datetime.date(year, month, day)

    def calcular_meses_duracion(self):
        """Calcula la duración en meses redondeando hacia arriba"""
        if not self.fecha_inicio or not self.fecha_fin:
            return 0

        total_dias = (self.fecha_fin - self.fecha_inicio).days
        return math.ceil(total_dias / 30.44)  # Aproximación de días por mes

    def save(self, *args, **kwargs):
        # Calcular duración antes de guardar
        self.meses_duracion = self.calcular_meses_duracion()
        super().save(*args, **kwargs)

    def crear_grados_automaticamente(self):
        """Crea los grados según la configuración del nivel educativo"""
        if self.nivel.codigo == 'PRI':  # Primaria: 6 grados
            for i in range(1, 7):
                Grado.objects.get_or_create(
                    ciclo=self,
                    nivel=self.nivel,
                    numero=i,
                    defaults={'nombre': f"{i}° de Primaria"}
                )
        elif self.nivel.codigo == 'SEC':  # Secundaria: 3 grados
            for i in range(1, 4):
                Grado.objects.get_or_create(
                    ciclo=self,
                    nivel=self.nivel,
                    numero=i,
                    defaults={'nombre': f"{i}° de Secundaria"}
                )
        # ... otros niveles

    def crear_periodos_automaticamente(self):
        """Crea los periodos escolares según el tipo de duración"""
        from .models import PeriodoEscolar
        PeriodoEscolar.objects.filter(ciclo=self).delete()

        if not self.fecha_inicio or not self.fecha_fin:
            return

        if self.tipo_duracion == 'TRAD':  # Tradicional (2 semestres)
            # Primer semestre (5 meses)
            fin_sem1 = self.calcular_fecha_con_meses(self.fecha_inicio, 5)

            PeriodoEscolar.objects.create(
                ciclo=self,
                nombre="Primer Semestre",
                fecha_inicio=self.fecha_inicio,
                fecha_fin=fin_sem1,
                orden=1
            )

            # Segundo semestre
            inicio_sem2 = fin_sem1 + datetime.timedelta(days=1)
            PeriodoEscolar.objects.create(
                ciclo=self,
                nombre="Segundo Semestre",
                fecha_inicio=inicio_sem2,
                fecha_fin=self.fecha_fin,
                orden=2
            )

        elif self.tipo_duracion == 'CUAT':  # 3 cuatrimestres
            for i in range(3):
                inicio = self.calcular_fecha_con_meses(self.fecha_inicio, i * 4)
                fin = self.calcular_fecha_con_meses(inicio, 4)

                PeriodoEscolar.objects.create(
                    ciclo=self,
                    nombre=f"Cuatrimestre {i + 1}",
                    fecha_inicio=inicio,
                    fecha_fin=fin - datetime.timedelta(days=1),
                    orden=i + 1
                )

        elif self.tipo_duracion == 'TRIM':  # 4 trimestres
            for i in range(4):
                inicio = self.calcular_fecha_con_meses(self.fecha_inicio, i * 3)
                fin = self.calcular_fecha_con_meses(inicio, 3)

                PeriodoEscolar.objects.create(
                    ciclo=self,
                    nombre=f"Trimestre {i + 1}",
                    fecha_inicio=inicio,
                    fecha_fin=fin - datetime.timedelta(days=1),
                    orden=i + 1
                )

        elif self.tipo_duracion == 'SEM':  # 2 semestres (12 meses)
            # Primer semestre (6 meses)
            fin_sem1 = self.calcular_fecha_con_meses(self.fecha_inicio, 6)

            PeriodoEscolar.objects.create(
                ciclo=self,
                nombre="Primer Semestre",
                fecha_inicio=self.fecha_inicio,
                fecha_fin=fin_sem1 - datetime.timedelta(days=1),
                orden=1
            )

            # Segundo semestre
            inicio_sem2 = fin_sem1
            PeriodoEscolar.objects.create(
                ciclo=self,
                nombre="Segundo Semestre",
                fecha_inicio=inicio_sem2,
                fecha_fin=self.fecha_fin,
                orden=2
            )

    def obtener_periodos(self):
        """Devuelve los periodos escolares según el tipo de duración"""
        periodos = []
        meses_por_periodo = {
            'TRAD': {'Primer Semestre': 5, 'Segundo Semestre': 5},
            'CUAT': {'Primer Cuatrimestre': 4, 'Segundo Cuatrimestre': 4, 'Tercer Cuatrimestre': 4},
            'TRIM': {'Primer Trimestre': 3, 'Segundo Trimestre': 3, 'Tercer Trimestre': 3, 'Cuarto Trimestre': 3},
            'SEM': {'Primer Semestre': 6, 'Segundo Semestre': 6},
            'PERS': {'Anual': 12}
        }

        tipo = self.tipo_duracion
        if tipo not in meses_por_periodo:
            return []

        fecha_actual = self.fecha_inicio
        for nombre, meses in meses_por_periodo[tipo].items():
            fecha_fin = self.calcular_fecha_con_meses(fecha_actual, meses)
            if fecha_fin > self.fecha_fin:
                fecha_fin = self.fecha_fin

            periodos.append({
                'nombre': nombre,
                'fecha_inicio': fecha_actual,
                'fecha_fin': fecha_fin,
                'meses': meses
            })

            fecha_actual = fecha_fin + datetime.timedelta(days=1)
            if fecha_actual > self.fecha_fin:
                break

        return periodos

    def periodo_actual(self, fecha=None):
        """Devuelve el periodo escolar actual para una fecha dada (o hoy)"""
        fecha = fecha or datetime.date.today()
        for periodo in self.obtener_periodos():
            if periodo['fecha_inicio'] <= fecha <= periodo['fecha_fin']:
                return periodo
        return None

    def periodo_por_nombre(self, nombre_periodo):
        """Busca un periodo por su nombre"""
        for periodo in self.obtener_periodos():
            if periodo['nombre'] == nombre_periodo:
                return periodo
        return None

    def calcular_fecha_con_meses(self, fecha_base, meses):
        """Calcula una fecha sumando meses a una fecha base"""
        year = fecha_base.year
        month = fecha_base.month + meses
        day = fecha_base.day

        # Ajustar año si pasamos de diciembre
        while month > 12:
            month -= 12
            year += 1

        # Asegurarnos que el día no exceda los días del mes
        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year

        last_day_of_month = (datetime.date(next_year, next_month, 1) - datetime.timedelta(days=1)).day
        day = min(day, last_day_of_month)

        return datetime.date(year, month, day)

    @property
    def años(self):
        año_inicio, año_fin = self.nombre.split('-')
        return (int(año_inicio), int(año_fin))

    @property
    def duracion_formateada(self):
        meses = self.meses_duracion
        if meses == 12:
            return "1 año"
        elif meses > 12:
            años = meses // 12
            meses_restantes = meses % 12
            return f"{años} año{'s' if años > 1 else ''} y {meses_restantes} mes{'es' if meses_restantes != 1 else ''}"
        return f"{meses} mes{'es' if meses != 1 else ''}"

    def __str__(self):
        return f"{self.nombre} - {self.duracion_formateada} ({self.get_tipo_duracion_display()})"

    @classmethod
    def obtener_actual(cls):
        return cls.objects.filter(actual=True).first()


@receiver(pre_save, sender=CicloEscolar)
def gestionar_ciclo_actual(sender, instance, **kwargs):
    if instance.actual:
        sender.objects.exclude(pk=instance.pk).filter(actual=True).update(actual=False)


class Grado(models.Model):
    ciclo = models.ForeignKey(
        'CicloEscolar',
        on_delete=models.CASCADE,
        related_name='grados_del_ciclo',
        verbose_name="Ciclo Escolar",
        null=True, blank=True
    )
    nivel = models.ForeignKey(
        NivelEducativo,
        on_delete=models.CASCADE,
        related_name='grados_por_nivel'
    )
    numero = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Número del grado (1 a 12)"
    )
    nombre = models.CharField(
        max_length=30,
        blank=True,
        help_text="Ej: Primer grado, Segundo año"
    )

    class Meta:
        verbose_name = "Grado"
        verbose_name_plural = "Grados"
        unique_together = ('ciclo', 'nivel', 'numero')  # Modificado
        ordering = ['nivel__orden', 'numero']

    def __str__(self):
        return f"{self.numero}° {self.nivel.nombre} - {self.ciclo.nombre}"


class Grupo(models.Model):
    TURNOS = [
        ('M', 'Matutino'),
        ('V', 'Vespertino'),
        ('C', 'Completo'),
    ]

    grado = models.ForeignKey(Grado, on_delete=models.PROTECT, related_name='grupos')
    ciclo = models.ForeignKey(CicloEscolar, on_delete=models.CASCADE)
    letra = models.CharField(
        max_length=1,
        help_text="Letra identificadora (A, B, C...)"
    )
    turno = models.CharField(
        max_length=1,
        choices=TURNOS,
        default='M'  # Matutino por defecto
    )
    capacidad = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(10), MaxValueValidator(50)]
    )
    aula = models.CharField(
        max_length=10,
        blank=True,
        help_text="Número o identificador del aula"
    )

    class Meta:
        verbose_name = "Grupo"
        verbose_name_plural = "Grupos"
        unique_together = ('grado', 'ciclo', 'letra', 'turno')
        ordering = ['grado__nivel__orden', 'grado__numero', 'letra']

    def __str__(self):
        return f"{self.grado} {self.letra} ({self.get_turno_display()}) - {self.ciclo.nombre}"

    def estudiantes_activos(self):
        """Devuelve solo los estudiantes activos en el grupo"""
        return self.estudiantes.filter(activo=True)

    def promedio_edad(self):
        """Calcula el promedio de edad de los estudiantes en el grupo"""
        from django.db.models import Avg
        from datetime import date

        today = date.today()
        avg_age = self.estudiantes_activos().annotate(
            age=date.today().year - models.F('fecha_nacimiento__year')
        ).aggregate(avg_age=Avg('age'))['avg_age']

        return avg_age or 0

    """
    activo = models.BooleanField(
        default=True,
        verbose_name="Estatus Activo"
    )"""


class Estudiante(models.Model):
    matricula = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Matrícula"
    )
    nombre = models.CharField(
        max_length=50,
        verbose_name="Nombre(s)"
    )
    apellido_paterno = models.CharField(
        max_length=50,
        verbose_name="Apellido Paterno"
    )
    apellido_materno = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Apellido Materno"
    )
    fecha_nacimiento = models.DateField(
        verbose_name="Fecha de Nacimiento",
        null=True,
        blank=True  # Permitir que esté vacío inicialmente
    )
    curp = models.CharField(
        max_length=18,
        unique=True,
        validators=[RegexValidator(
            regex=r'^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[0-9A-Z]{2}$',
            message='CURP inválida.'
        )],
        verbose_name="CURP",
        blank=True,  # Permitir que esté vacío inicialmente
        null=True  # Y que sea NULL en la base de datos
    )
    grupo_actual = models.ForeignKey(
        Grupo,
        on_delete=models.PROTECT,
        related_name='estudiantes',
        verbose_name="Grupo Actual",
        null=True,  # Permitir NULL temporalmente
        blank=True  # Permitir que esté vacío en formularios
    )
    fecha_inscripcion = models.DateField(
        auto_now_add=True,
        verbose_name="Fecha de Inscripción"
    )
    ciclo_inscripcion = models.ForeignKey(
        CicloEscolar,
        on_delete=models.PROTECT,
        related_name='estudiantes',
        verbose_name="Ciclo de Inscripción",
        null=True,  # Temporalmente permitir nulos
        blank=True  # Permitir que esté vacío en formularios
    )
    padre = models.ForeignKey(
        'padres.Padre',  # ¡Aquí está el cambio! 'padres.Padre' en lugar de solo 'Padre'
        on_delete=models.SET_NULL,
        related_name='hijos',
        verbose_name="Padre/Tutor",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Estudiante"
        verbose_name_plural = "Estudiantes"
        ordering = ['grupo_actual', 'apellido_paterno', 'apellido_materno']
        indexes = [
            models.Index(fields=['apellido_paterno', 'apellido_materno']),
        ]

    def __str__(self):
        return f"{self.matricula} - {self.nombre_completo()}"

    def nombre_completo(self):
        return f"{self.nombre} {self.apellido_paterno} {self.apellido_materno or ''}".strip()

    def clean(self):
        # Solo validar si ambos campos están presentes
        if self.grupo_actual and self.ciclo_inscripcion:
            if self.grupo_actual.ciclo != self.ciclo_inscripcion:
                raise ValidationError(
                    "El grupo asignado no pertenece al ciclo de inscripción del estudiante"
                )

    @property
    def edad(self):
        if not self.fecha_nacimiento:
            return None
        from datetime import date
        today = date.today()
        return today.year - self.fecha_nacimiento.year - (
                (today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )

    registro_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def get_registro_url(self):
        from django.urls import reverse
        return reverse('padres:registro_padre_token', args=[str(self.registro_token)])


class HistorialAcademico(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='historiales')
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name='historiales')
    fecha_ingreso = models.DateField(auto_now_add=True)
    fecha_salida = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_ingreso']
        unique_together = ('estudiante', 'grupo', 'fecha_ingreso')

    def __str__(self):
        return f"{self.estudiante} - {self.grupo} ({self.fecha_ingreso})"
