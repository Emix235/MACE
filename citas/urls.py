from django.urls import path
from . import views

app_name = 'citas'

urlpatterns = [
    path('citas/<int:cita_id>/cancelar/', views.cancelar_cita_view, name='cancelar_cita'),
]

# path('login/', views.login_view, name='login'),
# path('dashboard/', views.dashboard_view, name='dashboard'),