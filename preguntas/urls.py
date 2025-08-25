from django.urls import path
from . import views

app_name = 'preguntas'

urlpatterns = [
    path('buscar-respuesta/', views.buscar_respuesta, name='buscar_respuesta'),
    path('preguntas-frecuentes/', views.obtener_preguntas_frecuentes, name='preguntas_frecuentes'),
]

