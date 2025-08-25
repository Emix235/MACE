from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from openpyxl.descriptors import Max

import preguntas
from .models import Encuesta, Pregunta, EncuestaAplicada, RespuestaRetroalimentacion, RetroalimentacionAplicada, \
    RetroalimentacionCita, PreguntaRetroalimentacion
from estudiantes.models import CicloEscolar
from django.forms import BaseModelFormSet


# ENCUESTA
class EncuestaForm(forms.ModelForm):
    class Meta:
        model = Encuesta
        fields = ['titulo', 'descripcion']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        self.creada_por = kwargs.pop('creada_por', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.creada_por:
            instance.creada_por = self.creada_por
        if commit:
            instance.save()
            # Solo crear preguntas por defecto si es una nueva encuesta
            if not instance.pk:
                instance.crear_preguntas_por_defecto()
        return instance


class EditarEncuestaForm(forms.ModelForm):
    crear_nueva_version = forms.BooleanField(
        required=False,
        initial=False,
        label="Crear nueva versión",
        help_text="Recomendado si ya hay respuestas (mantiene versiones anteriores)",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'data-bs-toggle': 'toggle'
        })
    )

    class Meta:
        model = Encuesta
        fields = ['titulo', 'descripcion']
        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Título de la encuesta'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la encuesta'
            })
        }
        labels = {
            'titulo': 'Título',
            'descripcion': 'Descripción'
        }


class PreguntaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicar clases Bootstrap a todos los campos
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

            # Añadir estilos adicionales según el campo
            if field_name == 'texto':
                field.widget.attrs.update({'rows': '3', 'style': 'resize: vertical;'})
            elif field_name == 'orden':
                field.widget.attrs.update({'style': 'width: 80px;'})

    class Meta:
        model = Pregunta
        fields = '__all__'


def get_pregunta_formset(encuesta=None, extra=1):
    return inlineformset_factory(
        Encuesta,
        Pregunta,
        form=PreguntaForm,
        extra=extra,
        can_delete=True,
        widgets={
            'DELETE': forms.CheckboxInput(attrs={
                'class': 'form-check-input delete-checkbox'
            })
        }
    )


class AplicarEncuestaForm(forms.ModelForm):
    confirmar = forms.BooleanField(
        required=True,
        initial=False,
        label="Confirmo que esta es la versión final",
        help_text="No podrá modificar esta encuesta después de publicarla",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = EncuestaAplicada
        fields = ['ciclo_escolar']
        widgets = {
            'ciclo_escolar': forms.Select(attrs={'class': 'form-select'})
        }

    def __init__(self, *args, **kwargs):
        self.encuesta = kwargs.pop('encuesta', None)
        self.aplicada_por = kwargs.pop('aplicada_por', None)
        super().__init__(*args, **kwargs)

        if self.encuesta:
            # Filtrar ciclos no aplicados aún para esta encuesta base
            ciclos_aplicados = EncuestaAplicada.objects.filter(
                encuesta__encuesta_base=self.encuesta.encuesta_base or self.encuesta
            ).values_list('ciclo_escolar_id', flat=True)

            self.fields['ciclo_escolar'].queryset = CicloEscolar.objects.exclude(
                id__in=ciclos_aplicados
            )

    def clean(self):
        cleaned_data = super().clean()
        if self.encuesta and self.encuesta.aplicaciones.exists():
            raise forms.ValidationError(
                "Esta versión ya fue aplicada. Cree una nueva versión para modificaciones."
            )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.encuesta = self.encuesta
        instance.aplicada_por = self.aplicada_por

        if commit:
            # Marcamos la encuesta como no plantilla antes de guardar
            self.encuesta.es_plantilla = False
            self.encuesta.save()
            instance.save()
        return instance


# RETROALIMENTACIÓN


class RetroalimentacionForm(forms.ModelForm):
    class Meta:
        model = RetroalimentacionCita
        fields = ['titulo', 'descripcion']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        self.creada_por = kwargs.pop('creada_por', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.creada_por:
            instance.creada_por = self.creada_por
        if commit:
            instance.save()
            # Solo crear preguntas por defecto si es una nueva retroalimentación
            if not instance.pk:
                instance.crear_preguntas_por_defecto()
        return instance


class EditarRetroalimentacionForm(forms.ModelForm):
    crear_nueva_version = forms.BooleanField(
        required=False,
        initial=False,
        label="Crear nueva versión",
        help_text="Recomendado si ya hay respuestas (mantiene versiones anteriores)",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'data-bs-toggle': 'toggle'
        })
    )

    class Meta:
        model = RetroalimentacionCita
        fields = ['titulo', 'descripcion']
        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Título de la retroalimentación'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción de la retroalimentación'
            })
        }
        labels = {
            'titulo': 'Título',
            'descripcion': 'Descripción'
        }


