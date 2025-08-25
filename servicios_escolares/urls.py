from django.template.context_processors import static
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf.urls.static import static
from MACE import settings
from . import views
from estudiantes.views import (crear_ciclo_paso1, editar_nivel_view, editar_ciclo, configurar_grados,
                               asignar_estudiantes, panel_grupos, importar_estudiantes, EditarEstudianteView,
                               panel_grupos_padres)
from notificaciones.views import PanelServiciosEscolaresView, PanelNotificacionesView, NotificationTypesView
from ticket_soporte.views import TodosTicketsView
from .views import ReprogramarCitaServicioEscolarView, CrearCitaPrioritariaServiciosEscolaresView

app_name = 'servicios_escolares'

urlpatterns = [
                  # Redirección de / a /servicios_escolares/
                  path('', RedirectView.as_view(url='servicios_escolares/', permanent=False)),

                  path('servicios_escolares/', include([
                      path('registro/', views.registro_view, name='registro'),
                      path('', views.login_view, name='login'),
                      path('logout/', views.logout_view, name='logout'),
                      path('dashboard/', views.dashboard_view, name='dashboard'),
                      path('configuracion/', views.configuracion_view, name='configuracion'),
                      path('editar-perfil/', views.perfil_view, name='perfil'),
                      path('editar/', views.editar_view, name='editar'),
                      path('panel/', views.panel_principal, name='panel-principal'),
                      path('gestion/', views.gestion_ciclos, name='gestion_ciclos'),
                      path('nivel/editar/<int:pk>/', editar_nivel_view, name='editar_nivel'),
                      path('ciclo/paso1/', crear_ciclo_paso1, name='paso1_ciclo'),
                      path('ciclo/<int:ciclo_id>/grados/', configurar_grados, name='paso2_grados'),
                      path('ciclo/<int:ciclo_id>/estudiantes/', asignar_estudiantes, name='paso3_estudiante'),
                      path('ciclo/editar/<int:pk>/', editar_ciclo, name='editar_ciclo'),
                      path('panel-grupos/', panel_grupos, name='panel-grupos'),
                      path('panel-grupos-horarios/', views.panel_horarios_servicio_escolar,
                           name='panel-horarios-grupos'),

                      # Registros, listas, control parental, gestión de usuarios
                      path('panel-profesores/', views.panel_profesores, name='panel-profesores'),
                      path('profesor/<int:profesor_id>/', views.detalle_profesor, name='detalle_profesor'),
                      path('compartir-registro/', views.compartir_registro_view, name='compartir_registro'),
                      path('enviar-invitacion/', views.enviar_invitacion_view, name='enviar_invitacion'),
                      path('importar-estudiantes/<int:grupo_id>', importar_estudiantes, name='importar_estudiantes'),
                      path('estudiantes/editar/<int:pk>/', EditarEstudianteView.as_view(), name='editar_estudiante'),
                      path('panel-grupos-padres/', panel_grupos_padres, name='panel_grupos_padres'),
                      path('asignar-padres-grupo/<int:grupo_id>', views.asignar_padres_grupo,
                           name='asignar_padres_grupo'),
                      path('asignar-padre/<int:estudiante_id>/', views.asignar_padre_estudiante, name='asignar_padre'),

                      path('invitacion/<str:token>/', views.invitacion_registro, name='invitacion_registro'),
                      path('procesar-invitacion/<str:token>/', views.procesar_invitacion, name='procesar_invitacion'),

                      # Citas
                      path('citas/', views.panel_citas_servicio_escolar, name='panel_citas'),
                      path('citas/historial/<int:estudiante_id>/', views.historial_citas_estudiante,
                           name='historial_citas'),
                      path('mis-citas/', views.historial_citas_servicio_escolar, name='mis_citas'),
                      path('agendar-cita/<int:estudiante_id>/', views.agendar_cita_estudiante, name='agendar_cita'),
                      path('citas/<int:cita_id>/confirmar/', views.confirmar_cita_servicio,
                           name='confirmar_cita_servicio'),
                      path('citas/<int:cita_id>/cancelar/', views.cancelar_cita_servicio,
                           name='cancelar_cita_servicio'),
                      path('citas/<int:cita_id>/detalle/', views.detalle_cita_modal, name='detalle_cita'),
                      path('citas/reprogramar/<int:cita_id>/', ReprogramarCitaServicioEscolarView.as_view(),
                           name='reprogramar_cita'),
                      path('citas/crear-prioritaria/<int:estudiante_id>/',
                           CrearCitaPrioritariaServiciosEscolaresView.as_view(), name='crear_cita_prioritaria'),
                      path('citas/<int:cita_id>/completar/', views.marcar_cita_como_completada, name='completar_cita'),

                      # Notificaciones
                      path('servicios/notificaciones/', PanelServiciosEscolaresView.as_view(),
                           name='panel_notificaciones'),
                      path('servicios/notificaciones/tipos/', PanelNotificacionesView.as_view(),
                           name='panel_tipos_notificaciones'),
                      path('tipos-notificaciones/', NotificationTypesView.as_view(), name='notification_types'),

                      # Tickets de Soporte
                      path('tickets/', TodosTicketsView.as_view(), name='todos_tickets'),
                      path('tickets/<int:pk>/', views.DetalleTicketView.as_view(), name='detalle_ticket'),

                      # Tema
                      path('servicios/theme-settings/', views.theme_settings, name='theme_settings'),

                      # Calendario
                      path('eventos/', views.api_eventos_servicio_escolar, name='eventos_servicio_escolar'),

                      # Listas
                      path('padres-por-grupo/', views.lista_grados_grupos_padres, name='padres_por_grupo'),
                      path('padre/<int:padre_id>/', views.detalle_padre, name='detalle_padre'),

                      # Especial
                      path('padre/<int:padre_id>/marcar-leidas/', views.marcar_todas_leidas,
                           name='marcar_todas_leidas'),
                  ])),
              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
