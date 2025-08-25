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
        # print("Iniciando procesamiento de la solicitud en middleware de notificaciones para padres.")
        response = self.get_response(request)

        if not request.session.get('credenciales_padre'):
            # print("No se encontraron credenciales de padre en la sesión.")
            return response

        try:
            if request.session['credenciales_padre'].get('rol') != 'Padre':
                # print(f"El rol del usuario es {request.session['credenciales_padre'].get('rol')}, no es Padre.")
                return response

            padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
            nombre_limpio = clean_string(padre.nombre_completo)
            # print(f"Padre encontrado: {nombre_limpio}")

            notificaciones = padre.get_notificaciones()
            notificaciones_limpias = [clean_string(noti) for noti in notificaciones]
            # print(f"Notificaciones obtenidas para el padre: {notificaciones_limpias}")

            notificaciones_no_leidas = [n for n in notificaciones if not n.is_read]
            contador_no_leidas = len(notificaciones_no_leidas)

            request.session['notificaciones_padre_todas'] = notificaciones_limpias
            request.session['notificaciones_padre_no_leidas'] = contador_no_leidas
            request.session['contador_padre_no_leidas'] = contador_no_leidas

            request.session.modified = True
            # print(f"Sesión actualizada: {contador_no_leidas} notificaciones no leídas para padre.")

        except Padre.DoesNotExist:
            print("Padre no encontrado en la base de datos.")
        except Exception as e:
            print(f"Error en el middleware de notificaciones para padre: {str(e)}")

        # print("Finalizando el procesamiento de la solicitud en el middleware de notificaciones para padres.")
        return response
