from django.urls import path
from . import views

app_name = 'preguntas'

urlpatterns = [
    # path('buscar-respuesta/', views.buscar_respuesta, name='buscar_respuesta'),
    # path('preguntas-frecuentes/', views.obtener_preguntas_frecuentes, name='preguntas_frecuentes'),

    path('', views.faq_lista, name='faq_lista'),
    path('rol/<str:rol>/', views.faq_por_rol, name='faq_por_rol'),
    path('pregunta/<int:pk>/', views.pregunta_detalle, name='pregunta_detalle'),
    path('buscar/', views.buscar_preguntas, name='buscar_preguntas'),

    # API para búsqueda AJAX (mantener compatibilidad)
    path('api/buscar/', views.buscar_respuesta, name='buscar_respuesta'),
    path('api/preguntas-frecuentes/', views.obtener_preguntas_frecuentes, name='obtener_preguntas_frecuentes'),
    path('demo/', views.demo_chatbot, name='demo_chatbot'),
    path('demo-completa/', views.demo_completa_view, name='demo_completa'),

]

