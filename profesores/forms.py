from datetime import timedelta, time

import pytz
from django.contrib.auth.hashers import make_password, check_password
from pyexpat.errors import messages
from django.utils import timezone
from citas.models import Cita, CitaPrioritaria
from .models import Profesor, TiempoLibreProfesor
from django import forms
from django.core.exceptions import ValidationError
from .models import Clase, HorarioClase
from estudiantes.models import Grupo, CicloEscolar
from django.forms import inlineformset_factory


class RegistroProfesorForm(forms.ModelForm):
    confirmar_contraseña = forms.CharField(
        max_length=100,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirma tu contraseña'
        }),
        label="Confirmar Contraseña"
    )

    contraseña = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Crea una contraseña segura'
        }),
        min_length=8,
        help_text="La contraseña debe tener al menos 8 caracteres."
    )

    class Meta:
        model = Profesor
        fields = [
            'nombre_completo',
            'apellidos',
            'correo_electronico',
            'contraseña',
            'confirmar_contraseña',
            'telefono_principal',
            'telefono_respaldo',
            'imagen_usuario'
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. Juan Carlos'
            }),
            'apellidos': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. Pérez López'
            }),
            'correo_electronico': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. juan.perez@escuela.edu'
            }),
            'telefono_principal': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. 5512345678'
            }),
            'telefono_respaldo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Opcional'
            }),
            'imagen_usuario': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }
        labels = {
            'correo_electronico': 'Correo Electrónico',
            'telefono_principal': 'Teléfono Principal',
            'telefono_respaldo': 'Teléfono de Respaldo (Opcional)',
            'imagen_usuario': 'Foto de Perfil (Opcional)'
        }

    def clean_correo_electronico(self):
        correo = self.cleaned_data.get('correo_electronico')
        if Profesor.objects.filter(correo_electronico=correo).exists():
            raise ValidationError("Este correo electrónico ya está registrado.")
        return correo

    def clean_contraseña(self):
        contraseña = self.cleaned_data.get('contraseña')
        if len(contraseña) < 8:
            raise ValidationError("La contraseña debe tener al menos 8 caracteres.")
        return contraseña

    def clean(self):
        cleaned_data = super().clean()
        contraseña = cleaned_data.get('contraseña')
        confirmar_contraseña = cleaned_data.get('confirmar_contraseña')

        if contraseña and confirmar_contraseña and contraseña != confirmar_contraseña:
            raise ValidationError("Las contraseñas no coinciden.")

        return cleaned_data

    def save(self, commit=True):
        profesor = super().save(commit=False)
        profesor.contraseña = make_password(self.cleaned_data['contraseña'])
        profesor.rol_usuario = 'Profesor'
        profesor.estado_cuenta = 'Activo'

        if commit:
            profesor.save()
            if 'imagen_usuario' in self.files:
                profesor.imagen_usuario = self.files['imagen_usuario']
                profesor.save()

        return profesor


class LoginProfesorForm(forms.Form):
    correo_electronico = forms.EmailField(
        label="Correo Electrónico",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'tu.correo@escuela.edu'
        })
    )
    contraseña = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tu contraseña'
        }),
        min_length=8
    )


