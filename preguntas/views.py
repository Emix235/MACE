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
            user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)
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
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)
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
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)

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


'''
def faq_por_rol(request, rol):
    print(f"[DEBUG] === INICIO faq_por_rol ===")
    print(f"[DEBUG] Rol recibido en URL: {rol}")
    print(f"[DEBUG] Tipo de rol: {type(rol)}")
    
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)
    print(f"[DEBUG] user: {user}")
    print(f"[DEBUG] role obtenido: {role}")
    print(f"[DEBUG] base_template: {base_template}")
    print(f"[DEBUG] redirect_response: {redirect_response}")
    
    if redirect_response:
        print(f"[DEBUG] Hay redirect_response, redirigiendo a: {redirect_response.url if hasattr(redirect_response, 'url') else redirect_response}")
        return redirect_response

    roles_validos = dict(PreguntaRespuesta.ROL_CHOICES)
    print(f"[DEBUG] roles_validos: {roles_validos}")
    print(f"[DEBUG] ¿El rol '{rol}' está en roles_validos?: {rol in roles_validos}")
    
    if rol not in roles_validos:
        from django.contrib import messages
        print(f"[DEBUG] Rol NO válido: {rol}")
        messages.error(request, 'Rol no válido')
        return redirect('preguntas:faq_lista')

    print(f"[DEBUG] Rol válido, continuando...")
    
    # Ahora sí funcionan estos métodos
    preguntas_rol = PreguntaRespuesta.get_preguntas_por_rol(rol)
    preguntas_generales = PreguntaRespuesta.get_preguntas_generales()
    
    print(f"[DEBUG] preguntas_rol (type: {type(preguntas_rol)}):")
    if preguntas_rol:
        print(f"[DEBUG]   - Cantidad: {len(preguntas_rol) if hasattr(preguntas_rol, '__len__') else 'N/A'}")
        for i, p in enumerate(preguntas_rol):
            print(f"[DEBUG]     [{i}] pregunta: {getattr(p, 'pregunta', 'N/A')[:50]}...")
            print(f"[DEBUG]         respuesta: {getattr(p, 'respuesta', 'N/A')[:50]}...")
    else:
        print(f"[DEBUG]   - preguntas_rol está vacío o es None")
    
    print(f"[DEBUG] preguntas_generales (type: {type(preguntas_generales)}):")
    if preguntas_generales:
        print(f"[DEBUG]   - Cantidad: {len(preguntas_generales) if hasattr(preguntas_generales, '__len__') else 'N/A'}")
        for i, p in enumerate(preguntas_generales):
            print(f"[DEBUG]     [{i}] pregunta: {getattr(p, 'pregunta', 'N/A')[:50]}...")
    else:
        print(f"[DEBUG]   - preguntas_generales está vacío o es None")

    rol_display = get_user_role_display(role)
    rol_seleccionado_display = get_user_role_display(rol)
    
    print(f"[DEBUG] rol_display: {rol_display}")
    print(f"[DEBUG] rol_seleccionado_display: {rol_seleccionado_display}")
    print(f"[DEBUG] rol_seleccionado: {rol}")
    print(f"[DEBUG] rol_actual: {role}")

    # Mapeo de rol (que viene de la URL) a tutorial_id específico
    rol_to_tutorial = {
        'servicio': 'agendar_cita',      # ID del tutorial en servicios_escolares
        'padre': 'ver_citas',            # ID del tutorial en padre
        'profesor': 'gestionar_citas',   # ID del tutorial en profesor
    }
    
    context = {
        'preguntas_rol': preguntas_rol,
        'preguntas_generales': preguntas_generales,
        'rol_seleccionado': rol,
        'rol_seleccionado_display': rol_seleccionado_display,
        'rol_actual': role,
        'rol_display': rol_display,
        'base_template': base_template,
        'titulo': f'FAQ - {rol_seleccionado_display}',
        'user': user,
    }
    
    print(f"[DEBUG] Context a enviar a template:")
    for key, value in context.items():
        if key in ['preguntas_rol', 'preguntas_generales']:
            print(f"[DEBUG]   {key}: {type(value)} - cantidad: {len(value) if hasattr(value, '__len__') else 'N/A'}")
        else:
            print(f"[DEBUG]   {key}: {value}")
    
    print(f"[DEBUG] Template a renderizar: preguntas/pregunta_rol.html")
    print(f"[DEBUG] === FIN faq_por_rol ===")
    
    return render(request, 'preguntas/pregunta_rol.html', context)
'''


