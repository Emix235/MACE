from django.contrib import admin
from .models import NivelEducativo, PeriodoEscolar, CicloEscolar, Grado, Grupo

# Registro único de modelos
admin.site.register(NivelEducativo)
admin.site.register(PeriodoEscolar)
admin.site.register(CicloEscolar)
admin.site.register(Grado)
admin.site.register(Grupo)