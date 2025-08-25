from django.urls import path
from . import views
from .views import PanelMetricasView

app_name = 'formularios'

urlpatterns = [
    # Encuestas
    path('encuestas/', views.lista_encuestas_servicio, name='lista_encuestas_servicio'),
    path('servicio/encuestas/nueva/', views.gestionar_encuesta, name='nueva_encuesta'),
    path('aplicar/', views.aplicar_encuesta, name='aplicar_encuesta'),
    path('finalizar-encuesta/', views.finalizar_encuesta, name='finalizar_encuesta'),
    path('editar/', views.editar_encuesta, name='editar_encuesta'),
    path('encuesta/', views.contestar_encuesta, name='contestar_encuesta'),
    path('encuestas/respuestas/<int:encuesta_aplicada_id>/', views.detalle_respuestas_encuesta,
         name='detalle_respuestas_encuesta'),
    path('versiones-encuesta/', views.detalle_versiones_encuesta, name='detalle_versiones_encuesta'),
    path('versiones-encuesta/<int:pk>/', views.detalle_versiones_encuesta, name='detalle_versiones_encuesta'),

    # Retroalimentación

    path('citas/<int:cita_id>/completar/', views.marcar_cita_completada, name='marcar_cita_completada'),
    path('retroalimentacion/', views.gestionar_retroalimentacion, name='gestionar_retroalimentacion'),
    path('retroalimentacion/editar/<int:pk>/', views.editar_retroalimentacion, name='editar_retroalimentacion'),
    path('preguntas/historial/', views.historial_preguntas, name='historial_preguntas'),
    path('preguntas/<int:pregunta_id>/detalle/', views.detalle_pregunta, name='detalle_pregunta'),
    path('preguntas/<int:pregunta_id>/activar/', views.activar_pregunta, name='activar_pregunta'),
    path('preguntas/<int:pregunta_id>/eliminar/', views.eliminar_pregunta, name='eliminar_pregunta'),

    path('retroalimentacion/aplicar/<int:pk>/', views.aplicar_retroalimentacion, name='aplicar_retroalimentacion'),
    # path('retroalimentacion/historial/', views.HistorialRetroalimentacionPadres.as_view(),
    #          name='historial_retroalimentacion'),
    path('citas/<int:cita_id>/retroalimentacion/', views.responder_retroalimentacion,
         name='responder_retroalimentacion'),
    path('profesores/retroalimentaciones/', views.retroalimentaciones_profesores,
         name='retroalimentaciones_profesores'),
    path('profesores/retroalimentaciones/<int:profesor_id>/', views.detalle_retroalimentaciones_profesor,
         name='detalle_retroalimentaciones_profesor'),

    path('servicio-escolar/retroalimentaciones/', views.retroalimentaciones_servicio_escolar,
         name='retroalimentaciones_servicio_escolar'),

    path('citas/completar-pasadas/', views.completar_citas_pasadas, name='completar_citas_pasadas'),

    path('profesores-destacados/', views.tablero_profesores_destacados, name='profesores_destacados'),
    path('metricas/', PanelMetricasView.as_view(), name='panel_metricas'),

]
