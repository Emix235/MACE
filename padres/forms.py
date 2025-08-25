from datetime import timedelta, time

from django.contrib.auth.hashers import make_password
from django.db import models

from servicios_escolares.models import ServicioEscolar
from .models import Padre
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from estudiantes.models import Estudiante
from citas.models import Cita, ReprogramacionCita


class RegistroPadreForm(forms.ModelForm):
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
        model = Padre
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
                'placeholder': 'Ej. María Fernanda'
            }),
            'apellidos': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. Gómez Rivera'
            }),
            'correo_electronico': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. maria.gomez@gmail.com'
            }),
            'telefono_principal': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. 5511223344'
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

    # ❌ Puedes comentar esta validación si quieres permitir correos duplicados temporalmente
    # def clean_correo_electronico(self):
    #     correo = self.cleaned_data.get('correo_electronico')
    #     if Padre.objects.filter(correo_electronico=correo).exists():
    #         raise ValidationError("Este correo electrónico ya está registrado.")
    #     return correo

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
        padre = super().save(commit=False)
        padre.contraseña = make_password(self.cleaned_data['contraseña'])
        padre.rol_usuario = 'Padre'
        padre.estado_cuenta = 'Activo'

        if commit:
            padre.save()
            if 'imagen_usuario' in self.files:
                padre.imagen_usuario = self.files['imagen_usuario']
                padre.save()

        return padre


class LoginPadreForm(forms.Form):
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

    def clean(self):
        cleaned_data = super().clean()
        correo = cleaned_data.get('correo_electronico')
        contraseña = cleaned_data.get('contraseña')

        # ejemplo de validación global
        if correo and contraseña:
            if correo.endswith('@fake.com'):
                raise forms.ValidationError('El correo ingresado no está permitido.')


class EditarPerfilPadreForm(forms.ModelForm):
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
        }),
        label="Confirmar Contraseña"
    )

    class Meta:
        model = Padre
        fields = [
            'nombre_completo',
            'apellidos',
            'correo_electronico',
            'telefono_principal',
            'telefono_respaldo',
            'imagen_usuario',
            'datos_personales'
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'correo_electronico': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono_principal': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono_respaldo': forms.TextInput(attrs={'class': 'form-control'}),
            'imagen_usuario': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'datos_personales': forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        }

    def clean(self):
        cleaned_data = super().clean()
        nueva_contraseña = cleaned_data.get('nueva_contraseña')
        confirmar_contraseña = cleaned_data.get('confirmar_contraseña')

        if nueva_contraseña:
            if not confirmar_contraseña:
                raise forms.ValidationError("Debes confirmar la nueva contraseña.")
            elif nueva_contraseña != confirmar_contraseña:
                raise forms.ValidationError("Las contraseñas no coinciden.")
        elif confirmar_contraseña:
            raise forms.ValidationError("Debes ingresar una nueva contraseña.")

        return cleaned_data

    def save(self, commit=True):
        padre = super().save(commit=False)
        nueva_contraseña = self.cleaned_data.get('nueva_contraseña')

        if nueva_contraseña:
            padre.contraseña = make_password(nueva_contraseña)

        if commit:
            padre.save()

        return padre


