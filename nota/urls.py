from django.urls import path
from . import views

app_name = 'notas'

urlpatterns = [
    path('crear/', views.crear_nota, name='crear_nota'),
    path('lista_notas/', views.lista_notas, name='lista_notas'),
    path('<int:pk>/', views.detalle_nota, name='detalle_nota'),
    path('<int:pk>/eliminar/', views.eliminar_nota, name='eliminar_nota'),
]