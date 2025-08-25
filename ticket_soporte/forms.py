from django import forms
from .models import TicketSoporte


class TicketSoporteForm(forms.ModelForm):
    class Meta:
        model = TicketSoporte
        fields = ['asunto', 'descripcion']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 5}),
        }

