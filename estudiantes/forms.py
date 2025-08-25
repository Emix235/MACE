# forms.py
import pandas as pd
from django.core.exceptions import ValidationError
from .models import CicloEscolar, PeriodoEscolar, NivelEducativo, Grupo, Grado, Estudiante
from django import forms
from django.forms import inlineformset_factory, ModelForm
from .models import CicloEscolar, PeriodoEscolar, Grado, Grupo
from django.utils.translation import gettext_lazy as _
from .models import Estudiante, Grupo
from django.core.validators import FileExtensionValidator


class CicloEscolarForm(forms.ModelForm):
    class Meta:
        model = CicloEscolar
        fields = ['nombre', 'fecha_inicio', 'tipo_duracion', 'nivel', 'actual']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 2024-2025',
                'pattern': '\d{4}-\d{4}',
                'title': 'Formato: AAAA-AAAA (ej: 2023-2024)'
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'id': 'id_fecha_inicio'
            }),
            'tipo_duracion': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_tipo_duracion'
            }),
            'nivel': forms.Select(attrs={
                'class': 'form-select'
            }),
            'actual': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nivel'].queryset = NivelEducativo.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        nombre = cleaned_data.get('nombre')
        fecha_inicio = cleaned_data.get('fecha_inicio')

        if nombre:
            # Validación del formato del nombre
            if len(nombre) != 9 or nombre[4] != '-':
                raise ValidationError({
                    'nombre': _("Formato incorrecto. Use exactamente: AAAA-AAAA")
                })
            else:
                try:
                    año_inicio, año_fin = map(int, nombre.split('-'))
                    if año_fin - año_inicio != 1:
                        raise ValidationError({
                            'nombre': _("El año final debe ser el siguiente al inicial (ej: 2023-2024)")
                        })
                except ValueError:
                    raise ValidationError({
                        'nombre': _("Solo se permiten números en el formato AAAA-AAAA")
                    })

        return cleaned_data


class PeriodosConfigForm(forms.Form):
    PERIODOS_CHOICES = [
        ('SEM', 'Semestral (6 meses)'),
        ('TRI', 'Trimestral (3 meses)'),
        ('CUA', 'Cuatrimestral (4 meses)'),
        ('ANL', 'Anual (12 meses)'),
    ]

    tipo_periodo = forms.ChoiceField(
        choices=PERIODOS_CHOICES,
        widget=forms.RadioSelect,
        label="Seleccione el tipo de periodo académico",
        help_text="El sistema calculará automáticamente las fechas de cada periodo"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_periodo'].widget.attrs.update({'class': 'form-check-input'})


class GrupoForm(forms.ModelForm):
    class Meta:
        model = Grupo
        fields = ['grado', 'letra', 'turno', 'capacidad', 'aula']

    def __init__(self, *args, **kwargs):
        ciclo = kwargs.pop('ciclo', None)
        super().__init__(*args, **kwargs)
        if ciclo:
            self.fields['grado'].queryset = Grado.objects.filter(nivel=ciclo.nivel)


class CrearGruposForm(forms.Form):
    grado = forms.ModelChoiceField(queryset=Grado.objects.none())  # Se filtra por ciclo en el view
    cantidad_grupos = forms.IntegerField(min_value=1, max_value=5, initial=1)
    turno = forms.ChoiceField(choices=Grupo.TURNOS, initial='M')
    capacidad = forms.IntegerField(min_value=10, max_value=50, initial=30)

    def __init__(self, *args, **kwargs):
        ciclo = kwargs.pop('ciclo', None)
        super().__init__(*args, **kwargs)
        if ciclo:
            self.fields['grado'].queryset = Grado.objects.filter(nivel=ciclo.nivel)


class EstudianteForm(ModelForm):
    class Meta:
        model = Estudiante
        fields = '__all__'
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'fecha_inscripcion': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra grupos por ciclo de inscripción si ya está asignado
        if 'ciclo_inscripcion' in self.data:
            try:
                ciclo_id = int(self.data.get('ciclo_inscripcion'))
                self.fields['grupo_actual'].queryset = Grupo.objects.filter(ciclo_id=ciclo_id)
            except (ValueError, TypeError):
                pass


class NivelEducativoForm(forms.ModelForm):
    class Meta:
        model = NivelEducativo
        fields = ['codigo', 'orden']  # Solo estos campos son editables

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo'].widget.attrs.update({'class': 'form-control'})
        self.fields['orden'].widget.attrs.update({'class': 'form-control'})

        # Si es una instancia existente, mostrar el nombre como readonly
        if self.instance and self.instance.pk:
            self.fields['nombre_mostrar'] = forms.CharField(
                initial=self.instance.nombre,
                label='Nombre',
                widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
            )


class EditarNivelEducativoForm(forms.ModelForm):
    class Meta:
        model = NivelEducativo
        fields = ['codigo', 'orden']
        widgets = {
            'codigo': forms.Select(attrs={
                'class': 'form-select',
                'style': 'max-width: 200px;'
            }),
            'orden': forms.NumberInput(attrs={
                'class': 'form-control',
                'style': 'max-width: 100px;',
                'min': '1'
            })
        }

    def clean_orden(self):
        orden = self.cleaned_data['orden']
        if orden < 1:
            raise forms.ValidationError("El orden debe ser mayor que 0")
        return orden


class ConfiguracionGradosForm(forms.Form):
    def __init__(self, *args, **kwargs):
        niveles = kwargs.pop('niveles', NivelEducativo.objects.all())
        super().__init__(*args, **kwargs)

        for nivel in niveles:
            self.fields[f'grados_{nivel.id}'] = forms.IntegerField(
                label=f'Grados para {nivel.nombre}',
                min_value=0,
                max_value=12,
                initial=6 if nivel.codigo == 'PRI' else 3,
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )
            self.fields[f'grupos_{nivel.id}'] = forms.IntegerField(
                label=f'Grupos por grado en {nivel.nombre}',
                min_value=1,
                max_value=10,
                initial=1,
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )


class AsignarEstudiantesForm(forms.Form):
    def __init__(self, *args, **kwargs):
        grupos = kwargs.pop('grupos', [])
        super().__init__(*args, **kwargs)

        for grupo in grupos:
            self.fields[f'grupo_{grupo.id}'] = forms.IntegerField(
                label=f'Estudiantes para {grupo}',
                min_value=0,
                max_value=grupo.capacidad,
                initial=0,
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )


class ConfiguracionFlexibleForm(forms.Form):
    def __init__(self, *args, niveles=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.niveles = niveles or NivelEducativo.objects.all()

        for nivel in self.niveles:
            # Campo para número de grados en este nivel
            self.fields[f'nivel_{nivel.id}_grados'] = forms.IntegerField(
                label=f'Número de grados para {nivel.nombre}',
                min_value=0,
                max_value=12,
                initial=6 if nivel.codigo == 'PRI' else 3,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control grado-count',
                    'data-nivel-id': nivel.id,
                    'onchange': 'updateGruposFields(this)'
                })
            )

            # Contenedor para campos de grupos por grado (se llenará dinámicamente)
            self.fields[f'nivel_{nivel.id}_container'] = forms.CharField(
                label='',
                required=False,
                widget=forms.TextInput(attrs={
                    'class': 'd-none'  # Campo oculto solo para estructura
                })
            )


class EstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = [
            'matricula',
            'nombre',
            'apellido_paterno',
            'apellido_materno',
            'fecha_nacimiento',
            'curp',
            'grupo_actual',
            'ciclo_inscripcion'
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'grupo_actual': forms.HiddenInput(),  # Ocultamos porque ya sabemos el grupo
            'ciclo_inscripcion': forms.HiddenInput()  # Ocultamos porque viene del grupo
        }
        labels = {
            'apellido_materno': 'Apellido materno (opcional)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizamos el formulario según necesidades
        self.fields['curp'].required = False
        self.fields['fecha_nacimiento'].required = False


class ImportarEstudiantesForm(forms.Form):
    archivo = forms.FileField(
        label='Archivo de estudiantes',
        validators=[FileExtensionValidator(allowed_extensions=['xlsx', 'csv'])],
        help_text="Suba un archivo Excel (.xlsx) o CSV con: Nombre, Apellidos y CURP (opcional)"
    )

    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')
        if archivo:
            if archivo.size > 5 * 1024 * 1024:  # 5MB
                raise forms.ValidationError("El archivo es demasiado grande (máximo 5MB)")
            # Verificar que no contenga columna de matrícula
            try:
                if archivo.name.endswith('.xlsx'):
                    df = pd.read_excel(archivo, engine='openpyxl', nrows=1)
                elif archivo.name.endswith('.csv'):
                    df = pd.read_csv(archivo, nrows=1)

                if 'Matrícula' in df.columns:
                    raise forms.ValidationError("El archivo NO debe incluir matrículas (ya existen en el sistema)")
            except:
                pass
        return archivo


class FiltroEstudiantesForm(forms.Form):
    busqueda = forms.CharField(
        required=False,
        label='Buscar',
        widget=forms.TextInput(attrs={
            'placeholder': 'Matrícula o nombre...',
            'class': 'form-control'
        })
    )

    orden = forms.ChoiceField(
        required=False,
        choices=[
            ('apellido', 'Apellido (A-Z)'),
            ('-apellido', 'Apellido (Z-A)'),
            ('matricula', 'Matrícula (ascendente)'),
            ('-matricula', 'Matrícula (descendente)')
        ],
        initial='apellido',
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class EdicionRapidaEstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = ['nombre', 'apellido_paterno', 'apellido_materno']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido_paterno': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido_materno': forms.TextInput(attrs={'class': 'form-control'})
        }
