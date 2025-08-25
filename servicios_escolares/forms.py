from datetime import timezone, timedelta, time

import pytz
from django.utils import timezone
from django import forms
from django.core.exceptions import ValidationError

from citas.models import Cita, CitaPrioritaria
from .models import ServicioEscolar
import re


class LoginForm(forms.Form):
    correo_electronico = forms.EmailField(
        label="Correo Electrónico",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'ejemplo@escuela.edu'
        })
    )
    contraseña = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tu contraseña'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        correo = cleaned_data.get('correo_electronico')
        contraseña = cleaned_data.get('contraseña')

        if correo and contraseña:
            try:
                usuario = ServicioEscolar.objects.get(correo_electronico=correo)
                if not usuario.check_password(contraseña):  # Ahora funcionará
                    raise ValidationError("Credenciales inválidas")
                cleaned_data['usuario'] = usuario
            except ServicioEscolar.DoesNotExist:
                raise ValidationError("Credenciales inválidas")
        return cleaned_data


class RegistroForm(forms.ModelForm):
    confirmar_contraseña = forms.CharField(
        label="Confirmar Contraseña",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repite tu contraseña'
        })
    )

    class Meta:
        model = ServicioEscolar
        fields = [
            'nombre_completo',
            'apellidos',
            'correo_electronico',
            'contraseña',
            'confirmar_contraseña',
            'telefono_principal',
            'imagen_usuario'
        ]
        widgets = {
            'contraseña': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Mínimo 8 caracteres'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        contraseña = cleaned_data.get('contraseña')
        confirmar = cleaned_data.get('confirmar_contraseña')

        if contraseña and confirmar:
            if contraseña != confirmar:
                self.add_error('confirmar_contraseña', "Las contraseñas no coinciden")

            if len(contraseña) < 8:
                self.add_error('contraseña', "Debe tener al menos 8 caracteres")

            if not re.search(r'[A-Z]', contraseña):
                self.add_error('contraseña', "Debe contener al menos una mayúscula")

            if not re.search(r'\d', contraseña):
                self.add_error('contraseña', "Debe contener al menos un número")

        return cleaned_data

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if commit:
            usuario.save()  # El modelo ya maneja el hashing de la contraseña
        return usuario


# 'estado_disponibilidad',
'''
'estado_disponibilidad': forms.Select(attrs={
                'class': 'form-select'
            }),
'''


# 'estado_disponibilidad': 'Estado de Disponibilidad',

class ServicioEscolarForm(forms.ModelForm):
    class Meta:
        model = ServicioEscolar
        fields = [
            'nombre_completo',
            'apellidos',
            'correo_electronico',
            'telefono_principal',
            'telefono_respaldo',
            'datos_personales',
            'horario_atencion',
            'imagen_usuario'
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre(s) completo(s)'
            }),
            'apellidos': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apellidos'
            }),
            'correo_electronico': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'correo@ejemplo.com'
            }),
            'telefono_principal': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Teléfono principal'
            }),
            'telefono_respaldo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Teléfono de respaldo (opcional)'
            }),
            'datos_personales': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Información personal relevante'
            }),
            'horario_atencion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Ej: Lunes a Viernes, 9:00 - 15:00'
            }),
            'imagen_usuario': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }
        labels = {
            'correo_electronico': 'Correo Electrónico',
            'telefono_principal': 'Teléfono Principal',
            'telefono_respaldo': 'Teléfono de Respaldo',
            'datos_personales': 'Datos Personales',
            'horario_atencion': 'Horario de Atención',
            'imagen_usuario': 'Foto de Perfil'
        }

    def clean_telefono_principal(self):
        telefono = self.cleaned_data.get('telefono_principal')
        if not telefono.isdigit():
            raise forms.ValidationError("El teléfono solo debe contener números")
        return telefono

    def clean_telefono_respaldo(self):
        telefono = self.cleaned_data.get('telefono_respaldo')
        if telefono and not telefono.isdigit():
            raise forms.ValidationError("El teléfono solo debe contener números")
        return telefono


