import unicodedata

from padres.models import Padre

def clean_string(text):
    try:
        # Nos aseguramos de que 'text' es un string Unicode
        text = str(text)

        # Solo procesamos caracteres que sean válidos en Unicode
        return ''.join(
            (char if unicodedata.category(char) != 'So' else '') for char in text if
            isinstance(char, str) and len(char) == 1
        )
    except Exception as e:
        # print(f"Error limpiando la cadena: {e}")
        return text  # En caso de error, devolver la cadena original


class PadreNotificacionesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not request.session.get('credenciales_padre'):
            return response

        try:
            if request.session['credenciales_padre'].get('rol') != 'Padre':
                return response

            padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
            nombre_limpio = clean_string(padre.nombre_completo)

            # CAMBIO: Usar notificaciones_no_leidas() directamente
            notificaciones_no_leidas = padre.notificaciones_no_leidas()
            
            # Convertir a diccionarios para la sesión (sin límite)
            notificaciones_limpias = []
            for notif in notificaciones_no_leidas:
                notif_dict = {
                    'id': notif.id,
                    'title': clean_string(notif.title),
                    'message': clean_string(notif.message),
                    'is_read': notif.is_read,
                    'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'event_type': notif.event_type,
                }
                notificaciones_limpias.append(notif_dict)

            contador_no_leidas = notificaciones_no_leidas.count()

            request.session['notificaciones_padre_todas'] = notificaciones_limpias
            request.session['notificaciones_padre_no_leidas'] = contador_no_leidas
            request.session['contador_padre_no_leidas'] = contador_no_leidas
            request.session.modified = True

        except Padre.DoesNotExist:
            print("Padre no encontrado en la base de datos.")
        except Exception as e:
            print(f"Error en el middleware de notificaciones para padre: {str(e)}")

        return response


class PadreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user_obj = None

        credenciales = request.session.get('credenciales_padre')

        if credenciales:
            try:
                padre = Padre.objects.get(id=credenciales['id'])
                request.user_obj = padre
            except Padre.DoesNotExist:
                pass

        return self.get_response(request)
    