class CitaForm(forms.ModelForm):
    estudiantes = forms.ModelMultipleChoiceField(
        queryset=Estudiante.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Selecciona los estudiantes involucrados"
    )

    # Campo solo para citas con profesor
    incluir_servicio_escolar = forms.BooleanField(
        required=False,
        label="Incluir a servicio escolar en la cita",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Cita
        fields = ['tipo', 'titulo', 'fecha_hora_inicio', 'duracion', 'ubicacion',
                  'estudiantes', 'motivo', 'observaciones']
        widgets = {
            'fecha_hora_inicio': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
            }),
            'motivo': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.padre = kwargs.pop('padre', None)
        self.profesor = kwargs.pop('profesor', None)
        self.servicio_escolar = kwargs.pop('servicio_escolar', None)
        estudiantes_queryset = kwargs.pop('estudiantes_queryset', None)

        super().__init__(*args, **kwargs)

        # Configurar queryset de estudiantes
        if estudiantes_queryset is not None:
            self.fields['estudiantes'].queryset = estudiantes_queryset
        elif self.padre:
            self.fields['estudiantes'].queryset = Estudiante.objects.filter(
                padre=self.padre,
                grupo_actual__isnull=False
            ).order_by('apellido_paterno', 'apellido_materno')

        # Configurar opciones de duración
        self.fields['duracion'].widget = forms.Select(
            choices=[(15, '15 minutos'), (30, '30 minutos'),
                     (45, '45 minutos'), (60, '1 hora')],
            attrs={'class': 'form-control'}
        )

        # Configuraciones específicas para servicio escolar
        if self.servicio_escolar:
            # Forzar tipo administrativa pero mostrando el campo (no hidden)
            self.fields['tipo'].initial = 'administrativa'
            self.fields['tipo'].widget.attrs['readonly'] = True
            self.fields['tipo'].widget.attrs['class'] = 'form-control bg-light'
            self.fields['ubicacion'].initial = "Oficina de Servicios Escolares"
            # Ocultar checkbox de servicio escolar
            self.fields['incluir_servicio_escolar'].widget = forms.HiddenInput()
            self.fields['incluir_servicio_escolar'].initial = False

        # Configuraciones para citas con profesor
        elif self.profesor:
            # Mostrar todas las opciones de tipo
            self.fields['tipo'].choices = Cita.TIPOS
            # Mostrar checkbox para incluir servicio escolar
            self.fields['incluir_servicio_escolar'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})

    def clean(self):
        cleaned_data = super().clean()

        # Validar destinatario
        if not hasattr(self, 'profesor') and not hasattr(self, 'servicio_escolar'):
            raise forms.ValidationError("Debe seleccionar al menos un destinatario")

        # Validar disponibilidad del servicio escolar si aplica
        if hasattr(self, 'servicio_escolar'):
            if self.servicio_escolar and self.servicio_escolar.estado_disponibilidad != 'Disponible':
                raise forms.ValidationError("El servicio escolar seleccionado no está disponible")

        # Validar horario
        if 'fecha_hora_inicio' in cleaned_data:
            hora = cleaned_data['fecha_hora_inicio'].time()
            if hora < time(8, 0) or hora >= time(18, 0):
                raise forms.ValidationError("Horario no válido (08:00-18:00)")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Calcular fecha de fin automáticamente
        instance.fecha_hora_fin = instance.fecha_hora_inicio + timedelta(minutes=instance.duracion)

        # Asignar relaciones según el tipo de cita
        if self.servicio_escolar:
            instance.servicio_escolar = self.servicio_escolar
            instance.tipo = 'administrativa'  # Forzar tipo administrativa

        if self.profesor:
            instance.profesor = self.profesor
            if self.cleaned_data.get('incluir_servicio_escolar'):
                servicio = ServicioEscolar.objects.filter(
                    estado_cuenta='Activo',
                    estado_disponibilidad='Disponible'
                ).first()
                if servicio:
                    instance.servicio_escolar = servicio

        if commit:
            instance.save()
            self.save_m2m()

        return instance


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
        label="Motivo de la reprogramación",
        required=True,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe el motivo'
            }
        )
    )

    def __init__(self, *args, **kwargs):
        self.cita = kwargs.pop('cita', None)
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

        hora_minima_reprogramacion = self.cita.fecha_hora_inicio - timedelta(hours=1)
        if timezone.now() > hora_minima_reprogramacion:
            raise ValidationError(
                f"No se puede reprogramar la cita cuando faltan menos de 60 minutos para la misma. "
                f"Límite para reprogramar: {hora_minima_reprogramacion.strftime('%d/%m/%Y %H:%M')}"
            )

        if fecha_hora_inicio <= timezone.now():
            raise ValidationError("No se pueden agendar citas en el pasado")

        margen_minimo = timezone.now() + timedelta(minutes=15)
        if fecha_hora_inicio < margen_minimo:
            raise ValidationError(
                f"La cita debe programarse con al menos 15 minutos de anticipación. "
                f"Hora mínima: {margen_minimo.strftime('%d/%m/%Y %H:%M')}"
            )

        if fecha_hora_inicio.weekday() >= 5:
            raise ValidationError("No se pueden agendar citas los fines de semana")

        hora_inicio = fecha_hora_inicio.time()
        hora_fin = (fecha_hora_inicio + timedelta(minutes=duracion)).time()

        HORA_INICIO_OFICIAL = timezone.datetime.strptime('08:00', '%H:%M').time()
        HORA_FIN_OFICIAL = timezone.datetime.strptime('18:00', '%H:%M').time()

        if hora_inicio < HORA_INICIO_OFICIAL or hora_inicio > HORA_FIN_OFICIAL:
            raise ValidationError(
                f"El horario de atención es de {HORA_INICIO_OFICIAL.strftime('%H:%M')} "
                f"a {HORA_FIN_OFICIAL.strftime('%H:%M')}"
            )

        if hora_fin > HORA_FIN_OFICIAL:
            raise ValidationError(
                f"La cita no puede terminar después de las {HORA_FIN_OFICIAL.strftime('%H:%M')}"
            )

        return cleaned_data