class CitaForm(forms.ModelForm):
    class Meta:
        model = Cita
        fields = [
            'tipo',
            'fecha_hora_inicio',
            'duracion',
            'ubicacion',
            'motivo',
            'observaciones',
            'estado'
        ]
        widgets = {
            'fecha_hora_inicio': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'motivo': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Describa el propósito principal de la cita...'
            }),
            'observaciones': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Agregue cualquier información adicional...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Configuración básica de campos
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
            self.fields[field].widget.attrs.update({'aria-describedby': f'{field}-help'})

        # Establecer mínimo en el widget
        now = timezone.now()
        self.fields['fecha_hora_inicio'].widget.attrs['min'] = now.strftime('%Y-%m-%dT%H:%M')

    def clean_duracion(self):
        duracion = self.cleaned_data.get('duracion')
        if duracion:
            if duracion % 5 != 0:
                raise forms.ValidationError(
                    "La duración debe ser en múltiplos de 5 minutos"
                )
        return duracion


class ProfesorOptionalForm(forms.Form):
    def __init__(self, profesores, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Preparar opciones para el select
        choices = [
            ('', '──── No incluir profesor ────'),  # Opción por defecto más clara
            *[(prof.id, f"Prof. {prof.nombre_completo} {prof.apellidos}") for prof in profesores]
        ]

        self.fields['profesor'] = forms.ChoiceField(
            choices=choices,
            required=False,
            label="Selección de profesor",
            widget=forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_profesor'
            }),
            initial='',  # Selecciona la opción vacía por defecto
            help_text="Opcional: Seleccione un profesor si desea incluirlo en la cita"
        )

    def clean_profesor(self):
        profesor_id = self.cleaned_data.get('profesor')

        # Convertir string vacío a None explícitamente
        if profesor_id == '':
            return None

        # Validar que el ID sea un número válido
        try:
            return int(profesor_id) if profesor_id else None
        except (ValueError, TypeError):
            raise forms.ValidationError("Selección de profesor inválida")


