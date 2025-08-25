from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Cita
from profesores.models import Profesor
from padres.models import Padre
from servicios_escolares.models import ServicioEscolar
from datetime import timedelta


class CrearCitaForm(forms.ModelForm):
    padre = forms.ModelChoiceField(
        queryset=Padre.objects.none(),
        label="Padre/Madre/Tutor",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Cita
        fields = ['padre', 'tipo', 'titulo', 'fecha_hora_inicio', 'duracion', 'ubicacion', 'motivo']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Revisión de calificaciones'
            }),
            'fecha_hora_inicio': forms.DateTimeInput(attrs={
                'class': 'form-control datetimepicker',
                'type': 'datetime-local'
            }),
            'duracion': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '15',
                'step': '15'
            }),
            'ubicacion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Sala de profesores'
            }),
            'motivo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describa el motivo detalladamente...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.profesor = kwargs.pop('profesor', None)
        super().__init__(*args, **kwargs)

        # Filtrar padres relacionados con el profesor (ej: por asignaturas/grupos)
        if self.profesor:
            self.fields['padre'].queryset = Padre.objects.filter(
                # Aquí ajusta la relación según tu modelo de datos
                alumno__asignaturas__profesor=self.profesor
            ).distinct().order_by('nombre_completo')

    def clean_fecha_hora_inicio(self):
        fecha = self.cleaned_data['fecha_hora_inicio']
        if fecha < timezone.now():
            raise ValidationError("No se pueden agendar citas en el pasado")

        # Verificar disponibilidad del profesor
        if self.profesor:
            fin = fecha + timedelta(minutes=self.cleaned_data.get('duracion', 30))
            citas_solapadas = Cita.objects.filter(
                profesor=self.profesor,
                fecha_hora_inicio__lt=fin,
                fecha_hora_fin__gt=fecha
            ).exists()

            if citas_solapadas:
                raise ValidationError("Ya tiene una cita programada en ese horario")

        return fecha

    def save(self, commit=True):
        cita = super().save(commit=False)
        cita.solicitante = self.cleaned_data['padre']
        cita.profesor = self.profesor
        cita.fecha_hora_fin = cita.fecha_hora_inicio + timedelta(minutes=cita.duracion)

        if commit:
            cita.save()
        return cita


class CancelarCitaForm(forms.Form):
    motivo_cancelacion = forms.CharField(
        label='Motivo de la cancelación',
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Explica el motivo...'}),
        max_length=500,
        required=True
    )


class ReprogramarCitaForm(forms.ModelForm):
    motivo_reprogramacion = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=True,
        label="Motivo de la reprogramación"
    )

    class Meta:
        model = Cita
        fields = ['fecha_hora_inicio', 'duracion', 'motivo_reprogramacion']
        widgets = {
            'fecha_hora_inicio': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'duracion': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '15',
                'max': '120'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoy = timezone.now()
        self.fields['fecha_hora_inicio'].widget.attrs['min'] = hoy.strftime('%Y-%m-%dT%H:%M')
        self.fields['fecha_hora_inicio'].widget.attrs['max'] = (hoy + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M')

    def clean_fecha_hora_inicio(self):
        fecha = self.cleaned_data['fecha_hora_inicio']
        if fecha.weekday() >= 5:
            raise forms.ValidationError("No se pueden agendar citas los fines de semana")
        hora = fecha.time()
        if hora < time(8, 0) or hora > time(18, 0):
            raise forms.ValidationError("Horario no válido (8:00 - 18:00 hrs)")
        return fecha
