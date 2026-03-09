from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import PreguntaRespuesta, HistorialAyuda
from .utils import get_user_role_and_base, get_user_role_display
from django.db.models import Q
import json
import traceback
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_exempt


@require_POST
def buscar_respuesta(request):
    if request.method == 'POST':
        try:
            print("\n" + "=" * 50)
            print("[FAQ] Iniciando búsqueda...")

            # Obtener usuario y rol
            user, role, base_template, redirect_response = get_user_role_and_base(request)
            print(f"[FAQ] Rol detectado: {role}")
            print(f"[FAQ] Tipo de usuario: {type(user)}")

            if not user:
                print("[FAQ] ERROR: Usuario no autenticado")
                return JsonResponse({'error': 'Debes iniciar sesión'}, status=401)

            # Leer pregunta
            data = json.loads(request.body)
            pregunta = data.get('pregunta', '').strip()
            print(f"[FAQ] Pregunta: '{pregunta}'")

            if not pregunta:
                return JsonResponse({'error': 'La pregunta no puede estar vacía'}, status=400)

            # CORRECCIÓN: 'general' en minúscula (como en tu modelo)
            rol_busqueda = role
            rol_general = 'general'  # ← MINÚSCULA, no 'General'

            # Buscar primero en preguntas específicas del rol
            try:
                respuesta_obj = PreguntaRespuesta.objects.get(
                    rol=rol_busqueda,
                    pregunta__iexact=pregunta,
                    activa=True
                )
                respuesta = respuesta_obj.respuesta
                print(f"[FAQ] ✓ Coincidencia exacta en rol '{rol_busqueda}'")

            except PreguntaRespuesta.DoesNotExist:
                # Buscar en preguntas generales
                try:
                    respuesta_obj = PreguntaRespuesta.objects.get(
                        rol=rol_general,  # ← 'general' minúscula
                        pregunta__iexact=pregunta,
                        activa=True
                    )
                    respuesta = respuesta_obj.respuesta
                    print(f"[FAQ] ✓ Coincidencia exacta en 'general'")

                except PreguntaRespuesta.DoesNotExist:
                    # Buscar coincidencias parciales
                    respuestas_rol = PreguntaRespuesta.objects.filter(
                        rol=rol_busqueda,
                        pregunta__icontains=pregunta,
                        activa=True
                    )

                    if respuestas_rol.exists():
                        respuesta = respuestas_rol.first().respuesta
                        print(f"[FAQ] ✓ Coincidencia parcial en rol ({respuestas_rol.count()} resultados)")

                    else:
                        respuestas_general = PreguntaRespuesta.objects.filter(
                            rol=rol_general,  # ← 'general' minúscula
                            pregunta__icontains=pregunta,
                            activa=True
                        )

                        if respuestas_general.exists():
                            respuesta = respuestas_general.first().respuesta
                            print(f"[FAQ] ✓ Coincidencia parcial en general ({respuestas_general.count()} resultados)")

                        else:
                            respuesta = "No encontré información específica para tu pregunta. ¿Podrías reformularla?"
                            print("[FAQ] ✗ No se encontraron coincidencias")

            # SOLUCIÓN AL PROBLEMA: Obtener el User de Django relacionado
            try:
                print(f"[FAQ] Intentando registrar en historial...")
                print(f"[FAQ] Usuario original: {user} (tipo: {type(user).__name__})")

                # OPCIÓN 1: Buscar el User de Django por email (si tus modelos tienen email)
                django_user = None

                if hasattr(user, 'correo_electronico'):
                    from django.contrib.auth.models import User
                    try:
                        django_user = User.objects.get(email=user.correo_electronico)
                        print(f"[FAQ] ✓ User de Django encontrado: {django_user.username}")
                    except User.DoesNotExist:
                        print(f"[FAQ] ⚠️ No se encontró User de Django para email: {user.correo_electronico}")
                        # Crear un usuario de Django temporal o usar uno genérico
                        try:
                            django_user = User.objects.get(username='sistema_faq')
                        except User.DoesNotExist:
                            # Crear usuario genérico para FAQ
                            django_user = User.objects.create_user(
                                username='sistema_faq',
                                email='faq@sistema.edu',
                                password='temp_password_123'
                            )
                            print(f"[FAQ] ✓ Creado usuario genérico para FAQ")

                # OPCIÓN 2: Si no hay email, usar un usuario del sistema
                if not django_user:
                    from django.contrib.auth.models import User
                    django_user, created = User.objects.get_or_create(
                        username='sistema_ayuda',
                        defaults={'email': 'ayuda@sistema.edu', 'password': 'temp_pass'}
                    )
                    print(f"[FAQ] Usando usuario del sistema: {django_user.username}")

                # Crear el registro en HistorialAyuda
                historial = HistorialAyuda.objects.create(
                    usuario=django_user,  # ← User de Django, no tu modelo personalizado
                    rol_usuario=role,
                    pregunta=pregunta,
                    respuesta=respuesta[:500]  # Limitar longitud
                )
                print(f"[FAQ] ✓ Historial registrado ID: {historial.id}")

            except Exception as e:
                print(f"[FAQ] ⚠️ Error en historial (continuando): {str(e)}")
                # No fallar la búsqueda por error en historial

            print(f"[FAQ] Respuesta: {respuesta[:100]}...")
            print("=" * 50 + "\n")

            return JsonResponse({
                'respuesta': respuesta,
                'rol_usuario': role,
                'rol_display': get_user_role_display(role) if 'get_user_role_display' in globals() else role
            })

        except json.JSONDecodeError as e:
            print(f"[FAQ] ERROR JSON: {e}")
            return JsonResponse({'error': 'Formato JSON inválido'}, status=400)

        except Exception as e:
            print(f"[FAQ] ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': 'Error interno del servidor'}, status=500)

    return JsonResponse({'error': 'Método no permitido'}, status=405)


'''
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
'''


# Vista para ver todas las preguntas FAQ
def faq_lista(request):
    # Obtener usuario y rol
    user, role, base_template, redirect_response = get_user_role_and_base(request)

    if redirect_response:
        return redirect_response

    # Si no hay usuario (no debería pasar si redirige correctamente)
    if not user:
        messages.error(request, 'Debes iniciar sesión para acceder a las FAQ')
        # Redirige a tu página de login - ajusta la URL
        return redirect('servicios_escolares:login')

    # Obtener todas las preguntas activas
    preguntas = PreguntaRespuesta.objects.filter(activa=True).order_by('rol', 'orden', 'pregunta')

    # Organizar preguntas por rol
    preguntas_por_rol = {}
    for pregunta in preguntas:
        if pregunta.rol not in preguntas_por_rol:
            preguntas_por_rol[pregunta.rol] = []
        preguntas_por_rol[pregunta.rol].append(pregunta)

    # Agrupar las opciones de rol para el filtro
    roles = dict(PreguntaRespuesta.ROL_CHOICES)

    # Convertir el rol del usuario a display name
    rol_display = get_user_role_display(role)

    context = {
        'preguntas_por_rol': preguntas_por_rol,
        'roles': roles,
        'rol_actual': role,
        'rol_display': rol_display,
        'base_template': base_template,
        'titulo': 'Preguntas Frecuentes (FAQ)',
        'user': user,
    }

    return render(request, 'preguntas/pregunta_lista.html', context)


def faq_por_rol(request, rol):
    user, role, base_template, redirect_response = get_user_role_and_base(request)
    if redirect_response:
        return redirect_response

    roles_validos = dict(PreguntaRespuesta.ROL_CHOICES)
    if rol not in roles_validos:
        from django.contrib import messages
        messages.error(request, 'Rol no válido')
        return redirect('preguntas:faq_lista')  # O a donde prefieras

    # Ahora sí funcionan estos métodos
    preguntas_rol = PreguntaRespuesta.get_preguntas_por_rol(rol)
    preguntas_generales = PreguntaRespuesta.get_preguntas_generales()

    rol_display = get_user_role_display(role)
    rol_seleccionado_display = get_user_role_display(rol)

    # CAMBIA 'preguntas/pregunta_rol.html' por 'faq/faq_rol.html'
    return render(request, 'preguntas/pregunta_rol.html', {
        'preguntas_rol': preguntas_rol,
        'preguntas_generales': preguntas_generales,
        'rol_seleccionado': rol,
        'rol_seleccionado_display': rol_seleccionado_display,
        'rol_actual': role,
        'rol_display': rol_display,
        'base_template': base_template,
        'titulo': f'FAQ - {rol_seleccionado_display}',
        'user': user,
    })


# Vista para ver detalles de una pregunta
def pregunta_detalle(request, pk):
    # Obtener usuario y rol
    user, role, base_template, redirect_response = get_user_role_and_base(request)

    if redirect_response:
        return redirect_response

    # Obtener la pregunta
    pregunta = get_object_or_404(PreguntaRespuesta, pk=pk, activa=True)

    # Verificar si el usuario puede ver esta pregunta
    # (Solo puede ver preguntas de su rol o generales)
    if pregunta.rol != 'general' and pregunta.rol != role:
        messages.warning(request, 'Esta pregunta no está disponible para tu rol')
        return redirect('preguntas:faq_por_rol', rol=role)

    # Obtener preguntas relacionadas (mismo rol)
    preguntas_relacionadas = PreguntaRespuesta.objects.filter(
        rol=pregunta.rol,
        activa=True
    ).exclude(pk=pk).order_by('orden', 'pregunta')[:5]

    # Convertir rol a display
    rol_display = get_user_role_display(role)

    context = {
        'pregunta': pregunta,
        'preguntas_relacionadas': preguntas_relacionadas,
        'rol_actual': role,
        'rol_display': rol_display,
        'base_template': base_template,
        'titulo': pregunta.pregunta,
        'user': user,
    }

    return render(request, 'preguntas/pregunta_detalle.html', context)


def buscar_preguntas(request):
    user, role, base_template, redirect_response = get_user_role_and_base(request)
    if redirect_response:
        return redirect_response

    query = request.GET.get('q', '').strip()
    resultados = []

    if query:
        # CAMBIA 'models.Q' por solo 'Q' y usa activa=True
        resultados = PreguntaRespuesta.objects.filter(
            activa=True
        ).filter(
            Q(rol=role) | Q(rol='general')
        ).filter(
            Q(pregunta__icontains=query) |
            Q(respuesta__icontains=query)
        ).order_by('rol', 'orden', 'pregunta')

        HistorialAyuda.objects.create(
            usuario=user,
            rol_usuario=role,
            pregunta=f"Búsqueda: {query}",
            respuesta=f"Se encontraron {resultados.count()} resultados"
        )

    rol_display = get_user_role_display(role)

    # CAMBIA 'preguntas/buscar.html' por 'faq/buscar.html'
    return render(request, 'preguntas/buscar.html', {
        'query': query,
        'resultados': resultados,
        'resultados_count': resultados.count() if query else 0,
        'rol_actual': role,
        'rol_display': rol_display,
        'base_template': base_template,
        'titulo': f'Buscar: {query}' if query else 'Buscar en FAQ',
        'user': user,
    })


def obtener_preguntas_frecuentes(request):
    # Obtener usuario y rol
    user, role, base_template, redirect_response = get_user_role_and_base(request)
    if not user:
        return JsonResponse({'error': 'Debes iniciar sesión'}, status=401)

    # Obtener preguntas específicas del rol + preguntas generales
    preguntas_rol = PreguntaRespuesta.objects.filter(rol=role, activa=True).order_by('orden', 'pregunta')[:5]
    preguntas_general = PreguntaRespuesta.objects.filter(rol='general', activa=True).order_by('orden', 'pregunta')[:5]

    data = {
        'preguntas_especificas': [{
            'pregunta': p.pregunta,
            'id': p.id,
            'rol': p.rol
        } for p in preguntas_rol],
        'preguntas_generales': [{
            'pregunta': p.pregunta,
            'id': p.id,
            'rol': p.rol
        } for p in preguntas_general],
        'rol_usuario': role,
        'rol_display': get_user_role_display(role)
    }

    return JsonResponse(data)


# views.py
def demo_chatbot(request):
    """Vista para demostración interactiva del FAQ"""
    user, role, base_template, redirect_response = get_user_role_and_base(request)

    if redirect_response:
        return redirect_response

    # Obtener estadísticas
    total_preguntas = PreguntaRespuesta.objects.filter(activa=True).count()
    preguntas_rol = PreguntaRespuesta.objects.filter(rol=role, activa=True).count()

    context = {
        'rol_actual': role,
        'rol_display': get_user_role_display(role),
        'base_template': base_template,
        'total_preguntas': total_preguntas,
        'preguntas_rol': preguntas_rol,
        'titulo': 'Demo Interactivo FAQ',
        'user': user,
    }

    return render(request, 'preguntas/chatbot_demo.html', context)


@xframe_options_exempt
def demo_completa_view(request):
    """Vista para la demo completa con iframe"""
    user, role, base_template, redirect_response = get_user_role_and_base(request)

    if redirect_response:
        return redirect_response

    context = {
        'base_template': base_template,
        'rol_actual': role,
        'rol_display': get_user_role_display(role),
        'titulo': 'Demo Completa - Agendar Cita',
        'user': user,
    }

    return render(request, 'preguntas/demo_completa.html', context)

