from datetime import timezone, datetime, time
from time import localtime

import pytz

from nota.models import Nota
from .forms import CitaPrioritariaForm
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Count
from django.utils.dateparse import parse_datetime
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import DetailView, FormView, CreateView

from MACE import settings
from citas.models import Cita, CitaPrioritaria, ReprogramacionCita
from formularios.models import RetroalimentacionCita, RetroalimentacionAplicada, RespuestaRetroalimentacion
from padres.models import Padre
from profesores.models import Profesor, Clase, HorarioClase, TiempoLibreProfesor
from ticket_soporte.models import TicketSoporte
from .forms import LoginForm, RegistroForm, CitaForm, ReprogramarCitaServicioEscolarForm
from servicios_escolares.forms import ServicioEscolar, LoginForm, ServicioEscolarForm
from django.http import HttpResponseForbidden, Http404, HttpResponseRedirect, HttpResponse
from .models import ServicioEscolar, ThemeConfig
from calendar import monthrange
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from datetime import date, timedelta
from estudiantes.models import CicloEscolar, PeriodoEscolar, Grado, Grupo, NivelEducativo
from estudiantes.forms import CicloEscolarForm, GrupoForm, NivelEducativoForm
from django.shortcuts import render
from django.http import JsonResponse
import json
from profesores.models import HorarioClase
from django.template.loader import render_to_string
from estudiantes.models import Estudiante
from django.db.models import Count, Q
from .forms import CitaForm, ProfesorOptionalForm
from notificaciones.models import Notification
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import models
from django.utils import timezone
from citas.models import Cita
from django.utils import timezone
from datetime import datetime  # Importa correctamente la clase datetime
from django.db import transaction
from datetime import datetime, timedelta
from django.utils import timezone
import logging
from django.utils.timezone import is_naive, localtime
from django.views.generic import DetailView
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt


logger = logging.getLogger(__name__)


