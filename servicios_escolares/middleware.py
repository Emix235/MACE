from datetime import timezone
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist
import logging
from django.urls.exceptions import NoReverseMatch

from servicios_escolares.models import ServicioEscolar
logger = logging.getLogger(__name__)


class NotificacionesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # print("Middleware de notificaciones inicializado")

    def __call__(self, request):
        response = self.get_response(request)

        start_time = timezone.now()
        # print(f"[Notificaciones] Iniciando procesamiento para sesión: {request.session.session_key}")

        if not request.session.get('credenciales'):
            # print("[Notificaciones] No hay credenciales en sesión, omitiendo")
            return response

        try:
            usuario_id = request.session['credenciales']['id']
            # print(f"[Notificaciones] Buscando usuario con ID: {usuario_id}")

            usuario = ServicioEscolar.objects.get(id=usuario_id)
            # print(f"[Notificaciones] Usuario encontrado: {usuario}")

            # Obtener notificaciones
            # print("[Notificaciones] Obteniendo notificaciones...")
            notificaciones = usuario.notificaciones.order_by('-created_at').values(
                'id', 'title', 'message', 'is_read', 'created_at', 'event_type', 'target_id'
            )  # Sin [:10]
            # print(f"[Notificaciones] Total notificaciones encontradas: {len(notificaciones)}")

            notificaciones_list = []
            for notif in notificaciones:
                try:
                    # print(f"[Notificaciones] Procesando notificación ID: {notif['id']} - Tipo: {notif['event_type']}")

                    notif_dict = {
                        'id': notif['id'],
                        'title': notif['title'],
                        'message': notif['message'],
                        'is_read': notif['is_read'],
                        'fecha': notif['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                        'event_type': notif['event_type'],
                        'url': self._get_notification_url(notif['event_type'], notif.get('target_id'))
                    }

                    # print(f"[Notificaciones] URL generada para notif {notif['id']}: {notif_dict['url']}")
                    notificaciones_list.append(notif_dict)

                except Exception as e:
                    #print(f"[ERROR] Procesando notificación {notif.get('id')}: {str(e)}")
                    continue

            # Contar no leídas
            no_leidas = usuario.notificaciones.filter(is_read=False).count()
            # print(f"[Notificaciones] Notificaciones no leídas: {no_leidas}")

            # Actualizar sesión
            request.session['notificaciones_no_leidas'] = no_leidas
            request.session['notificaciones_todas'] = notificaciones_list
            request.session.modified = True
            # print("[Notificaciones] Sesión actualizada con notificaciones")

            duration = (timezone.now() - start_time).total_seconds()
            # print(f"[Notificaciones] Procesamiento completado en {duration:.2f} segundos")

        except ServicioEscolar.DoesNotExist:
            print(f"[ERROR] Usuario con ID {usuario_id} no encontrado")
        except KeyError as e:
            print(f"[ERROR] Falta clave en sesión: {str(e)}")
        except Exception as e:
            print(f"[ERROR] Inesperado: {str(e)}")

        return response

    def _get_notification_url(self, event_type, target_id=None):
        from notificaciones.models import Notification
        """Genera URL para la notificación usando la misma lógica que el modelo"""
        # print(f"[Notificaciones] Generando URL para {event_type} con target_id: {target_id}")

        try:
            # Usamos el EVENT_TYPES del modelo Notification
            event_info = Notification.EVENT_TYPES.get(event_type, Notification.EVENT_TYPES['custom'])
            url_name = event_info[0]
            # print(f"[Notificaciones] URL name encontrada: {url_name}")

            # Casos especiales que no necesitan target
            if event_type in ['registro_padre', 'servicio_nuevo_padre']:
                url = reverse('servicios_escolares:panel_grupos_padres')
                # print(f"[Notificaciones] URL especial generada: {url}")
                return url

            # Construir URL basada en si necesita parámetro o no
            if target_id:
                try:
                    # Intenta construir la URL con el ID del target
                    url = reverse(url_name, kwargs={'pk': target_id})
                    # print(f"[Notificaciones] URL con parámetro generada: {url}")
                    return url
                except:
                    # Si falla, intenta sin parámetro
                    url = reverse(url_name)
                    # print(f"[Notificaciones] URL sin parámetro (fallback): {url}")
                    return url
            else:
                url = reverse(url_name)
                # print(f"[Notificaciones] URL simple generada: {url}")
                return url

        except Exception as e:
            print(f"[ERROR] Generando URL: {str(e)}")
            return reverse('servicios_escolares:dashboard')