class PreguntaRetroalimentacionForm(forms.ModelForm):
    DELETE = forms.BooleanField(
        required=False,
        label="Eliminar esta pregunta",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input delete-checkbox'})
    )

    class Meta:
        model = PreguntaRetroalimentacion
        exclude = ['activa']  # Oculta el campo 'activa' del formulario completamente

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si está marcado para borrar, desactivar validación
        # if self.instance and self.instance.pk and 'activa' not in self.data:
        #    self.fields['activa'].initial = self.instance.activa

        if self.data.get(self.add_prefix('DELETE')) == 'on':
            for field in self.fields:
                self.fields[field].required = False
                self.fields[field].widget.attrs['disabled'] = 'disabled'

    def has_changed(self):
        if not self.instance.pk:
            prefix = self.prefix
            return any(
                self.data.get(f"{prefix}-{field}")
                for field in self.fields
                if field not in ['DELETE', 'id', 'orden']
            )
        return super().has_changed()


def get_pregunta_retroalimentacion_formset(retroalimentacion=None, extra=1):
    return inlineformset_factory(
        RetroalimentacionCita,
        PreguntaRetroalimentacion,
        form=PreguntaRetroalimentacionForm,
        extra=extra,
        can_delete=True,
        widgets={
            'DELETE': forms.CheckboxInput(attrs={
                'class': 'form-check-input delete-checkbox'
            })
        }
    )


class AplicarRetroalimentacionForm(forms.ModelForm):
    confirmar = forms.BooleanField(
        required=True,
        initial=False,
        label="Confirmo que esta es la versión final",
        help_text="No podrá modificar esta retroalimentación después de publicarla",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = RetroalimentacionAplicada
        fields = []  # No necesitamos campos adicionales para retroalimentación de citas

    def __init__(self, *args, **kwargs):
        self.retroalimentacion = kwargs.pop('retroalimentacion', None)
        self.aplicada_por = kwargs.pop('aplicada_por', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if self.retroalimentacion and self.retroalimentacion.aplicaciones.exists():
            raise forms.ValidationError(
                "Esta versión ya fue aplicada. Cree una nueva versión para modificaciones."
            )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.retroalimentacion = self.retroalimentacion
        instance.aplicada_por = self.aplicada_por

        if commit:
            # Marcamos la retroalimentación como no plantilla antes de guardar
            self.retroalimentacion.es_plantilla = False
            self.retroalimentacion.save()
            instance.save()
        return instance


class RespuestaRetroalimentacionForm(forms.ModelForm):
    pregunta_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)  # Campo adicional

    class Meta:
        model = RespuestaRetroalimentacion
        fields = ['valor_numero', 'respuesta_si_no', 'explicacion', 'respuesta_texto']
        widgets = {
            'pregunta_id': forms.HiddenInput(),  # Añade esto
            'valor_numero': forms.NumberInput(attrs={
                'class': 'form-control escala-input',
                'min': '1',
                'max': '5',
                'style': 'width: 80px;'
            }),
            'respuesta_si_no': forms.RadioSelect(attrs={
                'class': 'form-check-input'
            }, choices=[(True, 'Sí'), (False, 'No')]),
            'explicacion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Explica tu respuesta...'
            }),
            'respuesta_texto': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Escribe tu respuesta aquí...'
            })
        }

    def __init__(self, *args, **kwargs):
        self.pregunta = kwargs.pop('pregunta', None)
        print("Pregunta recibida:", self.pregunta)
        super().__init__(*args, **kwargs)

        if self.pregunta:
            self.fields['pregunta_id'] = forms.IntegerField(
                initial=self.pregunta.id,
                widget=forms.HiddenInput()
            )
            print("Tipo de pregunta:", self.pregunta.tipo)
            self.instance.pregunta = self.pregunta  # Opcional, para que esté accesible como instance.pregunta

            if self.pregunta.tipo == 'escala_5':
                self.fields['valor_numero'].required = True
                del self.fields['respuesta_si_no']
                del self.fields['explicacion']
                del self.fields['respuesta_texto']
            elif self.pregunta.tipo == 'si_no':
                self.fields['respuesta_si_no'].required = True
                del self.fields['valor_numero']
                del self.fields['explicacion']
                del self.fields['respuesta_texto']
            elif self.pregunta.tipo == 'si_no_explicacion':
                self.fields['respuesta_si_no'].required = True
                self.fields['explicacion'].required = True
                del self.fields['valor_numero']
                del self.fields['respuesta_texto']
            elif self.pregunta.tipo == 'texto':
                self.fields['respuesta_texto'].required = True
                del self.fields['valor_numero']
                del self.fields['respuesta_si_no']
                del self.fields['explicacion']


