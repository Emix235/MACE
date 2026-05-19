from django.template.context_processors import static
from django.urls import path
from MACE import settings
from . import views
from ticket_soporte.views import CrearTicketSoporteView
from .views import ReprogramarCitaView

app_name = 'padres'

urlpatterns = [
    path('registro/', views.registro_padre_view, name='registro_padre'),
    path('', views.login_padre_view, name='login_padre'),
    path('logout/', views.logout_padre_view, name='logout_padre'),
    path('configuracion/', views.configuracion_padre_view, name='configuracion_padre'),
    path('editar_perfil/', views.editar_perfil_padre_view, name="editar_perfil_padre"),
    path('index/', views.dashboard_padre_view, name="dashboard_padre"),
    # urls.py (app padres)
    path('registro/<int:estudiante_id>/', views.registro_padre_personalizado, name='registro_padre_estudiante'),
    path('registro/<uuid:token>/', views.registro_padre_token, name='registro_padre_token'),
    path('panel/', views.panel_estudiante, name='panel_estudiante'),
    path('estudiante/detalles/<int:estudiante_id>/', views.detalles_estudiante, name='detalles_estudiante'),

    path('profesores_disponibles/', views.profesores_disponibles, name='profesores_disponibles'),

    path('citas/', views.mis_citas, name='mis_citas'),
    path('citas/confirmar/<int:cita_id>/', views.confirmar_cita, name='confirmar_cita'),
    path('citas/crear/profesor/<int:profesor_id>/', views.CrearCitaProfesorView.as_view(), name='crear_cita_profesor'),
    path('profesor/<int:profesor_id>/disponibilidad/', views.VerDisponibilidadProfesorView.as_view(),
         name='ver_disponibilidad_profesor'),

    path('citas/crear/servicio/<int:servicio_id>/', views.CrearCitaServicioView.as_view(), name='crear_cita_servicio'),
    path('citas/nueva/<int:profesor_id>/', views.CrearCitaView.as_view(), name='crear_cita'),
    path('citas/reprogramar/<int:cita_id>/', ReprogramarCitaView.as_view(), name='reprogramar_cita'),

    path('debug/session/', views.debug_session, name='debug_session'),

    path('soporte/crear-ticket/', CrearTicketSoporteView.as_view(), name='crear_ticket_soporte'),
    path('mis-tickets/', views.MisTicketsView.as_view(), name='tickets_padre'),
    path('tickets/<int:pk>/', views.DetalleTicketView.as_view(), name='detalle_ticket'),

    path('notificaciones/', views.NotificacionesPadreListView.as_view(), name='panel_notificaciones'),
    path('notificaciones/marcar-leida/<int:notificacion_id>/', views.marcar_notificacion_leida,
         name='marcar_notificacion_leida'),
    path('notificaciones/marcar-todas-leidas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),

    path('tema/', views.padre_theme_settings, name='theme_settings'),

    path('calendar/', views.calendar_view, name='calendar'),

    path('profesores/<int:profesor_id>/seleccionar-fecha/', views.SeleccionarFechaCitaView.as_view(),
         name='seleccionar_fecha_cita'),

    path('profesores/<int:profesor_id>/crear-cita-calendario/',
         views.CrearCitaProfesorCalendarioView.as_view(),
         name='crear_cita_calendario'),

    path('profesores/<int:profesor_id>/horarios-disponibles/', views.obtener_horarios_disponibles, name='obtener_horarios_disponibles'),

    # APIS
    path('api/eventos-padre/', views.api_eventos_padre, name='api_eventos_padre'),

]

# ¡Esta línea es clave para servir archivos media en desarrollo!
