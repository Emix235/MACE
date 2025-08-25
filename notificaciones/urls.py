# notifications/urls.py
from django.urls import path
from .views import marcar_notificacion_leida, marcar_todas_leidas

app_name = 'notificaciones'

urlpatterns = [
    path('marcar-leida/<int:notification_id>/', marcar_notificacion_leida, name='marcar_notificacion_leida'),
    path('marcar-todas-leidas/', marcar_todas_leidas, name='marcar_todas_leidas'),
    # ... otras URLs ...
]