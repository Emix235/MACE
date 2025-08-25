from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static  # ¡Importante!

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('servicios_escolares.urls')),  # Servicios Escolares en raíz
    path('profesores/', include('profesores.urls')),
    path('padres/', include('padres.urls')),
    path('notificaciones/', include('notificaciones.urls')),
    path('citas/', include('citas.urls')),
    path('preguntas/', include('preguntas.urls')),
    path('notas/', include('nota.urls')),
    path('formularios/', include('formularios.urls')),
]

# ¡Esta línea es clave para servir archivos media en desarrollo!
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
