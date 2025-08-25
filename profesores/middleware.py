from profesores.models import Profesor  # Ajusta la importación si tu modelo está en otra app
import unicodedata


# Eliminar o reemplazar caracteres no codificables (como emojis)
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
        print(f"Error limpiando la cadena: {e}")
        return text  # En caso de error, devolver la cadena original


class ProfesorNotificacionesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # print("Iniciando el procesamiento de la solicitud en el middleware de notificaciones.")
        response = self.get_response(request)

        # Verificamos si el usuario está logueado como Profesor
        if not request.session.get('credenciales_profesor'):
            # print("No se encontraron credenciales de profesor en la sesión.")
            return response

        try:
            # Verificamos si el rol es de Profesor
            if request.session['credenciales_profesor'].get('rol') != 'Profesor':
                print(f"El rol del usuario es {request.session['credenciales_profesor'].get('rol')}, no es Profesor.")
                return response

            # Intentamos obtener al Profesor de la base de datos
            profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])

            # Usar clean_string para imprimir los nombres
            nombre_limpio = clean_string(profesor.nombre_completo)
            # print(f"Profesor encontrado: {nombre_limpio}")

            # Obtenemos las notificaciones del profesor
            notificaciones = profesor.get_notificaciones(limit=10)

            # Asegurémonos de que las notificaciones se puedan imprimir sin problemas
            notificaciones_limpias = [clean_string(noti) for noti in notificaciones]
            # print(f"Notificaciones obtenidas para el profesor: {notificaciones_limpias}")

            # Calcular notificaciones no leídas de la lista
            notificaciones_no_leidas = [n for n in notificaciones if not n['is_read']]
            contador_no_leidas = len(notificaciones_no_leidas)

            # Guardamos en sesión
            request.session['notificaciones_todas'] = notificaciones_limpias
            request.session['notificaciones_no_leidas'] = contador_no_leidas
            request.session['contador_no_leidas'] = contador_no_leidas

            request.session.modified = True
            # print(f"Sesión actualizada: {contador_no_leidas} notificaciones no leídas.")

        except Profesor.DoesNotExist:
            print("Profesor no encontrado en la base de datos.")
        except Exception as e:
            print(f"Error en el middleware de notificaciones para profesor: {str(e)}")

        # print("Finalizando el procesamiento de la solicitud en el middleware de notificaciones.")
        return response
