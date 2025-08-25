from django import forms
from .models import EstiloUsuario, ConfiguracionEstilos


class EstiloUsuarioForm(forms.ModelForm):
    class Meta:
        model = EstiloUsuario
        fields = ['tema_preferido', 'color_primario', 'color_secundario', 'fuente', 'tamanio_fuente']
        widgets = {
            'color_primario': forms.TextInput(attrs={'type': 'color'}),
            'color_secundario': forms.TextInput(attrs={'type': 'color'}),
        }


class ConfiguracionEstilosForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionEstilos
        fields = ['habilitar_cambio_estilos']