def faq_por_rol(request, rol):
    print(f"[DEBUG] === INICIO faq_por_rol ===")
    print(f"[DEBUG] Rol recibido en URL: {rol}")
    print(f"[DEBUG] Tipo de rol: {type(rol)}")
    
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)
    print(f"[DEBUG] user: {user}")
    print(f"[DEBUG] role obtenido: {role}")
    print(f"[DEBUG] base_template: {base_template}")
    print(f"[DEBUG] redirect_response: {redirect_response}")
    
    if redirect_response:
        print(f"[DEBUG] Hay redirect_response, redirigiendo a: {redirect_response.url if hasattr(redirect_response, 'url') else redirect_response}")
        return redirect_response

    roles_validos = ['servicio', 'padre', 'profesor']
    print(f"[DEBUG] roles_validos: {roles_validos}")
    print(f"[DEBUG] ¿El rol '{rol}' está en roles_validos?: {rol in roles_validos}")
    
    if rol not in roles_validos:
        from django.contrib import messages
        print(f"[DEBUG] Rol NO válido: {rol}")
        messages.error(request, 'Rol no válido')
        return redirect('preguntas:faq_lista')

    print(f"[DEBUG] Rol válido, continuando...")
    
    # Mapeo de rol a ID de tutorial (para pasar al frontend)
    rol_to_tutorial = {
        'servicio': 'agendar_cita',      # ID del tutorial en servicios_escolares
        'padre': 'ver_citas',            # ID del tutorial en padre
        'profesor': 'gestionar_citas',   # ID del tutorial en profesor
    }
    
    # Mapeo de rol a nombre para mostrar
    rol_display_names = {
        'servicio': 'Servicios Escolares',
        'padre': 'Padre de Familia',
        'profesor': 'Profesor'
    }
    
    rol_seleccionado_display = rol_display_names.get(rol, rol)
    rol_actual_display = rol_display_names.get(role, role)
    
    # Obtenemos los tutoriales según el rol seleccionado
    # Esto ahora se pasará al contexto para que JS lo maneje
    tutoriales_por_rol = {
        'servicio': {
            'agendar_cita': {
                'nombre': 'Cómo Agendar una Cita',
                'descripcion': 'Aprende a agendar citas para estudiantes paso a paso'
            },
            'gestionar_calendario': {
                'nombre': 'Gestión de Calendario',
                'descripcion': 'Aprende a gestionar y visualizar el calendario de citas'
            },
            'generar_reportes': {
                'nombre': 'Generar Reportes',
                'descripcion': 'Aprende a generar reportes estadísticos del sistema'
            },
            'gestionar_usuarios': {
                'nombre': 'Gestión de Usuarios',
                'descripcion': 'Aprende a gestionar usuarios y permisos en el sistema'
            }
        },
        'padre': {
            'ver_citas': {
                'nombre': 'Ver Citas de mi Hijo',
                'descripcion': 'Consulta las citas programadas para tus hijos'
            },
            'solicitar_reunion': {
                'nombre': 'Solicitar Reunión',
                'descripcion': 'Aprende a solicitar una reunión con los profesores'
            }
        },
        'profesor': {
            'gestionar_citas': {
                'nombre': 'Gestionar Mis Citas',
                'descripcion': 'Administra las citas programadas con padres y estudiantes'
            },
            'registrar_notas': {
                'nombre': 'Registrar Notas',
                'descripcion': 'Registrar observaciones después de cada reunión'
            }
        }
    }
    
    # Obtener tutoriales del rol seleccionado
    tutoriales_del_rol = tutoriales_por_rol.get(rol, {})
    
    # Crear lista de preguntas frecuentes desde los tutoriales
    preguntas_rol = []
    for tutorial_id, tutorial_info in tutoriales_del_rol.items():
        preguntas_rol.append({
            'id': tutorial_id,
            'pregunta': f"¿Cómo {tutorial_info['nombre'].lower()}?",
            'respuesta': tutorial_info['descripcion'],
            'tutorial_id': tutorial_id,
            'fecha_creacion': None  # O puedes poner una fecha por defecto
        })
    
    # Preguntas generales (puedes mantenerlas desde BD o crear algunas)
    preguntas_generales = [
        {
            'id': 1,
            'pregunta': '¿Cómo cambio mi contraseña?',
            'respuesta': 'Puedes cambiar tu contraseña desde tu perfil de usuario, en la sección de configuración.'
        },
        {
            'id': 2,
            'pregunta': '¿Cómo recupero mi cuenta?',
            'respuesta': 'Usa la opción "Olvidé mi contraseña" en la página de inicio de sesión.'
        },
        {
            'id': 3,
            'pregunta': '¿Dónde puedo ver mis notificaciones?',
            'respuesta': 'Las notificaciones aparecen en el ícono de campana en la parte superior derecha.'
        }
    ]
    
    print(f"[DEBUG] preguntas_rol creadas: {len(preguntas_rol)}")
    for i, p in enumerate(preguntas_rol):
        print(f"[DEBUG]   [{i}] pregunta: {p['pregunta']}")
        print(f"[DEBUG]       tutorial_id: {p['tutorial_id']}")
    
    print(f"[DEBUG] preguntas_generales: {len(preguntas_generales)}")

    context = {
        'preguntas_rol': preguntas_rol,
        'preguntas_generales': preguntas_generales,
        'rol_seleccionado': rol,
        'rol_seleccionado_display': rol_seleccionado_display,
        'rol_actual': role,
        'rol_actual_display': rol_actual_display,
        'base_template': base_template,
        'titulo': f'FAQ - {rol_seleccionado_display}',
        'user': user,
        'tutorial_id_principal': rol_to_tutorial.get(rol, ''),
    }
    
    print(f"[DEBUG] Context a enviar a template:")
    for key, value in context.items():
        if key == 'preguntas_rol':
            print(f"[DEBUG]   {key}: lista con {len(value)} items")
        elif key == 'preguntas_generales':
            print(f"[DEBUG]   {key}: lista con {len(value)} items")
        else:
            print(f"[DEBUG]   {key}: {value}")
    
    print(f"[DEBUG] Template a renderizar: preguntas/pregunta_rol.html")
    print(f"[DEBUG] === FIN faq_por_rol ===")
    
    return render(request, 'preguntas/pregunta_rol.html', context)



