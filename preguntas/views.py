from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import PreguntaRespuesta, HistorialAyuda
from .utils import get_user_role_and_base
import json


def buscar_respuesta(request):
    if request.method == 'POST':
        try:
            # Obtener usuario y rol
            user, role, base_template, redirect_response = get_user_role_and_base(request)
            if not user:
                return JsonResponse({'error': 'Debes iniciar sesión'}, status=401)

            data = json.loads(request.body)
            pregunta = data.get('pregunta', '').strip()

            if not pregunta:
                return JsonResponse({'error': 'La pregunta no puede estar vacía'}, status=400)

            # Buscar primero en preguntas específicas del rol
            try:
                respuesta_obj = PreguntaRespuesta.objects.get(
                    rol=role,
                    pregunta__iexact=pregunta
                )
                respuesta = respuesta_obj.respuesta
            except PreguntaRespuesta.DoesNotExist:
                # Buscar en preguntas generales
                try:
                    respuesta_obj = PreguntaRespuesta.objects.get(
                        rol='General',
                        pregunta__iexact=pregunta
                    )
                    respuesta = respuesta_obj.respuesta
                except PreguntaRespuesta.DoesNotExist:
                    # Buscar coincidencias parciales (primero en rol, luego en general)
                    respuestas_rol = PreguntaRespuesta.objects.filter(
                        rol=role,
                        pregunta__icontains=pregunta
                    )
                    if respuestas_rol.exists():
                        respuesta = respuestas_rol.first().respuesta
                    else:
                        respuestas_general = PreguntaRespuesta.objects.filter(
                            rol='General',
                            pregunta__icontains=pregunta
                        )
                        if respuestas_general.exists():
                            respuesta = respuestas_general.first().respuesta
                        else:
                            respuesta = (
                                f"No encontré información específica para tu rol ({role}). "
                                "¿Podrías reformular tu pregunta o contactar al administrador?"
                            )

            # Registrar en el historial
            HistorialAyuda.objects.create(
                usuario=user,
                rol_usuario=role,
                pregunta=pregunta,
                respuesta=respuesta
            )

            return JsonResponse({
                'respuesta': respuesta,
                'rol_usuario': role
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método no permitido'}, status=405)


def obtener_preguntas_frecuentes(request):
    # Obtener usuario y rol
    user, role, base_template, redirect_response = get_user_role_and_base(request)
    if not user:
        return JsonResponse({'error': 'Debes iniciar sesión'}, status=401)

    # Obtener preguntas específicas del rol + preguntas generales
    preguntas_rol = PreguntaRespuesta.objects.filter(rol=role).order_by('pregunta')[:5]
    preguntas_general = PreguntaRespuesta.objects.filter(rol='General').order_by('pregunta')[:5]

    data = {
        'preguntas_especificas': [{'pregunta': p.pregunta} for p in preguntas_rol],
        'preguntas_generales': [{'pregunta': p.pregunta} for p in preguntas_general],
        'rol_usuario': role
    }

    return JsonResponse(data)

