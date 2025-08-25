from django import forms
from .models import Nota


class NotaForm(forms.ModelForm):
    class Meta:
        model = Nota
        fields = ['titulo', 'contenido', 'tipo', 'imagen', 'documento', 'audio']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Título de la nota'}),
            'contenido': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Contenido de la nota'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'imagen': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'documento': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'audio': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }
        labels = {
            'titulo': 'Título',
            'contenido': 'Contenido',
            'tipo': 'Tipo de nota',
            'imagen': 'Imagen adjunta',
            'documento': 'Documento adjunto',
            'audio': 'Audio adjunto',
        }

