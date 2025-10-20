from django.urls import path, include

from padres.views import ReprogramarCitaView
from . import views
from django.conf import settings
from django.conf.urls.static import static  # ¡Importante!
from ticket_soporte.views import panel_tickets_profesor
from .views import ReprogramarCitaProfesorView

app_name = 'profesores'

urlpatterns = [
    path('registro/', views.registro_profesor_view, name='registro_profesor'),
    path('login/', views.login_profesor_view, name='login_profesor'),
    path('logout/', views.logout_profesor_view, name='logout_profesor'),
    path('index/', views.dashboard_profesor_view, name='dashboard_profesor'),
    path('configuracion/', views.configuracion_view, name='configuracion_profesor'),
    path('editar_perfil/', views.editar_perfil_view, name='editar_perfil_profesor'),
    # ... otras URLs
    path('clases/', views.profesor_dashboard, name='panel_horario'),
    path('clases/agregar/', views.agregar_clase, name='agregar_clase'),
    path('clases/editar/<int:clase_id>/', views.editar_clase, name='editar_clase'),
    path('clases/eliminar/<int:clase_id>/', views.eliminar_clase, name='eliminar_clase'),
    path('clases/<int:clase_id>/horarios/', views.gestionar_horarios, name='gestionar_horarios'),
    path('horarios/eliminar/<int:horario_id>/', views.eliminar_horario, name='eliminar_horario'),

    # Tiempos libres
    path('tiempos-libres/agregar/', views.agregar_tiempo_libre, name='agregar_tiempo_libre'),
    path('tiempos-libres/editar/<int:id>/', views.editar_tiempo_libre, name='editar_tiempo_libre'),
    path('tiempos-libres/eliminar/<int:id>/', views.eliminar_tiempo_libre, name='eliminar_tiempo_libre'),

    # Citas
    path('citas/', views.PanelCitasProfesor.as_view(), name='panel_citas'),
    path('citas/clase/<int:clase_id>/estudiantes/', views.ListaEstudiantesCitas.as_view(),
         name='lista_estudiantes_citas'),
    path('citas/estudiante/<int:estudiante_id>/nueva/', views.CrearCitaEstudiante.as_view(),
         name='crear_cita_estudiante'),
    path('citas/prioritaria/<int:estudiante_id>/', views.CrearCitaPrioritariaView.as_view(),
         name='crear_cita_prioritaria'),
    path('citas/calendario/', views.CalendarioCitasProfesor.as_view(), name='calendario_citas'),
    path('citas/historial/', views.HistorialCitasView.as_view(), name='historial_citas'),
    path('citas/reprogramar/<int:cita_id>/', ReprogramarCitaProfesorView.as_view(), name='reprogramar_cita'),
    path('citas/<int:cita_id>/completar/', views.marcar_cita_como_completada, name='completar_cita'),
    path('citas/<int:cita_id>/detalles/', views.detalles_cita, name='detalles_cita'),

    # Tickets
    path('tickets/', panel_tickets_profesor, name='panel_tickets'),
    path('tickets/<int:pk>/', views.DetalleTicketView.as_view(), name='detalle_ticket'),

    # Notificaciones
    path('notificaciones/', views.panel_notificaciones_profesor, name='panel_notificaciones'),
    path('notificaciones/marcar-leida/<int:notificacion_id>/', views.marcar_notificacion_leida,
         name='marcar_notificacion_leida'),

    # Tema
    path('tema/', views.profesor_theme_settings, name='theme_settings'),

    # APIS
    path('api/profesor/eventos/', views.api_eventos_profesor, name='api_eventos_profesor'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