# Vista para ver detalles de una pregunta
def pregunta_detalle(request, pk):
    # Obtener usuario y rol
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)

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
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)
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
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)
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
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)

    # 🔥 OVERRIDE DESDE URL
    role_param = request.GET.get("role")
    if role_param:
        role = role_param

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

'''
@xframe_options_exempt
def demo_completa_view(request):
    """Vista para la demo completa con iframe"""
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)

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
'''

'''
@xframe_options_exempt
def demo_completa_view(request):
    """Vista para la demo completa con iframe"""
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)

    if redirect_response:
        return redirect_response

    # Obtener tutorial específico desde la URL (parámetro 'tutorial')
    tutorial_seleccionado = request.GET.get('tutorial', role)
    
    context = {
        'base_template': base_template,
        'rol_actual': role,
        'rol_display': get_user_role_display(role),
        'titulo': 'Demo Completa - Agendar Cita',
        'user': user,
        'tutorial_seleccionado': tutorial_seleccionado,  # ← NUEVO
    }

    return render(request, 'preguntas/demo_completa.html', context)
'''


@xframe_options_exempt
def demo_completa_view(request):
    """Vista para la demo completa con iframe"""
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)

    if redirect_response:
        return redirect_response

    # Obtener tutorial específico desde la URL (parámetro 'tutorial')
    tutorial_seleccionado = request.GET.get('tutorial', '')
    
    context = {
        'base_template': base_template,
        'rol_actual': role,
        'titulo': 'Demo Interactiva',
        'user': user,
        'tutorial_seleccionado': tutorial_seleccionado,
    }

    return render(request, 'preguntas/demo_completa.html', context)