def registro_view(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Registro exitoso! Por favor inicia sesión.')
            return redirect('servicios_escolares:login')
    else:
        form = RegistroForm()

    return render(request, 'servicios_escolares/registro.html', {'form': form})


def login_view(request):
    # Verificar si el usuario ya está logueado
    if request.session.get('credenciales'):
        return redirect('servicios_escolares:dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            usuario = form.cleaned_data['usuario']

            # Guardar la fecha actual para el hash
            fecha_actual = timezone.now().date()
            hash_credencial = f"{usuario.correo_electronico}-{fecha_actual}".encode('utf-8').hex()

            # Guardar datos en la sesión
            request.session['credenciales'] = {
                'id': usuario.id,
                'hash_credencial': hash_credencial,
                'rol': usuario.rol_usuario
            }
            request.session['ultima_actividad'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')

            request.session.save()  # Forzar guardado de sesión

            usuario.ultima_fecha_sesion = fecha_actual
            usuario.save(update_fields=['ultima_fecha_sesion'])

            print(f"DEBUG: Hash generado: {hash_credencial[:15]}...")
            return redirect('servicios_escolares:dashboard')
    else:
        form = LoginForm()

    return render(request, 'servicios_escolares/login.html', {'form': form})


def logout_view(request):
    # Limpiar toda la información sensible
    if 'credenciales' in request.session:
        del request.session['credenciales']
    if 'ultima_actividad' in request.session:
        del request.session['ultima_actividad']

    request.session.flush()
    # Usar messages.add_message() con un nivel específico y una etiqueta única
    messages.add_message(request, messages.INFO, 'Has cerrado sesión correctamente.', extra_tags='logout_message')
    return redirect('servicios_escolares:login')


def dashboard_view(request):
    now = timezone.localtime(timezone.now())
    current_date = now.date()

    # Calendario Semanal
    start_week = now - timedelta(days=now.weekday())
    week_days = [start_week + timedelta(days=i) for i in range(7)]

    # Calendario Mensual
    year = now.year
    month = now.month
    _, num_days = monthrange(year, month)
    first_day = datetime(year, month, 1)

    # Ajustar para que comience en lunes
    first_weekday = (first_day.weekday() + 1) % 7  # Lunes=0, Domingo=6
    calendar_days = []

    # Días del mes anterior
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    _, prev_num_days = monthrange(prev_year, prev_month)

    for i in range(first_weekday):
        day = prev_num_days - first_weekday + i + 1
        calendar_days.append({
            'date': datetime(prev_year, prev_month, day),
            'current_month': False
        })

    # Días del mes actual
    for day in range(1, num_days + 1):
        calendar_days.append({
            'date': datetime(year, month, day),
            'current_month': True,
            'is_today': day == now.day and month == now.month and year == now.year
        })

    # Días del siguiente mes
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    days_to_add = 42 - len(calendar_days)  # 6 semanas

    for day in range(1, days_to_add + 1):
        calendar_days.append({
            'date': datetime(next_year, next_month, day),
            'current_month': False
        })

    # Dividir en semanas
    month_weeks = [calendar_days[i:i + 7] for i in range(0, len(calendar_days), 7)]

    # --- VERIFICACIÓN DE SESIÓN MEJORADA ---
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        # Obtener usuario
        usuario = ServicioEscolar.objects.get(id=request.session['credenciales']['id'])

        # Debug de sesión
        print(f"[DEBUG] Sesión activa para: {usuario.nombre_completo}")
        print(f"[DEBUG] Credenciales sesión: {request.session['credenciales']}")

        # Verificación simplificada (solo ID y rol)
        if (request.session['credenciales']['id'] != usuario.id or
                request.session['credenciales']['rol'] != usuario.rol_usuario):
            print("[ERROR] Credenciales no coinciden")
            messages.error(request, 'Error de autenticación')
            return redirect('servicios_escolares:logout')

        # Actualizar actividad
        request.session['ultima_actividad'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        request.session.modified = True  # Forzar guardado

        # --- Obtener citas para completar ---
        citas_para_completar = Cita.objects.filter(
            (Q(servicio_escolar=usuario) | Q(asistentes_servicio=usuario)),
            estado__in=['confirmada', 'pendiente'],
            fecha_hora_fin__lt=timezone.now()
        ).exclude(estado='completada').distinct().order_by('-fecha_hora_inicio')

        # --- Citas con retroalimentación pendiente ---
        citas_con_retro_pendiente = Cita.objects.filter(
            (Q(servicio_escolar=usuario) | Q(asistentes_servicio=usuario)),
            estado='completada',
            retroalimentacion__completada=False
        ).distinct().select_related('solicitante', 'retroalimentacion')

        # --- CÓDIGO ORIGINAL DE CITAS Y NOTIFICACIONES ---
        notificaciones = usuario.notificaciones.filter(rol_destinatario='servicio').order_by('-created_at')

        servicio_ct = ContentType.objects.get_for_model(ServicioEscolar)
        padre_ct = ContentType.objects.get_for_model(Padre)
        profesor_ct = ContentType.objects.get_for_model(Profesor)

        estado = request.GET.get('estado')

        citas_creadas = Cita.objects.filter(
            creador_tipo=servicio_ct,
            creador_id=usuario.id
        )
        citas_pendientes_creadas = citas_creadas.filter(
            estado__in=['pendiente', 'reprogramada']
        ).order_by('-fecha_hora_inicio')

        citas_como_agendador = Cita.objects.filter(
            servicio_escolar=usuario
        )

        citas_como_asistente = Cita.objects.filter(
            asistentes_servicio=usuario
        ).exclude(
            Q(creador_tipo=servicio_ct, creador_id=usuario.id) | Q(servicio_escolar=usuario)
        )

        citas_solicitadas_por_padres = Cita.objects.filter(
            solicitante__isnull=False,
            asistentes_servicio=usuario
        ).exclude(
            creador_tipo=servicio_ct
        )

        citas_de_profesores = Cita.objects.filter(
            creador_tipo=profesor_ct,
            asistentes_servicio=usuario
        )

        if estado and estado in dict(Cita.ESTADOS):
            citas_creadas = citas_creadas.filter(estado=estado)
            citas_como_agendador = citas_como_agendador.filter(estado=estado)
            citas_como_asistente = citas_como_asistente.filter(estado=estado)
            citas_solicitadas_por_padres = citas_solicitadas_por_padres.filter(estado=estado)
            citas_de_profesores = citas_de_profesores.filter(estado=estado)

        # --- RENDER FINAL ---
        return render(request, 'servicios_escolares/index.html', {
            'notificaciones': notificaciones,
            'usuario': {
                'nombre': usuario.nombre_completo,
                'rol': usuario.rol_usuario,
                'correo': usuario.correo_electronico[:3] + '***' + usuario.correo_electronico.split('@')[1],
                'ultimo_acceso': usuario.ultima_fecha_sesion
            },
            'hora_actual': now.strftime('%H:%M:%S'),
            'week_days': week_days,
            'month_weeks': month_weeks,
            'current_month': now.strftime('%B %Y'),
            'current_week': f"Semana del {start_week.strftime('%d/%m')} al {(start_week + timedelta(days=6)).strftime('%d/%m')}",
            'current_date': current_date,
            'citas_creadas': citas_creadas.order_by('-fecha_hora_inicio'),
            'citas_como_agendador': citas_como_agendador.order_by('-fecha_hora_inicio'),
            'citas_como_asistente': citas_como_asistente.order_by('-fecha_hora_inicio'),
            'citas_solicitadas_por_padres': citas_solicitadas_por_padres.order_by('-fecha_hora_inicio'),
            'citas_de_profesores': citas_de_profesores.order_by('-fecha_hora_inicio'),
            'citas_pendientes_creadas': citas_pendientes_creadas.order_by('-fecha_hora_inicio'),
            'filtro_estado': estado,
            'estados_cita': Cita.ESTADOS,
            'citas_para_completar': citas_para_completar,
            'citas_con_retro_pendiente': citas_con_retro_pendiente,
        })

    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('servicios_escolares:logout')


@require_POST
def confirmar_cita_servicio(request, cita_id):
    # Verificar que el usuario esté autenticado
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        # Obtener usuario desde la sesión
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'  # Solo cuentas activas
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')
    except KeyError:
        messages.error(request, 'Error en los datos de sesión')
        return redirect('servicios_escolares:logout')

    # Buscar la cita
    try:
        cita = Cita.objects.get(
            id=cita_id,
            estado='pendiente',
            servicio_escolar=usuario  # Usamos el usuario de la sesión
        )
    except Cita.DoesNotExist:
        messages.error(request, "Cita no encontrada o no autorizada")
        return redirect('servicios_escolares:mis_citas')

    # Confirmar cita
    cita.estado = 'confirmada'
    cita.save()

    # Generar notificación
    cita.generar_notificacion_confirmacion(usuario, 'servicio')

    messages.success(request, f"Cita confirmada correctamente")
    return redirect('servicios_escolares:mis_citas')


@require_http_methods(["GET", "POST"])
def cancelar_cita_servicio(request, cita_id):
    # Verificar autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except (ServicioEscolar.DoesNotExist, KeyError):
        messages.error(request, 'Usuario no válido o sesión caducada')
        return redirect('servicios_escolares:logout')

    cita = get_object_or_404(Cita, id=cita_id, estado__in=['pendiente', 'confirmada'])

    if request.method == 'POST':
        accion = request.POST.get('accion')  # Determinar si es cancelación o reprogramación

        if accion == 'cancelar' and 'motivo_cancelacion' in request.POST:
            # Procesar cancelación
            motivo = request.POST.get('motivo_cancelacion')
            cita.estado = 'cancelada'
            cita.motivo_cancelacion = motivo
            cita.save()

            # Enviar notificación
            for receptor in [cita.solicitante, cita.profesor]:
                if receptor:
                    Notification.objects.create(
                        recipient=receptor,
                        event_type='servicio_cita_cancelada',
                        title=f"Cita cancelada: {cita.titulo}",
                        message=f"El servicio escolar canceló la cita del {cita.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}. Motivo: {motivo}",
                        target=cita
                    )

            messages.success(request, "Cita cancelada correctamente")
            return redirect('servicios_escolares:mis_citas')

        elif accion == 'reprogramar' and 'nueva_fecha' in request.POST:
            # Procesar reprogramación
            nueva_fecha_str = request.POST.get('nueva_fecha')
            motivo = request.POST.get('motivo')

            try:
                nueva_fecha = parse_datetime(nueva_fecha_str)
                if not nueva_fecha or nueva_fecha <= timezone.now():
                    raise ValueError
            except (ValueError, TypeError):
                messages.error(request, 'Fecha inválida o debe ser futura')
                return render(request, 'servicios_escolares/citas/cancelar_cita.html', {'cita': cita})

            # Guardar la cita original como cancelada
            cita_original = cita
            cita_original.estado = 'cancelada'
            cita_original.motivo_cancelacion = f"Reprogramación: {motivo}"
            cita_original.save()

            # Crear nueva cita con los nuevos datos
            nueva_cita = Cita.objects.create(
                titulo=cita_original.titulo,
                descripcion=cita_original.descripcion,
                solicitante=cita_original.solicitante,
                profesor=cita_original.profesor,
                servicio_escolar=cita_original.servicio_escolar,
                fecha_hora_inicio=nueva_fecha,
                motivo=motivo,
                estado='pendiente'
            )

            # Enviar notificación
            for receptor in [nueva_cita.solicitante, nueva_cita.profesor]:
                if receptor:
                    Notification.objects.create(
                        recipient=receptor,
                        event_type='servicio_cita_reprogramada',
                        title=f"Cita reprogramada: {nueva_cita.titulo}",
                        message=f"El servicio escolar reprogramó la cita para {nueva_cita.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}. Motivo: {motivo}",
                        target=nueva_cita
                    )

            messages.success(request, "Cita reprogramada correctamente")
            return redirect('servicios_escolares:mis_citas')

        messages.error(request, 'Acción no válida o datos incompletos')
        return render(request, 'servicios_escolares/citas/cancelar_cita.html', {'cita': cita})

    # Si es GET, mostrar formulario de confirmación
    return render(request, 'servicios_escolares/citas/cancelar_cita.html', {'cita': cita})


def detalle_cita_modal(request, cita_id):
    # Verificar que el usuario esté autenticado
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        # Obtener usuario desde la sesión
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')
    except KeyError:
        messages.error(request, 'Error en los datos de sesión')
        return redirect('servicios_escolares:logout')

    # Obtener la cita
    cita = get_object_or_404(Cita, id=cita_id)

    # Contexto para renderizar la vista
    context = {
        'cita': cita,
        'es_servicio_escolar': True,
    }

    # Usar el template específico para modal (SIN base.html)
    html = render_to_string('servicios_escolares/citas/detalle_cita_modal.html', context, request)
    return HttpResponse(html)


def configuracion_view(request):
    """
    Vista de configuración para Servicio Escolar
    - Verifica sesión activa
    - Obtiene datos del usuario
    - Redirige a template sin manejar formularios
    """
    # Verificar autenticación (usando tu sistema de sesiones)
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        # Obtener usuario desde la sesión
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'  # Solo cuentas activas
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')
    except KeyError:
        messages.error(request, 'Error en los datos de sesión')
        return redirect('servicios_escolares:logout')

    # Preparar contexto para el template
    context = {
        'usuario': usuario,
        'ultimo_acceso': request.session.get('ultimo_acceso', 'N/A'),
        'rol': request.session.get('credenciales', {}).get('rol', 'Servicio Escolar')
    }

    return render(request, 'servicios_escolares/configuracion.html', context)


def perfil_view(request):
    """
    Vista de configuración para Servicio Escolar
    - Verifica sesión activa
    - Obtiene datos del usuario
    - Redirige a template sin manejar formularios
    """
    # Verificar autenticación (usando tu sistema de sesiones)
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        # Obtener usuario desde la sesión
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'  # Solo cuentas activas
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')
    except KeyError:
        messages.error(request, 'Error en los datos de sesión')
        return redirect('servicios_escolares:logout')

    # Preparar contexto para el template
    context = {
        'usuario': usuario,
        'ultimo_acceso': request.session.get('ultimo_acceso', 'N/A'),
        'rol': request.session.get('credenciales', {}).get('rol', 'Servicio Escolar')
    }

    return render(request, 'servicios_escolares/perfil.html', context)


"""
    Vista para editar la información de Servicio Escolar
    - Verifica autenticación
    - Maneja el formulario de edición
    - Actualiza la información en la base de datos
    """


def editar_view(request):
    # Verificar autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')
    except KeyError:
        messages.error(request, 'Error en los datos de sesión')
        return redirect('servicios_escolares:logout')

    if request.method == 'POST':
        form = ServicioEscolarForm(request.POST, request.FILES, instance=usuario)
        if form.is_valid():
            form.save()

            # Actualizar datos en la sesión si el nombre cambió
            if 'nombre_completo' in form.changed_data:
                request.session['credenciales']['nombre'] = form.cleaned_data['nombre_completo']
                request.session.modified = True

            messages.success(request, 'Información actualizada correctamente')
            return redirect('servicios_escolares:perfil')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario')
    else:
        form = ServicioEscolarForm(instance=usuario)

    context = {
        'form': form,
        'usuario': usuario,
        'ultimo_acceso': request.session.get('ultimo_acceso', 'Nunca'),
        'rol': request.session.get('credenciales', {}).get('rol', 'Servicio Escolar')
    }

    return render(request, 'servicios_escolares/editar_perfil.html', context)


def panel_principal(request):
    # Verificar autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')
    except KeyError:
        messages.error(request, 'Error en los datos de sesión')
        return redirect('servicios_escolares:logout')

    # Verificar si existe algún nivel educativo
    nivel_existente = NivelEducativo.objects.first()

    # Manejar formulario de nivel educativo
    if request.method == 'POST':
        if 'guardar_nivel' in request.POST:
            form = NivelEducativoForm(request.POST, instance=nivel_existente)
            if form.is_valid():
                nivel = form.save(commit=False)
                nivel.nombre = dict(NivelEducativo.NIVELES).get(nivel.codigo, '')
                nivel.save()
                nivel.crear_grados_automaticamente()
                messages.success(request, 'Nivel educativo guardado correctamente')
                return redirect('servicios_escolares:panel-principal')
            else:
                messages.error(request, 'Por favor corrige los errores en el formulario')
        elif 'cambiar_ciclo_actual' in request.POST and nivel_existente:
            # Manejar cambio de ciclo actual (tu lógica original)
            pass

    # Preparar contexto base
    context = {
        'usuario': usuario,
        'ultimo_acceso': request.session.get('ultimo_acceso', 'Nunca'),
        'rol': request.session.get('credenciales', {}).get('rol', 'Servicio Escolar')
    }

    # Si no existe nivel, mostrar solo el formulario
    if not nivel_existente:
        context.update({
            'mostrar_form_nivel': True,
            'form_nivel': NivelEducativoForm(initial={'codigo': 'SEC'})
        })
        return render(request, 'servicios_escolares/administracion/panel_principal.html', context)

    # Lógica para mostrar panel normal con ciclos
    context.update({
        'nivel_actual': nivel_existente,
        'ciclos': CicloEscolar.objects.filter(nivel=nivel_existente).order_by('-fecha_inicio'),
        'ciclo_actual': CicloEscolar.objects.filter(actual=True, nivel=nivel_existente).first(),
        'form_nivel': NivelEducativoForm(instance=nivel_existente),
        'mostrar_form_nivel': False
    })

    return render(request, 'servicios_escolares/administracion/panel_principal.html', context)


def gestion_ciclos(request):
    # Manejo del nivel educativo seleccionado
    nivel_actual = request.GET.get('nivel')
    if not nivel_actual and NivelEducativo.objects.exists():
        nivel_actual = NivelEducativo.objects.first().codigo

    # Obtener datos filtrados
    ciclos = CicloEscolar.objects.filter(nivel__codigo=nivel_actual).order_by('-fecha_inicio')
    ciclo_actual = CicloEscolar.obtener_actual()

    # Formulario para nuevo ciclo (inicialmente oculto)
    ciclo_form = CicloEscolarForm(request.POST or None, initial={'nivel': nivel_actual})

    # Procesar creación de nuevo ciclo
    if request.method == 'POST' and 'crear_ciclo' in request.POST:
        if ciclo_form.is_valid():
            ciclo = ciclo_form.save(commit=False)

            # Validación adicional para ciclo actual
            if ciclo.actual:
                CicloEscolar.objects.filter(actual=True).update(actual=False)

            ciclo.save()
            messages.success(request, f'Ciclo {ciclo.nombre} creado exitosamente!')
            return redirect(reverse('servicios_escolares:paso2_periodos', kwargs={'ciclo_id': ciclo.id}))

    context = {
        'nivel_actual': NivelEducativo.objects.get(codigo=nivel_actual) if nivel_actual else None,
        'niveles': NivelEducativo.objects.all(),
        'ciclos': ciclos,
        'ciclo_actual': ciclo_actual,
        'ciclo_form': ciclo_form,
        'mostrar_formulario': request.GET.get('mostrar_form', False),
    }
    return render(request, 'servicios_escolares/administracion/gestion_ciclos.html', context)


def panel_profesores(request):
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')
    except KeyError:
        messages.error(request, 'Error en los datos de sesión')
        return redirect('servicios_escolares:logout')

    # Cambiar Padre por Profesor aquí
    profesores = Profesor.objects.filter(rol_usuario='Profesor')  # O el valor que uses para profesores

    context = {
        'profesores': profesores,
        'usuario': usuario,
        'titulo_pagina': 'Panel de Profesores'
    }
    return render(request, 'servicios_escolares/administracion/panel_profesores.html', context)


def compartir_registro_view(request):
    """
    Vista para compartir el link de registro de profesores
    - Verifica sesión activa
    - Valida que el usuario sea Servicio Escolar activo
    - Genera el link de registro seguro
    """
    # Verificar autenticación usando el sistema de sesiones
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        # Obtener usuario desde la sesión
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo',  # Solo cuentas activas
            rol_usuario='Servicio Escolar'  # Solo para este rol
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no autorizado o cuenta inactiva')
        return redirect('servicios_escolares:logout')
    except KeyError:
        messages.error(request, 'Error en los datos de sesión')
        return redirect('servicios_escolares:logout')

    # Generar URL de registro absoluta
    registro_url = request.build_absolute_uri(reverse('profesores:registro_profesor'))

    # Preparar contexto para el template
    context = {
        'usuario': usuario,
        'registro_url': registro_url,
        'rol': request.session.get('credenciales', {}).get('rol', 'Servicio Escolar'),
        'ultimo_acceso': request.session.get('ultimo_acceso', 'N/A')
    }
    return render(request, 'servicios_escolares/administracion/compartir_registro.html', context)


def enviar_invitacion_view(request):
    """
    Vista para enviar invitaciones por correo
    - Verifica sesión activa
    - Valida datos del formulario
    - Envía el correo de invitación
    """
    # Verificar autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    if request.method != 'POST':
        messages.error(request, 'Método no permitido')
        return redirect('servicios_escolares:compartir_registro')

    try:
        # Validar usuario autorizado
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo',
            rol_usuario='Servicio Escolar'
        )
    except (ServicioEscolar.DoesNotExist, KeyError):
        messages.error(request, 'Usuario no autorizado')
        return redirect('servicios_escolares:logout')

    # Obtener email del formulario
    email_destino = request.POST.get('email')
    if not email_destino:
        messages.error(request, 'Debes proporcionar un correo electrónico')
        return redirect('servicios_escolares:compartir_registro')

    # Generar URL de registro
    registro_url = request.build_absolute_uri(reverse('profesores:registro_profesor'))

    # Enviar correo
    try:
        send_mail(
            subject=f'Invitación para registrarse como profesor - {usuario.nombre_completo}',
            message=f'''Has sido invitado a registrarte como profesor en nuestro sistema.

Por favor visita el siguiente enlace para completar tu registro:
{registro_url}

Este enlace es válido por 7 días.

Atentamente,
{usuario.nombre_completo}
Servicio Escolar''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_destino],
            fail_silently=False
        )
        messages.success(request, f'Invitación enviada a {email_destino}')
    except Exception as e:
        messages.error(request, f'Error al enviar invitación: {str(e)}')

    return redirect('servicios_escolares:compartir_registro')


def panel_horarios_servicio_escolar(request):
    """
    Vista para mostrar horarios por grado y grupo con mensajes de depuración
    """
    # Verificar autenticación
    if not request.session.get('credenciales'):
        # messages.warning(request, '[DEBUG] No hay credenciales en la sesión')
        return redirect('servicios_escolares:login')

    try:
        # Validar usuario autorizado
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo',
            rol_usuario='Servicio Escolar'
        )
        # messages.info(request, f'[DEBUG] Usuario autenticado: {usuario.nombre_completo}')
    except ServicioEscolar.DoesNotExist:
        messages.error(request, '[DEBUG] Usuario no encontrado o no autorizado')
        return redirect('servicios_escolares:logout')
    except KeyError:
        messages.error(request, '[DEBUG] Error en la estructura de credenciales')
        return redirect('servicios_escolares:logout')

    # Obtener ciclo escolar actual
    ciclo_actual = CicloEscolar.obtener_actual()
    if not ciclo_actual:
        messages.error(request, '[DEBUG] No hay ciclo escolar activo')
        return redirect('servicios_escolares:gestion_ciclos')

    # messages.info(request, f'[DEBUG] Ciclo escolar actual: {ciclo_actual.nombre}')

    # Configurar horas del día (7:00 AM a 3:00 PM)
    horas = [time(h, 0) for h in range(7, 16)]
    # messages.info(request, f'[DEBUG] Rango de horas configurado: 7:00 - 15:00')

    # Obtener todos los grados del ciclo actual
    grados = Grado.objects.filter(
        ciclo=ciclo_actual
    ).select_related('nivel').order_by('nivel__orden', 'numero')

    # messages.info(request, f'[DEBUG] Grados encontrados: {grados.count()}')

    estructura_grados = []

    for grado in grados:
        # messages.info(request,
                     # f'[DEBUG] Procesando grado: {grado.nombre if grado.nombre else f"{grado.numero}° {grado.nivel.nombre}"}')

        # Obtener grupos de este grado
        grupos = Grupo.objects.filter(
            grado=grado,
            ciclo=ciclo_actual
        ).order_by('letra')

        # messages.info(request, f'[DEBUG] Grupos encontrados para este grado: {grupos.count()}')

        grupos_data = []

        for grupo in grupos:
            # messages.info(request, f'[DEBUG] Procesando grupo: {grupo.letra}')

            # Obtener clases con sus horarios
            clases = Clase.objects.filter(
                grupo=grupo,
                ciclo_escolar=ciclo_actual
            ).select_related('profesor').prefetch_related(
                Prefetch(
                    'horarios',
                    queryset=HorarioClase.objects.order_by('dia_semana', 'hora_inicio')
                )
            )

            # messages.info(request, f'[DEBUG] Clases encontradas para este grupo: {clases.count()}')

            # Preparar matriz de horarios
            matriz_horarios = []

            for hora in horas:
                fila = {
                    'hora': hora,
                    'dias': []
                }

                # Para cada día de la semana
                for dia_id, dia_nombre in HorarioClase.DIAS_SEMANA:
                    clases_dia = []

                    # Buscar clases que coincidan con esta hora y día
                    for clase in clases:
                        for horario in clase.horarios.all():
                            if (horario.dia_semana == dia_id and
                                    horario.hora_inicio <= hora < horario.hora_fin):
                                clases_dia.append({
                                    'materia': clase.nombre,
                                    'profesor': clase.profesor.nombre_completo,
                                    'aula': horario.aula,
                                    'hora_inicio': horario.hora_inicio,
                                    'hora_fin': horario.hora_fin
                                })

                    fila['dias'].append({
                        'dia_id': dia_id,
                        'dia_nombre': dia_nombre,
                        'clases': clases_dia
                    })

                matriz_horarios.append(fila)

            grupos_data.append({
                'id': grupo.id,
                'letra': grupo.letra,
                'turno': grupo.get_turno_display(),
                'matriz_horarios': matriz_horarios
            })

        estructura_grados.append({
            'id': grado.id,
            'nombre': grado.nombre if grado.nombre else f"{grado.numero}° {grado.nivel.nombre}",
            'grupos': grupos_data
        })

    # messages.info(request, '[DEBUG] Procesamiento completado. Renderizando plantilla...')

    return render(request, 'servicios_escolares/administracion/panel_horarios_grupos.html', {
        'grados': estructura_grados,
        'dias_semana': HorarioClase.DIAS_SEMANA,
        'ciclo_actual': ciclo_actual
    })


# views.py (app servicios_escolares)
'''
def asignar_padres_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)
    estudiantes = Estudiante.objects.filter(grupo_actual=grupo)

    # Generar enlaces completos
    for estudiante in estudiantes:
        estudiante.enlace_registro = request.build_absolute_uri(
            f'/padres/registro/{estudiante.registro_token}/'
        )

    return render(request, 'servicios_escolares/administracion/asignar_padres_grupo.html', {
        'grupo': grupo,
        'estudiantes': estudiantes
    })
    '''


def asignar_padres_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)
    estudiantes = Estudiante.objects.filter(grupo_actual=grupo)

    # Preparar datos para la plantilla
    for estudiante in estudiantes:
        estudiante.enlace_registro = f"{request.scheme}://{request.get_host()}/padres/registro/{estudiante.registro_token}/"

    return render(request, 'servicios_escolares/administracion/asignar_padres_grupo.html', {
        'grupo': grupo,
        'estudiantes': estudiantes
    })


def asignar_padre_estudiante(request, estudiante_id):
    # Verificación de autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')

    # Obtener el estudiante
    estudiante = get_object_or_404(Estudiante, pk=estudiante_id)

    # Obtener todos los padres disponibles
    padres = Padre.objects.all().order_by('nombre_completo')

    # Procesar el formulario si se envió
    if request.method == 'POST':
        padre_id = request.POST.get('padre_id')
        if padre_id:
            try:
                padre = Padre.objects.get(pk=padre_id)
                estudiante.padre = padre
                estudiante.save()
                messages.success(request, f'Padre asignado correctamente a {estudiante.nombre_completo()}')

                # Redirección corregida manteniendo los parámetros GET
                redirect_url = reverse(
                    'servicios_escolares:panel_grupos_padres') + f'?grado_id={estudiante.grupo_actual.grado.id}&grupo_id={estudiante.grupo_actual.id}'
                return HttpResponseRedirect(redirect_url)

            except Padre.DoesNotExist:
                messages.error(request, 'El padre seleccionado no existe')

    context = {
        'estudiante': estudiante,
        'padres': padres,
        'usuario': usuario,
    }
    return render(request, 'servicios_escolares/administracion/asignar_padre.html', context)


@xframe_options_exempt
def invitacion_registro(request, token):
    estudiante = get_object_or_404(Estudiante, registro_token=token)

    return render(request, 'servicios_escolares/administracion/invitacion.html', {
        'estudiante': estudiante,
        'token': token
    })


def procesar_invitacion(request, token):
    if request.method == 'POST':
        # Aquí iría la lógica de procesamiento del registro
        return redirect('registro_padres', token=token)
    return redirect('servicios_escolares:dashboard')


def panel_citas_servicio_escolar(request):
    # Verificación de autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        servicio_escolar = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')

    # Obtener el ciclo actual
    ciclo_actual = CicloEscolar.obtener_actual()
    if not ciclo_actual:
        messages.error(request, 'No hay un ciclo escolar activo')
        return redirect('servicios_escolares:dashboard')

    # Obtener parámetros
    grado_id = request.GET.get('grado_id')
    grupo_id = request.GET.get('grupo_id')

    # Obtener todos los grados del ciclo actual
    grados = Grado.objects.filter(
        ciclo=ciclo_actual
    ).annotate(
        num_grupos=Count('grupos'),
        num_citas_pendientes=Count('grupos__estudiantes__padre__citas_solicitadas',
                                   filter=Q(grupos__estudiantes__padre__citas_solicitadas__estado='pendiente'))
    ).order_by('nivel__orden', 'numero')

    grado_seleccionado = None
    grupos = None
    grupo_seleccionado = None
    estudiantes = None

    if grado_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id, ciclo=ciclo_actual)

        # Obtener grupos con conteo de estudiantes y citas
        grupos = Grupo.objects.filter(
            grado=grado_seleccionado,
            ciclo=ciclo_actual
        ).annotate(
            num_estudiantes=Count('estudiantes'),
            num_citas_pendientes=Count('estudiantes__padre__citas_solicitadas',
                                       filter=Q(estudiantes__padre__citas_solicitadas__estado='pendiente'))
        ).order_by('letra')

        if grupo_id:
            grupo_seleccionado = get_object_or_404(Grupo, pk=grupo_id, grado=grado_seleccionado)

            # Obtener estudiantes con información de citas
            estudiantes = Estudiante.objects.filter(
                grupo_actual=grupo_seleccionado
            ).select_related('padre').annotate(
                num_citas=Count('padre__citas_solicitadas'),
                citas_pendientes=Count('padre__citas_solicitadas',
                                       filter=Q(padre__citas_solicitadas__estado='pendiente'))
            ).order_by('apellido_paterno', 'apellido_materno', 'nombre')

    context = {
        'ciclo_actual': ciclo_actual,
        'grados': grados,
        'grado_seleccionado': grado_seleccionado,
        'grupos': grupos,
        'grupo_seleccionado': grupo_seleccionado,
        'estudiantes': estudiantes,
        'usuario': servicio_escolar,
    }
    return render(request, 'servicios_escolares/citas/panel_citas.html', context)


def historial_citas_estudiante(request, estudiante_id):
    """
    Vista que muestra el historial de citas asociadas a un estudiante específico.
    Recibe el ID del estudiante (no del padre) como parámetro.
    """
    # print(f"\n[DEBUG] Iniciando historial_citas_estudiante para estudiante_id: {estudiante_id}")

    # 1. Verificación de autenticación
    if not request.session.get('credenciales'):
        # print("[DEBUG] No hay sesión activa - Redirigiendo a login")
        messages.error(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    # 2. Autenticación del servicio escolar
    try:
        servicio_escolar = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
        # print(f"[DEBUG] Usuario autenticado: {servicio_escolar}")
    except (ServicioEscolar.DoesNotExist, KeyError):
        # print("[DEBUG] Error de autenticación")
        messages.error(request, 'Error de autenticación')
        return redirect('servicios_escolares:logout')

    # 3. Obtención del estudiante
    try:
        estudiante = Estudiante.objects.select_related('padre').get(id=estudiante_id)
        # print(f"\n[DEBUG] Información del estudiante:")
        # print(f"ID: {estudiante.id}")
        # print(f"Nombre: {estudiante.nombre_completo()}")
        # print(f"Padre ID: {estudiante.padre_id if estudiante.padre else 'No asignado'}")
    except Estudiante.DoesNotExist:
        # print(f"[DEBUG] Estudiante con ID {estudiante_id} no encontrado")
        raise Http404("Estudiante no encontrado")

    # 4. Obtención de citas asociadas al estudiante (a través del padre si existe)
    if not estudiante.padre:
        # print("[DEBUG] El estudiante no tiene padre asignado")
        messages.warning(request, 'Este estudiante no tiene padre/tutor asignado')
        citas = Cita.objects.none()  # QuerySet vacío
    else:
        # print(f"[DEBUG] Buscando citas para el padre ID: {estudiante.padre.id}")
        citas = Cita.objects.filter(
            solicitante=estudiante.padre
        ).select_related(
            'profesor',
            'servicio_escolar'
        ).order_by('-fecha_hora_inicio')

    print(f"[DEBUG] Total de citas encontradas: {citas.count()}")

    # 5. Preparación del contexto
    context = {
        'estudiante': estudiante,
        'citas': citas,
        'total_citas': citas.count(),
        'citas_pendientes': citas.filter(estado='pendiente').count(),
        'citas_completadas': citas.filter(estado='completada').count(),
        'usuario': servicio_escolar,
        'sin_padre': not estudiante.padre,
    }

    # print("\n[DEBUG] Contexto enviado al template:")
    # print(f"Estudiante: {estudiante.nombre_completo()}")
    # print(f"Total citas: {context['total_citas']}")
    # print(f"Padre asignado: {'Sí' if estudiante.padre else 'No'}")

    return render(request, 'servicios_escolares/citas/historial_citas.html', context)


def historial_citas_servicio_escolar(request):
    # 1. Verificación de autenticación
    if not request.session.get('credenciales'):
        print("[DEBUG] No hay sesión activa - Redirigiendo a login")
        messages.error(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    # 2. Obtener el servicio escolar actual
    try:
        servicio_escolar = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
        print(f"[DEBUG] Servicio escolar autenticado: {servicio_escolar}")
    except ServicioEscolar.DoesNotExist:
        print("[DEBUG] Error: ServicioEscolar no existe o cuenta no activa")
        messages.error(request, 'Error de autenticación')
        return redirect('servicios_escolares:logout')
    except KeyError:
        print("[DEBUG] Error: KeyError al acceder a credenciales")
        messages.error(request, 'Error de autenticación')
        return redirect('servicios_escolares:logout')

    # 3. Obtener citas normales y prioritarias donde este servicio escolar está involucrado
    citas_normales = Cita.objects.filter(
        Q(servicio_escolar=servicio_escolar)
    ).select_related(
        'solicitante',
        'profesor',
        'servicio_escolar'
    )

    citas_prioritarias = CitaPrioritaria.objects.filter(
        Q(servicio_escolar=servicio_escolar)
    ).select_related(
        'solicitante',
        'profesor',
        'servicio_escolar'
    )

    # Combinar ambas querysets
    citas = list(citas_normales) + list(citas_prioritarias)
    citas = sorted(citas, key=lambda x: x.fecha_hora_inicio, reverse=True)

    print(f"[DEBUG] Total de citas encontradas: {len(citas)}")

    # 4. Aplicar filtros si existen
    estado_filtro = request.GET.get('estado')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    if estado_filtro:
        citas = [c for c in citas if c.estado == estado_filtro]
        print(f"[DEBUG] Filtro aplicado - Estado: {estado_filtro}")

    if fecha_inicio:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            citas = [c for c in citas if c.fecha_hora_inicio.date() >= fecha_inicio]
            print(f"[DEBUG] Filtro aplicado - Desde: {fecha_inicio}")
        except ValueError:
            print("[DEBUG] Formato de fecha inicio inválido")
            messages.warning(request, 'Formato de fecha inicial inválido')

    if fecha_fin:
        try:
            fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date() + timedelta(days=1)
            citas = [c for c in citas if c.fecha_hora_inicio.date() < fecha_fin]
            print(f"[DEBUG] Filtro aplicado - Hasta: {fecha_fin}")
        except ValueError:
            print("[DEBUG] Formato de fecha fin inválido")
            messages.warning(request, 'Formato de fecha final inválido')

    # 5. Calcular estadísticas
    total_citas = len(citas)
    citas_hoy = len([c for c in citas if c.fecha_hora_inicio.date() == datetime.now().date()])
    citas_pendientes = len([c for c in citas if c.estado == 'pendiente'])
    citas_completadas = len([c for c in citas if c.estado == 'completada'])

    # Contar citas prioritarias por nivel de prioridad
    citas_criticas = len([c for c in citas if hasattr(c, 'nivel_prioridad') and c.nivel_prioridad == 'critica'])
    citas_altas = len([c for c in citas if hasattr(c, 'nivel_prioridad') and c.nivel_prioridad == 'alta'])
    citas_medias = len([c for c in citas if hasattr(c, 'nivel_prioridad') and c.nivel_prioridad == 'media'])

    # 6. Preparar contexto
    context = {
        'servicio_escolar': servicio_escolar,
        'citas': citas,
        'total_citas': total_citas,
        'citas_hoy': citas_hoy,
        'citas_pendientes': citas_pendientes,
        'citas_completadas': citas_completadas,
        'citas_criticas': citas_criticas,
        'citas_altas': citas_altas,
        'citas_medias': citas_medias,
        'estados_cita': dict(Cita.ESTADOS),
    }

    print("\n[DEBUG] Contexto preparado:")
    print(f"- Usuario: {servicio_escolar.nombre_completo}")
    print(f"- Total citas: {total_citas}")
    print(f"- Citas hoy: {citas_hoy}")
    print(f"- Citas prioritarias: Criticas={citas_criticas}, Altas={citas_altas}, Medias={citas_medias}")

    return render(request, 'servicios_escolares/citas/historial_servicio_escolar.html', context)


def agendar_cita_estudiante(request, estudiante_id):
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        servicio_escolar = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')

    estudiante = get_object_or_404(Estudiante, id=estudiante_id)

    if not estudiante.padre:
        messages.error(request, 'El estudiante no tiene padre/tutor asignado')
        return redirect('servicios_escolares:panel_citas')

    profesores_disponibles = []
    if estudiante.grupo_actual:
        clases = Clase.objects.filter(grupo=estudiante.grupo_actual).select_related('profesor').distinct()
        profesores_disponibles = [clase.profesor for clase in clases if clase.profesor]

    if request.method == 'POST':
        form = CitaForm(request.POST)
        profesor_form = ProfesorOptionalForm(profesores_disponibles, request.POST)

        print("POST recibido:", request.POST)

        if form.is_valid() and profesor_form.is_valid():
            print("Ambos formularios son válidos")
            try:
                cita = form.save(commit=False)
                cita.solicitante = estudiante.padre
                cita.servicio_escolar = servicio_escolar
                cita.titulo = f"Reunión con padre de {estudiante.nombre_completo()}"

                cita.creador_tipo = ContentType.objects.get_for_model(servicio_escolar)
                cita.creador_id = servicio_escolar.id

                profesor_id = profesor_form.cleaned_data.get('profesor')
                if profesor_id:
                    profesor = Profesor.objects.get(id=profesor_id)
                    cita.profesor = profesor
                    cita.titulo += f" y {profesor.nombre_completo}"

                # Asegurar que ambos campos necesarios están presentes antes del cálculo
                if cita.fecha_hora_inicio and cita.duracion:
                    cita.fecha_hora_fin = cita.fecha_hora_inicio + timedelta(minutes=cita.duracion)
                    print("Fecha y hora fin calculada:", cita.fecha_hora_fin)
                else:
                    raise ValidationError("Faltan datos para calcular la hora de finalización.")

                cita.full_clean()
                cita.save()

                cita.estudiantes.add(estudiante)
                cita.asistentes_padres.add(estudiante.padre)
                cita.asistentes_servicio.add(servicio_escolar)
                if cita.profesor:
                    cita.asistentes_profesores.add(cita.profesor)

                Notification.crear_notificacion_cita(
                    event_type='padre_cita_creada',
                    sender=servicio_escolar,
                    recipient=estudiante.padre,
                    message=f"📅 Cita agendada para el {cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}. Motivo: {cita.motivo}",
                    target=cita,
                )

                if cita.profesor:
                    Notification.crear_notificacion_cita(
                        event_type='profesor_cita_creada',
                        sender=servicio_escolar,
                        recipient=cita.profesor,
                        message=f"Tienes una cita con {estudiante.padre.nombre_completo} el {cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}.",
                        target=cita,
                    )

                messages.success(request, 'Cita agendada correctamente')
                return redirect('servicios_escolares:panel_citas')

            except ValidationError as e:
                print("Errores de validación del modelo:", e)
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
                messages.error(request, 'Por favor corrige los errores en el formulario')

            except Exception as e:
                print("Error inesperado al agendar cita:", str(e))
                messages.error(request, f'Ocurrió un error al agendar la cita: {str(e)}')

        else:
            print("Formulario no válido. Errores:", form.errors, profesor_form.errors)

    else:
        initial = {
            'fecha_hora_inicio': timezone.now() + timedelta(hours=1),
            'duracion': 30,
            'ubicacion': 'Escuela',
            'estado': 'pendiente',
            'tipo': 'academica'
        }
        form = CitaForm(initial=initial)
        profesor_form = ProfesorOptionalForm(profesores_disponibles)

    context = {
        'form': form,
        'profesor_form': profesor_form,
        'estudiante': estudiante,
        'padre': estudiante.padre,
        'servicio_escolar': servicio_escolar,
        'titulo': f"Agendar cita con padre de {estudiante.nombre_completo()}",
        'tiene_profesores': bool(profesores_disponibles),
    }

    return render(request, 'servicios_escolares/citas/agendar_cita.html', context)


class ReprogramarCitaServicioEscolarView(FormView):
    template_name = 'servicios_escolares/citas/reprogramar_cita.html'
    form_class = ReprogramarCitaServicioEscolarForm

    def dispatch(self, request, *args, **kwargs):
        # Verificar sesión del servicio escolar
        if not request.session.get('credenciales', {}).get('id'):
            messages.error(request, 'Debe iniciar sesión como servicio escolar')
            return redirect('servicios_escolares:login')

        # Obtener usuario y cita
        self.servicio_escolar = get_object_or_404(
            ServicioEscolar,
            id=request.session['credenciales']['id']
        )
        self.cita = get_object_or_404(Cita, id=kwargs['cita_id'])

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'cita': self.cita,
            'servicio_escolar': self.servicio_escolar
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'cita': self.cita,
            'servicio_escolar': self.servicio_escolar
        })
        return context

    def form_valid(self, form):
        try:
            # Registrar la reprogramación
            ReprogramacionCita.objects.create(
                cita_original=self.cita,
                fecha_hora_original=self.cita.fecha_hora_inicio,
                fecha_hora_nueva=form.cleaned_data['fecha_hora_inicio'],
                motivo=form.cleaned_data['motivo_reprogramacion'],
                realizado_por_tipo=ContentType.objects.get_for_model(self.servicio_escolar),
                realizado_por_id=self.servicio_escolar.id
            )

            # Actualizar la cita
            self.cita.fecha_hora_inicio = form.cleaned_data['fecha_hora_inicio']
            self.cita.duracion = form.cleaned_data['duracion']
            self.cita.fecha_hora_fin = self.cita.fecha_hora_inicio + timedelta(minutes=self.cita.duracion)
            self.cita.estado = 'reprogramada'
            self.cita.save()

            messages.success(self.request, '¡Cita reprogramada correctamente!')
            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f'Error al reprogramar la cita: {str(e)}')
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse('servicios_escolares:dashboard')

    def _enviar_notificaciones(self):
        logger.debug("Iniciando envío de notificaciones")

        try:
            # Notificación al servicio escolar
            notif_servicio = Notification.objects.create(
                sender_ct=ContentType.objects.get_for_model(self.servicio_escolar),
                sender_id=self.servicio_escolar.id,
                recipient_ct=ContentType.objects.get_for_model(self.servicio_escolar),
                recipient_id=self.servicio_escolar.id,
                event_type='servicio_escolar_cita_reprogramada',
                title=f'Cita reprogramada: {self.cita.titulo}',
                message=f"Has reprogramado la cita para el {self.cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}",
                target_ct=ContentType.objects.get_for_model(self.cita),
                target_id=self.cita.id
            )
            logger.debug(f"Notificación al servicio escolar creada ID: {notif_servicio.id}")

            # Notificación al padre
            notif_padre = Notification.objects.create(
                sender_ct=ContentType.objects.get_for_model(self.servicio_escolar),
                sender_id=self.servicio_escolar.id,
                recipient_ct=ContentType.objects.get_for_model(Padre),
                recipient_id=self.cita.solicitante.id,
                event_type='cita_reprogramada_por_servicio',
                title=f'Cita reprogramada por Servicio Escolar',
                message=f"La cita '{self.cita.titulo}' ha sido reprogramada para el {self.cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}. Motivo: {self.request.POST.get('motivo_reprogramacion', 'No especificado')}",
                target_ct=ContentType.objects.get_for_model(self.cita),
                target_id=self.cita.id
            )
            logger.debug(f"Notificación al padre creada ID: {notif_padre.id}")

            # Notificación al profesor si está asignado
            if self.cita.profesor:
                notif_profesor = Notification.objects.create(
                    sender_ct=ContentType.objects.get_for_model(self.servicio_escolar),
                    sender_id=self.servicio_escolar.id,
                    recipient_ct=ContentType.objects.get_for_model(Profesor),
                    recipient_id=self.cita.profesor.id,
                    event_type='cita_reprogramada_por_servicio',
                    title=f'Cita reprogramada por Servicio Escolar',
                    message=f"La cita '{self.cita.titulo}' con {self.cita.solicitante.nombre_completo} ha sido reprogramada para el {self.cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}",
                    target_ct=ContentType.objects.get_for_model(self.cita),
                    target_id=self.cita.id
                )
                logger.debug(f"Notificación al profesor creada ID: {notif_profesor.id}")

        except Exception as e:
            logger.error(f"Error al enviar notificaciones: {str(e)}", exc_info=True)
            raise


def detalle_profesor(request, profesor_id):
    # Obtener el profesor con sus relaciones
    profesor = get_object_or_404(
        Profesor.objects.prefetch_related(
            'clases__horarios',
            'clases__grupo',
            'tiempos_libres'
        ),
        pk=profesor_id
    )

    # Definir estructura de días y horas
    DIAS = {
        1: {'nombre': 'Lunes', 'eventos': {}},
        2: {'nombre': 'Martes', 'eventos': {}},
        3: {'nombre': 'Miércoles', 'eventos': {}},
        4: {'nombre': 'Jueves', 'eventos': {}},
        5: {'nombre': 'Viernes', 'eventos': {}},
        6: {'nombre': 'Sábado', 'eventos': {}}
    }

    HORAS = [
        '07:00', '08:00', '09:00', '10:00', '11:00', '12:00',
        '13:00', '14:00', '15:00', '16:00', '17:00', '18:00',
        '19:00', '20:00'
    ]

    # Inicializar estructura para cada hora en cada día
    for dia in DIAS.values():
        for hora in HORAS:
            dia['eventos'][hora] = []

    # Procesar clases del profesor
    for clase in profesor.clases.all():
        for horario in clase.horarios.all():
            dia_num = horario.dia_semana
            hora_inicio = horario.hora_inicio.strftime('%H:%M')
            hora_fin = horario.hora_fin.strftime('%H:%M')

            # Determinar qué horas cubre este horario
            for hora in HORAS:
                if hora_inicio <= hora < hora_fin:
                    DIAS[dia_num]['eventos'][hora].append({
                        'tipo': 'clase',
                        'nombre': clase.nombre,
                        'grupo': str(clase.grupo) if clase.grupo else '',
                        'aula': horario.aula,
                        'hora_inicio': hora_inicio,
                        'hora_fin': hora_fin
                    })

    # Procesar tiempos libres del profesor
    for tiempo in profesor.tiempos_libres.all():
        dia_num = tiempo.dia_semana
        hora_inicio = tiempo.hora_inicio.strftime('%H:%M')
        hora_fin = tiempo.hora_fin.strftime('%H:%M')

        for hora in HORAS:
            if hora_inicio <= hora < hora_fin:
                DIAS[dia_num]['eventos'][hora].append({
                    'tipo': 'tiempo_libre',
                    'motivo': tiempo.motivo or "Tiempo libre",
                    'hora_inicio': hora_inicio,
                    'hora_fin': hora_fin
                })

    # Preparar datos para el template
    datos_horario = []
    for hora in HORAS:
        fila = {'hora': hora, 'dias': []}
        for dia_num in sorted(DIAS.keys()):
            fila['dias'].append(DIAS[dia_num]['eventos'][hora])
        datos_horario.append(fila)

    context = {
        'profesor': profesor,
        'nombres_dias': [dia['nombre'] for dia in DIAS.values()],
        'horario': datos_horario
    }

    return render(request, 'servicios_escolares/administracion/detalle_profesor.html', context)


class CrearCitaPrioritariaServiciosEscolaresView(CreateView):
    model = CitaPrioritaria
    form_class = CitaPrioritariaForm
    template_name = 'servicios_escolares/citas/crear_cita_prioritaria.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('credenciales'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('servicios_escolares:login')

        try:
            servicio_id = request.session['credenciales']['id']
            self.servicio = ServicioEscolar.objects.get(id=servicio_id, estado_cuenta='Activo')
        except (ServicioEscolar.DoesNotExist, KeyError):
            messages.error(request, 'Error con la cuenta de Servicios Escolares')
            return redirect('servicios_escolares:logout')

        self.estudiante = get_object_or_404(Estudiante, id=self.kwargs['estudiante_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['estudiante'] = self.estudiante
        return kwargs

    def form_valid(self, form):
        cita = form.save(commit=False)
        cita.creado_por_servicios = self.servicio
        cita.estudiante = self.estudiante
        cita.solicitante = self.estudiante.padre

        tz_mexico = pytz.timezone('America/Mexico_City')
        ahora = timezone.localtime(timezone.now(), tz_mexico)

        fecha_hora = form.cleaned_data.get('fecha_hora_inicio')
        if not fecha_hora:
            form.add_error('fecha_hora_inicio', 'Debe especificar una fecha y hora')
            return self.form_invalid(form)

        try:
            if fecha_hora.tzinfo is None:
                fecha_hora = tz_mexico.localize(fecha_hora)
            else:
                fecha_hora = fecha_hora.astimezone(tz_mexico)
        except Exception:
            form.add_error('fecha_hora_inicio', 'Error al procesar la fecha/hora')
            return self.form_invalid(form)

        if fecha_hora.date() < ahora.date():
            form.add_error('fecha_hora_inicio', 'No se pueden agendar citas en días pasados')
            return self.form_invalid(form)

        if fecha_hora.date() == ahora.date():
            hora_minima = ahora + timedelta(hours=1)
            if fecha_hora < hora_minima:
                form.add_error('fecha_hora_inicio',
                               f'Para hoy, la hora debe ser al menos {hora_minima.strftime("%H:%M")}')
                return self.form_invalid(form)

        hora_inicio = fecha_hora.time()
        if hora_inicio < time(8, 0):
            form.add_error('fecha_hora_inicio', 'El horario de atención comienza a las 8:00')
            return self.form_invalid(form)
        elif hora_inicio > time(17, 30):
            form.add_error('fecha_hora_inicio', 'Último horario disponible: 17:30')
            return self.form_invalid(form)

        if fecha_hora.weekday() >= 5:
            form.add_error('fecha_hora_inicio', 'No se pueden agendar citas los fines de semana')
            return self.form_invalid(form)

        # Calcular fecha_hora_fin
        cita.fecha_hora_inicio = fecha_hora
        if cita.duracion:
            cita.fecha_hora_fin = fecha_hora + timedelta(minutes=cita.duracion)

        try:
            cita.save()
            messages.success(self.request, 'Cita prioritaria creada correctamente')

            if self.estudiante.padre:
                Notification.crear_notificacion_cita(
                    event_type='padre_cita_prioritaria',
                    sender=self.servicio,
                    recipient=self.estudiante.padre,
                    message=(
                        f"Se ha generado una cita prioritaria para {self.estudiante.nombre_completo()} "
                        f"el {cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')} - Motivo: {cita.motivo_prioridad}"
                    ),
                    target=cita,
                )

            return redirect('servicios_escolares:panel_citas')

        except Exception as e:
            form.add_error(None, f'Error al guardar: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Corrige los errores del formulario antes de continuar')
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tz_mexico = pytz.timezone('America/Mexico_City')
        ahora = timezone.localtime(timezone.now(), tz_mexico)

        hora_minima_hoy = ahora + timedelta(hours=1)
        if hora_minima_hoy.time() < time(8, 0):
            hora_minima_hoy = hora_minima_hoy.replace(hour=8, minute=0)

        hora_minima_futuro = ahora.replace(hour=8, minute=0, second=0, microsecond=0)
        hora_maxima_diaria = ahora.replace(hour=17, minute=30, second=0, microsecond=0)

        context.update({
            'estudiante': self.estudiante,
            'servicio': self.servicio,
            'titulo': f'Cita prioritaria para {self.estudiante.nombre_completo()}',
            'now': ahora,
            'hora_minima_hoy': hora_minima_hoy,
            'hora_minima_futuro': hora_minima_futuro,
            'hora_maxima_diaria': hora_maxima_diaria,
            'hora_minima_legible': hora_minima_hoy.strftime('%H:%M'),
            'hora_maxima_legible': hora_maxima_diaria.strftime('%H:%M'),
            'es_profesor': False,  # útil si el template pregunta por esto
        })

        return context


'''
def generar_imagen_interactiva(estudiante, request):
    # Crear imagen (ejemplo: 600x400 píxeles)
    img = Image.new('RGB', (600, 400), color=(73, 109, 137))
    draw = ImageDraw.Draw(img)

    # Añadir texto
    font = ImageFont.load_default()
    draw.text((50, 50), f"Invitación para {estudiante.nombre_completo()}", fill=(255, 255, 255), font=font)
    draw.text((50, 100), "Haga clic en el botón para registrarse:", fill=(255, 255, 255), font=font)

    # Dibujar un "botón" gráfico (coordenadas: x1, y1, x2, y2)
    draw.rectangle([200, 200, 400, 250], fill=(0, 150, 0))  # Rectángulo verde como botón
    draw.text((250, 210), "REGISTRARSE", fill=(255, 255, 255), font=font)

    # Guardar imagen en bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_base64}"


def generar_invitacion_grafica(estudiante, grupo):
    # 1. Crear imagen base (600x400)
    img = Image.new('RGB', (600, 400), color=(58, 123, 213))  # Fondo azul
    draw = ImageDraw.Draw(img)

    # 2. Añadir texto (usar fuente estándar o cargar una custom)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()

    # Texto de invitación
    textos = [
        "Invitación Plataforma Educativa",
        f"Padre de: {estudiante.nombre_completo()}",
        "Haz clic en este botón para registrarte:",
        f"Grado: {grupo.grado.numero}°{grupo.letra}",
        "Enlace personal e intransferible"
    ]

    # Posiciones del texto
    y_pos = 30
    for texto in textos:
        draw.text((50, y_pos), texto, fill="white", font=font)
        y_pos += 40

    # 3. Botón interactivo (área clickeable)
    draw.rectangle([50, 200, 300, 250], fill="#FFD700")  # Rectángulo dorado
    draw.text((70, 210), "🖱️ REGISTRARSE AQUÍ", fill="black", font=font)

    # 4. Convertir a base64 para HTML
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_base64}"

'''


@method_decorator(xframe_options_exempt, name='dispatch')
class DetalleTicketView(DetailView):
    model = TicketSoporte
    template_name = 'soporte/detalle_ticket.html'  # Un solo template
    context_object_name = 'ticket'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Determinar el tipo de usuario y asignar el template base correspondiente
        if 'credenciales_padre' in self.request.session:
            context['base_template'] = 'padres/base.html'
        elif 'credenciales_profesor' in self.request.session:
            context['base_template'] = 'profesores/base.html'
        elif 'credenciales' in self.request.session:
            context['base_template'] = 'servicios_escolares/base.html'
        else:
            context['base_template'] = 'base_generico.html'  # Template por defecto

        return context


@require_POST
@transaction.atomic
def marcar_cita_como_completada(request, cita_id):
    """
    Vista para que un usuario de Servicios Escolares marque una cita como completada
    y se asigne automáticamente la retroalimentación al padre.
    """
    # Validar sesión
    credenciales = request.session.get('credenciales')
    if not credenciales:
        messages.error(request, "Debes iniciar sesión.")
        return redirect('servicios_escolares:login')

    try:
        # Obtener al usuario autenticado y la cita correspondiente
        usuario = ServicioEscolar.objects.get(id=credenciales['id'])
        cita = get_object_or_404(Cita, id=cita_id)

        # Ejecutar la lógica de completar la cita con retroalimentación
        success, mensaje, retro_aplicada = usuario.marcar_cita_como_completada_con_retroalimentacion(cita)

        if not success:
            messages.error(request, mensaje)
        else:
            messages.success(request, "Cita marcada como completada y retroalimentación asignada al padre.")

        return redirect('servicios_escolares:dashboard')

    except ServicioEscolar.DoesNotExist:
        messages.error(request, "Usuario no válido. Inicia sesión nuevamente.")
        return redirect('servicios_escolares:login')

    except Exception as e:
        messages.error(request, f"Ocurrió un error inesperado: {str(e)}")
        transaction.set_rollback(True)
        return redirect('servicios_escolares:dashboard')


def get_user_from_session(request):
    if not hasattr(request, 'session'):
        return None

    session_mapping = {
        'credenciales': ('servicios_escolares.ServicioEscolar', 'servicios_escolares:logout'),
        'credenciales_profesor': ('profesores.Profesor', 'profesores:login_profesor'),
        'credenciales_padre': ('padres.Padre', 'padres:login_padre')
    }

    for session_key, (model_path, logout_url) in session_mapping.items():
        if request.session.get(session_key):
            try:
                from django.apps import apps
                model = apps.get_model(model_path)
                user = model.objects.get(
                    id=request.session[session_key]['id'],
                    estado_cuenta='Activo'
                )
                return user
            except Exception:
                messages.error(request, 'Error de autenticación')
                return redirect(logout_url)
    return None


def requiere_servicio_escolar(view_func):
    def wrapper(request, *args, **kwargs):
        user = get_user_from_session(request)
        if not user or user.__class__.__name__ != 'ServicioEscolar':
            messages.warning(request, 'Acceso restringido a Servicio Escolar')
            return redirect('servicios_escolares:login')
        request.user_obj = user
        return view_func(request, *args, **kwargs)

    return wrapper


def requiere_profesor(view_func):
    def wrapper(request, *args, **kwargs):
        user = get_user_from_session(request)
        if not user or user.__class__.__name__ != 'Profesor':
            messages.warning(request, 'Acceso restringido a Profesores')
            return redirect('profesores:login_profesor')
        request.user_obj = user
        return view_func(request, *args, **kwargs)

    return wrapper


def requiere_padre(view_func):
    def wrapper(request, *args, **kwargs):
        user = get_user_from_session(request)
        if not user or user.__class__.__name__ != 'Padre':
            messages.warning(request, 'Acceso restringido a Padres')
            return redirect('padres:login_padre')
        request.user_obj = user
        return view_func(request, *args, **kwargs)

    return wrapper


@requiere_servicio_escolar
def theme_settings(request):
    print("\n=== INICIO DE DEPURACIÓN theme_settings ===")
    print(f"Usuario autenticado: {request.user_obj} | Tipo: {type(request.user_obj)}")

    theme_config = ThemeConfig.objects.first()
    if not theme_config:
        theme_config = ThemeConfig.objects.create()
        print("¡Nuevo ThemeConfig creado!")

    print(f"Configuración actual - Tema global: {theme_config.global_theme}")
    print(f"Permisos actuales - Profesores: {theme_config.allow_profesors} | Padres: {theme_config.allow_padres}")

    if request.method == 'POST':
        print("\nDatos POST recibidos:")
        for key, value in request.POST.items():
            print(f"{key}: {value}")

        # 1. Actualizar el tema global (si se envió)
        if 'active_theme' in request.POST:
            new_theme = request.POST['active_theme']
            temas_validos = [choice[0] for choice in ThemeConfig.THEME_CHOICES]
            print(f"Validando tema - Recibido: '{new_theme}' | Válidos: {temas_validos}")

            if new_theme in temas_validos:
                theme_config.global_theme = new_theme
                theme_config.set_last_updated_by(request.user_obj)
                print(f"¡Tema actualizado a: {new_theme}!")
            else:
                print(f"¡Tema inválido detectado!: {new_theme}")

        # 2. Actualizar los permisos (checkboxes)
        theme_config.allow_profesors = 'allow_profesors' in request.POST  # True si el checkbox está marcado
        theme_config.allow_padres = 'allow_padres' in request.POST  # True si el checkbox está marcado
        print(
            f"Permisos actualizados - Profesores: {theme_config.allow_profesors} | Padres: {theme_config.allow_padres}")

        theme_config.save()
        print("¡Configuración guardada!")
        return redirect('servicios_escolares:theme_settings')

    return render(request, 'servicios_escolares/theme_settings.html', {
        'theme_config': theme_config,
        'THEME_CHOICES': ThemeConfig.THEME_CHOICES
    })


def user_theme_settings(request):
    user_obj = get_user_from_session(request)

    if not user_obj:
        messages.error(request, 'Debes iniciar sesión')
        return redirect('login_general')

    if not ThemeConfig.can_user_change_theme(user_obj):
        messages.warning(request, 'No tienes permiso para cambiar el tema')
        return redirect('profesores:login_profesor')

    if request.method == 'POST':
        theme = request.POST.get('theme')
        if theme in [t[0] for t in ThemeConfig.THEME_CHOICES]:
            if user_obj.__class__.__name__ == 'ServicioEscolar':
                ThemeConfig.objects.update_or_create(
                    pk=1,
                    defaults={'global_theme': theme}
                )
            else:
                user_obj.personal_theme = theme
                user_obj.save()
            messages.success(request, 'Tema actualizado')
        return redirect('user_theme_settings')

    return render(request, 'theme/user_settings.html', {
        'theme_choices': ThemeConfig.THEME_CHOICES,
        'is_global': user_obj.__class__.__name__ == 'ServicioEscolar'
    })


@requiere_servicio_escolar
def api_eventos_servicio_escolar(request):
    usuario = getattr(request, 'user_obj', None)
    eventos = []

    if usuario and usuario.__class__.__name__ == 'ServicioEscolar':
        servicio_ct = ContentType.objects.get_for_model(ServicioEscolar)
        profesor_ct = ContentType.objects.get_for_model(Profesor)

        estado = request.GET.get('estado')

        citas_creadas = Cita.objects.filter(
            creador_tipo=servicio_ct,
            creador_id=usuario.id
        )
        citas_como_agendador = Cita.objects.filter(
            servicio_escolar=usuario
        )
        citas_como_asistente = Cita.objects.filter(
            asistentes_servicio=usuario
        ).exclude(
            Q(creador_tipo=servicio_ct, creador_id=usuario.id) |
            Q(servicio_escolar=usuario)
        )
        citas_solicitadas_por_padres = Cita.objects.filter(
            solicitante__isnull=False,
            asistentes_servicio=usuario
        ).exclude(
            creador_tipo=servicio_ct
        )
        citas_de_profesores = Cita.objects.filter(
            creador_tipo=profesor_ct,
            asistentes_servicio=usuario
        )

        if estado and estado in dict(Cita.ESTADOS):
            citas_creadas = citas_creadas.filter(estado=estado)
            citas_como_agendador = citas_como_agendador.filter(estado=estado)
            citas_como_asistente = citas_como_asistente.filter(estado=estado)
            citas_solicitadas_por_padres = citas_solicitadas_por_padres.filter(estado=estado)
            citas_de_profesores = citas_de_profesores.filter(estado=estado)

        todas = (
                list(citas_creadas) +
                list(citas_como_agendador) +
                list(citas_como_asistente) +
                list(citas_solicitadas_por_padres) +
                list(citas_de_profesores)
        )

        citas_unicas = list({cita.id: cita for cita in todas}.values())

        for cita in citas_unicas:
            eventos.append({
                'id': cita.id,
                'title': cita.titulo,
                'start': seguro_localtime(cita.fecha_hora_inicio).isoformat(),
                'end': seguro_localtime(cita.fecha_hora_fin).isoformat(),
                'backgroundColor': estado_color(cita.estado),
                'borderColor': estado_color(cita.estado),
                'textColor': 'white',
                'extendedProps': {
                    'estado': cita.get_estado_display(),
                    'tipo': cita.get_tipo_display(),
                    'descripcion': cita.motivo,
                    'ubicacion': cita.ubicacion,
                    'solicitante': str(cita.solicitante),
                    'estudiantes': cita.estudiantes_list()
                }
            })

    return JsonResponse(eventos, safe=False)


def seguro_localtime(dt):
    return localtime(dt) if is_naive(dt) else dt


def estado_color(estado):
    colores = {
        'pendiente': '#f1c40f',  # amarillo
        'confirmada': '#2ecc71',  # verde
        'completada': '#3498db',  # azul
        'cancelada': '#e74c3c',  # rojo
        'reprogramada': '#e67e22',  # naranja
    }
    return colores.get(estado, '#95a5a6')  # gris por defecto


@requiere_servicio_escolar
def lista_grados_grupos_padres(request):
    # Obtener todos los grados con sus grupos (usando el related_name correcto: 'grupos')
    grados = Grado.objects.select_related('nivel', 'ciclo').prefetch_related('grupos').order_by('nivel__orden',
                                                                                                'numero')

    estructura = []

    for grado in grados:
        grupos_del_grado = grado.grupos.all().order_by('letra')  # Accede a los grupos usando el related_name

        grupos_con_padres = []

        for grupo in grupos_del_grado:
            estudiantes_del_grupo = Estudiante.objects.filter(grupo_actual=grupo).select_related('padre')

            padres_en_grupo = {}

            for estudiante in estudiantes_del_grupo:
                if estudiante.padre:
                    if estudiante.padre.id not in padres_en_grupo:
                        padres_en_grupo[estudiante.padre.id] = {
                            'padre': estudiante.padre,
                            'estudiantes': []
                        }
                    padres_en_grupo[estudiante.padre.id]['estudiantes'].append(estudiante)

            grupos_con_padres.append({
                'grupo': grupo,
                'padres': list(padres_en_grupo.values())
            })

        estructura.append({
            'grado': grado,
            'grupos': grupos_con_padres
        })

    return render(request, 'servicios_escolares/administracion/grados_grupos_padres.html', {
        'estructura': estructura
    })


@requiere_servicio_escolar
def detalle_padre(request, padre_id):
    # Obtener el padre y sus estudiantes
    padre = get_object_or_404(Padre, id=padre_id)
    estudiantes = Estudiante.objects.filter(padre=padre).select_related('grupo_actual')

    # Obtener todas las citas del padre
    citas_solicitadas = Cita.objects.filter(
        solicitante=padre
    ).order_by('-fecha_hora_inicio').select_related('profesor', 'servicio_escolar')

    citas_como_asistente = Cita.objects.filter(
        asistentes_padres=padre
    ).order_by('-fecha_hora_inicio').select_related('profesor', 'servicio_escolar')

    # Obtener citas prioritarias
    citas_prioritarias = CitaPrioritaria.objects.filter(
        solicitante=padre
    ).order_by('nivel_prioridad', '-fecha_hora_inicio')

    # Obtener reprogramaciones
    reprogramaciones = ReprogramacionCita.objects.filter(
        cita_original__solicitante=padre
    ).order_by('-fecha_reprogramacion')

    # Obtener notas relacionadas
    notas_enviadas = Nota.objects.filter(
        creador_padre=padre
    ).order_by('-fecha_creacion')

    notas_recibidas = Nota.objects.filter(
        destinatario_padre=padre
    ).order_by('-fecha_creacion')

    # Obtener notificaciones relacionadas
    notificaciones = Notification.objects.filter(
        recipient_ct=ContentType.objects.get_for_model(Padre),
        recipient_id=padre.id
    ).order_by('-created_at').select_related(
        'sender_ct', 'target_ct'
    )

    return render(request, 'servicios_escolares/administracion/detalle_padre.html', {
        'padre': padre,
        'estudiantes': estudiantes,
        'citas_solicitadas': citas_solicitadas,
        'citas_como_asistente': citas_como_asistente,
        'notas_enviadas': notas_enviadas,
        'notas_recibidas': notas_recibidas,
        'notificaciones': notificaciones,
        'citas_prioritarias': citas_prioritarias,
        'reprogramaciones': reprogramaciones,
    })


@require_POST
@requiere_servicio_escolar
def marcar_todas_leidas(request, padre_id):
    padre = get_object_or_404(Padre, id=padre_id)

    Notification.objects.filter(
        recipient_ct=ContentType.objects.get_for_model(Padre),
        recipient_id=padre.id,
        is_read=False
    ).update(is_read=True)

    messages.success(request, 'Todas las notificaciones han sido marcadas como leídas')
    return redirect('detalle_padre', padre_id=padre.id)