class ReprogramarCitaServicioEscolarForm(forms.Form):
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
        label="Motivo de la reprogramación (Obligatorio)",
        required=True,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Indique el motivo detalladamente'
            }
        )
    )

    def __init__(self, *args, **kwargs):
        self.cita = kwargs.pop('cita', None)
        self.servicio_escolar = kwargs.pop('servicio_escolar', None)
        super().__init__(*args, **kwargs)

        if self.cita:
            self.fields['fecha_hora_inicio'].initial = self.cita.fecha_hora_inicio
            self.fields['duracion'].initial = self.cita.duracion
            # Mostrar campo urgente solo para citas asignadas
            if self.cita.estado != 'asignada':
                self.fields['es_urgente'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        fecha_hora_inicio = cleaned_data.get('fecha_hora_inicio')
        duracion = cleaned_data.get('duracion')
        es_urgente = cleaned_data.get('es_urgente', False)

        if not fecha_hora_inicio or not duracion:
            return cleaned_data

        # Validaciones especiales para servicio escolar
        if not es_urgente:
            hora_minima_reprogramacion = self.cita.fecha_hora_inicio - timedelta(minutes=30)
            if timezone.now() > hora_minima_reprogramacion and self.cita.estado != 'asignada':
                raise ValidationError(
                    f"Para reprogramaciones normales se requiere al menos 30 minutos de anticipación. "
                    f"Límite: {hora_minima_reprogramacion.strftime('%d/%m/%Y %H:%M')}. "
                    "Marque 'Reprogramación urgente' si es necesario."
                )

        # Validaciones básicas de fecha/hora
        if fecha_hora_inicio <= timezone.now():
            raise ValidationError("No se pueden programar citas en fechas pasadas")

        margen_minimo = timezone.now() + timedelta(minutes=5 if es_urgente else 15)
        if fecha_hora_inicio < margen_minimo:
            raise ValidationError(
                f"La cita debe programarse con al menos {5 if es_urgente else 15} minutos de anticipación. "
                f"Hora mínima permitida: {margen_minimo.strftime('%d/%m/%Y %H:%M')}"
            )

        if fecha_hora_inicio.weekday() >= 5 and not es_urgente:
            raise ValidationError("No se pueden agendar citas los fines de semana (excepto casos urgentes)")

        # Horario de atención extendido para servicio escolar
        hora_inicio = fecha_hora_inicio.time()
        hora_fin = (fecha_hora_inicio + timedelta(minutes=duracion)).time()

        HORA_INICIO = time(7, 30)  # 7:30 AM
        HORA_FIN = time(19, 0)  # 7:00 PM

        if (hora_inicio < HORA_INICIO or hora_fin > HORA_FIN) and not es_urgente:
            raise ValidationError(
                f"El horario normal de atención es de {HORA_INICIO.strftime('%H:%M')} a {HORA_FIN.strftime('%H:%M')}. "
                "Para horarios especiales marque 'Reprogramación urgente'"
            )

        # Validación de disponibilidad del servicio escolar
        if self.servicio_escolar and self.cita.servicio_escolar == self.servicio_escolar:
            citas_solapadas = Cita.objects.filter(
                servicio_escolar=self.servicio_escolar,
                fecha_hora_inicio__lt=fecha_hora_inicio + timedelta(minutes=duracion),
                fecha_hora_fin__gt=fecha_hora_inicio
            ).exclude(id=self.cita.id)

            if citas_solapadas.exists():
                raise ValidationError(
                    "Ya tiene otra cita programada en ese horario. "
                    "Por favor seleccione otro horario o cancele la cita existente primero."
                )

        return cleaned_data


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

        if estudiante:
            self.fields['titulo'].initial = f"Cita urgente: {estudiante.nombre_completo()}"

        if 'fecha_hora_inicio' not in self.data:
            ahora = timezone.localtime(timezone.now())
            self.fields['fecha_hora_inicio'].initial = (ahora + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')

        self.fields['duracion'].initial = 30
        self.fields['ubicacion'].initial = "Escuela"

    def clean_fecha_hora_inicio(self):
        fecha_hora = self.cleaned_data.get('fecha_hora_inicio')
        tz_mexico = pytz.timezone('America/Mexico_City')
        ahora = timezone.localtime(timezone.now(), tz_mexico)

        if not fecha_hora:
            raise ValidationError("Debe especificar una fecha y hora")

        # Asegurar zona horaria
        if fecha_hora.tzinfo is None:
            fecha_hora = tz_mexico.localize(fecha_hora)

        # Validación: no pasado
        if fecha_hora < ahora:
            raise ValidationError("No puede agendar citas en horarios pasados")

        # Validación: margen mínimo de 15 minutos
        if fecha_hora < (ahora + timedelta(minutes=15)):
            raise ValidationError("Debe agendarse con al menos 15 minutos de anticipación")

        # Validación: solo días hábiles
        if fecha_hora.weekday() >= 5:
            raise ValidationError("No se permiten citas los fines de semana")

        # Validación: horario laboral
        hora = fecha_hora.time()
        if hora < time(8, 0) or hora > time(17, 30):
            raise ValidationError("Horario de atención: 8:00 - 17:30 hrs")

        return fecha_hora

    def clean(self):
        cleaned_data = super().clean()
        fecha_hora = cleaned_data.get('fecha_hora_inicio')
        duracion = cleaned_data.get('duracion')

        if fecha_hora and duracion:
            hora_fin = (fecha_hora + timedelta(minutes=duracion)).time()

            # Limite final de atención
            if hora_fin > time(18, 0):
                self.add_error(
                    'duracion',
                    "La duración seleccionada excede el horario de atención (termina después de las 18:00)"
                )

    def clean_evidencia_archivo(self):
        archivo = self.cleaned_data.get('evidencia_archivo')
        if archivo:
            if archivo.size > 5 * 1024 * 1024:
                raise ValidationError("El archivo no puede exceder los 5MB")

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
                raise ValidationError("Archivo no válido. Solo PDF, JPG, PNG, Word o Excel")

        return archivo