class EditarPerfilForm(forms.ModelForm):
    nueva_contraseña = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Dejar en blanco para no cambiar'
        }),
        label="Nueva Contraseña"
    )
    confirmar_contraseña = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmar nueva contraseña'
        })
    )

    class Meta:
        model = Profesor
        fields = [
            'nombre_completo',
            'apellidos',
            'correo_electronico',
            'telefono_principal',
            'telefono_respaldo',
            'imagen_usuario',
            'datos_personales',
            'asignaturas_impartidas',
            'datos_contacto'
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'correo_electronico': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono_principal': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono_respaldo': forms.TextInput(attrs={'class': 'form-control'}),
            'datos_personales': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'asignaturas_impartidas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'datos_contacto': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        nueva_contraseña = cleaned_data.get('nueva_contraseña')
        confirmar_contraseña = cleaned_data.get('confirmar_contraseña')

        # Lógica mejorada de validación
        if nueva_contraseña:  # Si hay nueva contraseña
            if not confirmar_contraseña:
                raise forms.ValidationError("Debes confirmar la nueva contraseña")
            elif nueva_contraseña != confirmar_contraseña:
                raise forms.ValidationError("Las contraseñas no coinciden")
        elif confirmar_contraseña:  # Si solo hay confirmación sin nueva contraseña
            raise forms.ValidationError("Debes ingresar una nueva contraseña")

        return cleaned_data

    def save(self, commit=True):
        profesor = super().save(commit=False)
        nueva_contraseña = self.cleaned_data.get('nueva_contraseña')

        if nueva_contraseña:
            profesor.contraseña = make_password(nueva_contraseña)

        if commit:
            profesor.save()

        return profesor


class HorarioClaseForm(forms.ModelForm):
    class Meta:
        model = HorarioClase
        fields = ['dia_semana', 'hora_inicio', 'hora_fin', 'aula']
        widgets = {
            'dia_semana': forms.Select(attrs={'class': 'form-control'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'aula': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Aula 101'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        hora_inicio = cleaned_data.get('hora_inicio')
        hora_fin = cleaned_data.get('hora_fin')

        if hora_inicio and hora_fin and hora_fin <= hora_inicio:
            raise ValidationError("La hora de finalización debe ser posterior a la de inicio")

        return cleaned_data


HorarioFormSet = inlineformset_factory(
    Clase,
    HorarioClase,
    form=HorarioClaseForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class ClaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.profesor = kwargs.pop('profesor', None)
        super().__init__(*args, **kwargs)

        # Obtener ciclo actual
        self.ciclo_actual = CicloEscolar.obtener_actual()

        if self.ciclo_actual:
            # Ocultar el campo de nivel educativo
            self.fields['nivel_educativo'].widget = forms.HiddenInput()
            self.initial['nivel_educativo'] = self.ciclo_actual.nivel

            # Filtrar grupos solo del ciclo actual (sin filtrar por nivel)
            self.fields['grupo'].queryset = Grupo.objects.filter(
                ciclo=self.ciclo_actual
            ).order_by('grado', 'letra')
        else:
            self.fields['grupo'].queryset = Grupo.objects.none()
            if hasattr(self, 'request'):
                messages.warning(self.request, 'No hay un ciclo escolar activo')

        # Configurar campos
        self.fields['nombre'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Ej: Matemáticas Avanzadas'
        })

        for field in ['tipo_asignatura', 'grupo']:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

    class Meta:
        model = Clase
        fields = ['nombre', 'nivel_educativo', 'tipo_asignatura', 'grupo']
        labels = {
            'nombre': 'Nombre de la Materia',
            'tipo_asignatura': 'Tipo de Asignatura',
            'grupo': 'Grupo Asignado'
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.profesor = self.profesor
        instance.ciclo_escolar = self.ciclo_actual

        if self.ciclo_actual:
            instance.nivel_educativo = self.ciclo_actual.nivel

        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned_data = super().clean()

        if not self.ciclo_actual:
            raise ValidationError('No hay un ciclo escolar activo')

        nombre = cleaned_data.get('nombre')
        grupo = cleaned_data.get('grupo')

        if nombre and grupo:
            if Clase.objects.filter(
                    nombre=nombre,
                    grupo=grupo,
                    ciclo_escolar=self.ciclo_actual,
                    profesor=self.profesor
            ).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise ValidationError('Ya existe una clase con estos datos para el ciclo actual')

        return cleaned_data


class TiempoLibreForm(forms.ModelForm):
    class Meta:
        model = TiempoLibreProfesor
        fields = ['dia_semana', 'hora_inicio', 'hora_fin', 'motivo']
        widgets = {
            'dia_semana': forms.Select(attrs={'class': 'form-control'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'motivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Descanso, Reunión familiar'}),
        }

    def __init__(self, *args, **kwargs):
        self.profesor = kwargs.pop('profesor', None)
        self.ciclo_escolar = kwargs.pop('ciclo_escolar', None)
        super().__init__(*args, **kwargs)
        # Set the instance fields immediately
        if self.profesor and hasattr(self, 'instance'):
            self.instance.profesor = self.profesor
        if self.ciclo_escolar and hasattr(self, 'instance'):
            self.instance.ciclo_escolar = self.ciclo_escolar

    def save(self, commit=True):
        # Fields are already set in __init__, just save normally
        return super().save(commit=commit)


class CitaPrioritariaForm(forms.ModelForm):
    class Meta:
        model = CitaPrioritaria
        fields = [
            'titulo', 'fecha_hora_inicio', 'duracion', 'ubicacion',
            'nivel_prioridad', 'motivo_prioridad', 'evidencia_archivo'
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'placeholder': 'Ej: Situación disciplinaria urgente'}),
            'fecha_hora_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'motivo_prioridad': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describa la situación urgente...'}),
            'nivel_prioridad': forms.RadioSelect(),
            'duracion': forms.Select(choices=[(30, '30 minutos'), (60, '1 hora')]),
        }
        labels = {
            'nivel_prioridad': 'Nivel de Prioridad',
            'motivo_prioridad': 'Justificación de Prioridad',
        }
        help_texts = {
            'motivo_prioridad': 'Describa en detalle por qué esta cita requiere atención inmediata',
            'evidencia_archivo': 'Adjunte archivo relevante (opcional, máximo 5MB)',
        }

    def __init__(self, *args, estudiante=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Debug de los datos iniciales
        print(f"\n[FORM DEBUG] Datos iniciales: {self.initial}")
        print(f"[FORM DEBUG] Datos recibidos: {self.data if self.is_bound else 'N/A'}")

        # Configuración inicial basada en el estudiante
        if estudiante:
            self.fields['titulo'].initial = f"Cita urgente: {estudiante.nombre_completo()}"

        # Manejo especial para fecha/hora (compatible con HTML5)
        if 'fecha_hora_inicio' not in self.data:  # Solo si no se envió
            ahora = timezone.now()
            self.fields['fecha_hora_inicio'].initial = (ahora + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')

        # Valores por defecto
        self.fields['duracion'].initial = 30
        self.fields['ubicacion'].initial = "Escuela"

    def clean_fecha_hora_inicio(self):
        tz_mexico = pytz.timezone('America/Mexico_City')
        fecha_hora = self.cleaned_data.get('fecha_hora_inicio')
        ahora = timezone.localtime(timezone.now(), tz_mexico)

        if not fecha_hora:
            raise ValidationError("Debe especificar una fecha y hora")

        # Asegurar zona horaria
        if fecha_hora.tzinfo is None:
            fecha_hora = tz_mexico.localize(fecha_hora)

        # Validación 1: No fechas pasadas
        if fecha_hora < ahora:
            raise ValidationError("No puede agendar citas en horarios pasados")

        # Validación 2: Margen mínimo de 1 hora para hoy
        if fecha_hora.date() == ahora.date() and fecha_hora < (ahora + timedelta(hours=1)):
            raise ValidationError(f"Para hoy, la hora mínima es {(ahora + timedelta(hours=1)).strftime('%H:%M')}")

        # Validación 3: Horario laboral (8:00-17:30)
        hora = fecha_hora.time()
        if hora < time(8, 0) or hora > time(17, 30):
            raise ValidationError("Horario de atención: 8:00 - 17:30 hrs")

        # Validación 4: No fines de semana
        if fecha_hora.weekday() >= 5:
            raise ValidationError("No se permiten citas los fines de semana")

        return fecha_hora

    def calcular_duracion_maxima(self, fecha_hora):
        hora_fin_maxima = fecha_hora.replace(hour=18, minute=0)
        diferencia = hora_fin_maxima - fecha_hora
        return int(diferencia.total_seconds() / 60)

    def clean_evidencia_archivo(self):
        archivo = self.cleaned_data.get('evidencia_archivo')
        if archivo:
            # Validar tamaño
            if archivo.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError("El archivo no puede exceder los 5MB")

            # Validar tipo de archivo
            tipos_permitidos = [
                'application/pdf',
                'image/jpeg',
                'image/png',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ]

            if archivo.content_type not in tipos_permitidos:
                raise ValidationError("Solo se permiten archivos PDF, imágenes (JPEG/PNG) o documentos (Word/Excel)")

        return archivo


class ReprogramarCitaForm(forms.Form):
    fecha_hora_inicio = forms.DateTimeField(
        label="Nueva fecha y hora",
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'placeholder': 'Selecciona nueva fecha y hora',
            }
        ),
        input_formats=['%Y-%m-%dT%H:%M']
    )
    duracion = forms.IntegerField(
        label="Duración (minutos)",
        min_value=15,
        max_value=240,
        initial=30,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Duración en minutos'
            }
        )
    )
    motivo_reprogramacion = forms.CharField(
        label="Motivo de la reprogramación (requerido)",
        required=True,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe el motivo de la reprogramación'
            }
        )
    )

    def __init__(self, *args, **kwargs):
        self.cita = kwargs.pop('cita', None)
        self.profesor = kwargs.pop('profesor', None)
        super().__init__(*args, **kwargs)

        if self.cita:
            self.fields['fecha_hora_inicio'].initial = self.cita.fecha_hora_inicio
            self.fields['duracion'].initial = self.cita.duracion

    def clean(self):
        cleaned_data = super().clean()
        fecha_hora_inicio = cleaned_data.get('fecha_hora_inicio')
        duracion = cleaned_data.get('duracion')

        if not fecha_hora_inicio or not duracion:
            return cleaned_data

        # Validación de tiempo mínimo para reprogramación (60 minutos antes)
        hora_minima_reprogramacion = self.cita.fecha_hora_inicio - timedelta(hours=1)
        if timezone.now() > hora_minima_reprogramacion:
            raise ValidationError(
                f"No se puede reprogramar la cita cuando faltan menos de 60 minutos para la misma. "
                f"Límite para reprogramar: {hora_minima_reprogramacion.strftime('%d/%m/%Y %H:%M')}"
            )

        # Validaciones de fecha/hora
        if fecha_hora_inicio <= timezone.now():
            raise ValidationError("No se pueden programar citas en fechas pasadas")

        margen_minimo = timezone.now() + timedelta(minutes=30)  # 30 minutos mínimo de anticipación
        if fecha_hora_inicio < margen_minimo:
            raise ValidationError(
                f"La cita debe programarse con al menos 30 minutos de anticipación. "
                f"Hora mínima permitida: {margen_minimo.strftime('%d/%m/%Y %H:%M')}"
            )

        # Validación de horario laboral del profesor (personalizable)
        hora_inicio = fecha_hora_inicio.time()
        hora_fin = (fecha_hora_inicio + timedelta(minutes=duracion)).time()

        HORA_INICIO_LABORAL = time(8, 0)  # 8:00 AM
        HORA_FIN_LABORAL = time(17, 0)  # 5:00 PM

        if hora_inicio < HORA_INICIO_LABORAL or hora_fin > HORA_FIN_LABORAL:
            raise ValidationError(
                f"El horario laboral para citas es de {HORA_INICIO_LABORAL.strftime('%H:%M')} "
                f"a {HORA_FIN_LABORAL.strftime('%H:%M')}"
            )

        # Validación de disponibilidad del profesor
        if self.profesor:
            citas_solapadas = Cita.objects.filter(
                profesor=self.profesor,
                fecha_hora_inicio__lt=fecha_hora_inicio + timedelta(minutes=duracion),
                fecha_hora_fin__gt=fecha_hora_inicio
            ).exclude(id=self.cita.id)

            if citas_solapadas.exists():
                raise ValidationError(
                    "Ya tiene una cita programada en ese horario. "
                    "Por favor seleccione otro horario."
                )

        return cleaned_data