class PreguntaRetroalimentacionFormSet(BaseInlineFormSet):
    def __init__(self, *args, preguntas=None, **kwargs):
        self.preguntas = preguntas
        super().__init__(*args, **kwargs)

        for form in self.forms:
            # Solo establecer DELETE=True si explícitamente está en initial o data
            if form.initial:
                form.fields['DELETE'].initial = form.initial.get('DELETE', False)

            # Solo deshabilitar campos si realmente está marcado para borrar
            delete_checked = (
                                     form.data and
                                     form.data.get(form.add_prefix('DELETE')) == 'on'
                             ) or (
                                     form.initial and
                                     form.initial.get('DELETE') is True
                             )

            if delete_checked:
                for field in form.fields:
                    if field != 'DELETE':  # No deshabilitar el checkbox DELETE
                        form.fields[field].required = False
                        form.fields[field].widget.attrs['disabled'] = 'disabled'

    # CODI GO SENSIBLE, PARA INGRESAR CORRECTAMENTE TODAS LAS PREGUNTAS NUEVAS
    def clean(self):
        super().clean()

        active_questions = 0

        for form in self.forms:
            # Leer DELETE de forma segura
            delete = form.cleaned_data.get('DELETE') if hasattr(form, 'cleaned_data') else form.data.get(
                form.add_prefix('DELETE'))
            if delete in [True, 'on', 'true', '1']:
                form._errors.clear()
                continue

            if not self._form_has_data(form):
                continue

            texto = (getattr(form, 'cleaned_data', {}) or {}).get('texto') or form.data.get(form.add_prefix('texto'))
            tipo = (getattr(form, 'cleaned_data', {}) or {}).get('tipo') or form.data.get(form.add_prefix('tipo'))

            if not texto:
                form.add_error('texto', 'Este campo es requerido')
            else:
                active_questions += 1

            if not tipo:
                form.add_error('tipo', 'Este campo es requerido')

        if active_questions == 0 and not any(form.instance.pk for form in self.forms):
            raise forms.ValidationError("Debe haber al menos una pregunta activa")

    def _form_has_data(self, form):
        """Determina si el formulario tiene datos válidos no vacíos."""
        for field in form.fields:
            if field in ['DELETE', 'id']:
                continue
            key = form.add_prefix(field)
            value = form.data.get(key, '')
            if isinstance(value, str) and value.strip():
                return True
            elif value:  # Si es otro tipo y no está vacío
                return True
        return False

    def save(self, commit=True):
        """Guarda solo forms con datos"""
        instances = []
        deleted_ids = []

        for form in self.forms:
            print(
                f"[DEBUG] Guardando pregunta: {form.cleaned_data.get('texto')} - DELETE: {form.cleaned_data.get('DELETE')}")

            if form.cleaned_data.get('DELETE', False):
                if form.instance.pk:
                    deleted_ids.append(form.instance.pk)
                    form.instance.delete()
                continue

            if self._form_has_data(form):
                instance = form.save(commit=False)
                instances.append(instance)

        if commit:
            # Guardar las instancias primero
            for instance in instances:
                instance.save()

            # Eliminar definitivamente las marcadas para borrar
            if deleted_ids:
                PreguntaRetroalimentacion.objects.filter(
                    pk__in=deleted_ids
                ).delete()

            self.save_m2m()

        return instances


'''
 'valor_numero': forms.NumberInput(attrs={
                'class': 'form-control escala-input',
                'min': '1',
                'max': '5',
                'style': 'width: 80px;'
            }),
'''
