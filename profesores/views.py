import hashlib
import json
import logging
import pytz
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.template.defaulttags import now
from django.views.decorators.http import require_POST
from MACE import settings
from formularios.models import EncuestaAplicada, Respuesta
from notificaciones.models import Notification
from padres.models import Padre
from servicios_escolares.models import ServicioEscolar, ThemeConfig
from ticket_soporte.models import TicketSoporte
from .forms import RegistroProfesorForm, LoginProfesorForm, EditarPerfilForm, TiempoLibreForm, CitaPrioritariaForm
from .models import Profesor, Calificacion, TiempoLibreProfesor
from django.contrib import messages
from datetime import datetime, timedelta, date, time
from calendar import monthrange
from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import render, redirect, get_object_or_404
from .models import Profesor, Clase, HorarioClase
from estudiantes.models import Grupo, CicloEscolar, Estudiante, PeriodoEscolar
from .forms import ClaseForm, HorarioFormSet, HorarioClaseForm
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView, FormView
from django.urls import reverse_lazy
from django.db.models import Prefetch
from django.db import models  # Para models.Q
from citas.models import Cita, CitaPrioritaria, ReprogramacionCita  # Para el modelo Cita
from django.views.generic import TemplateView
from django.utils import timezone
from datetime import timedelta, datetime
from .forms import ReprogramarCitaForm
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.apps import apps
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def registro_profesor_view(request):
    if request.method == 'POST':
        form = RegistroProfesorForm(request.POST, request.FILES)
        if form.is_valid():
            profesor = form.save()

            # Notificar a todos los servicio escolar activos
            destinatarios = ServicioEscolar.objects.filter(estado_cuenta='Activo')
            for destinatario in destinatarios:
                Notification.crear_notificacion(
                    event_type='servicio_nuevo_profesor',
                    recipient=destinatario,
                    message=f"El profesor {profesor.nombre_completo} se ha registrado en el sistema.",
                    rol_destinatario='servicio'  # Forzar rol explícitamente
                )

            messages.success(request, '¡Registro exitoso! Por favor inicia sesión.')
            return redirect('profesores:login_profesor')
    else:
        form = RegistroProfesorForm()

    return render(request, 'profesores/registro.html', {'form': form})


def login_profesor_view(request):
    # Verificar si el profesor ya está logueado
    if request.session.get('credenciales_profesor'):
        return redirect('profesores:dashboard_profesor')

    if request.method == 'POST':
        form = LoginProfesorForm(request.POST)
        if form.is_valid():
            correo = form.cleaned_data['correo_electronico']
            try:
                profesor = Profesor.objects.get(correo_electronico=correo)

                if not check_password(form.cleaned_data['contraseña'], profesor.contraseña):
                    form.add_error('contraseña', 'Credenciales incorrectas')
                    return render(request, 'profesores/login.html', {'form': form})

                # Actualizar fecha de sesión ANTES de generar el hash
                profesor.ultima_fecha_sesion = timezone.now().date()
                profesor.save(update_fields=['ultima_fecha_sesion'])

                # Generar hash con los datos actualizados
                session_hash = f"{profesor.correo_electronico}-{profesor.ultima_fecha_sesion}".encode('utf-8').hex()

                request.session['credenciales_profesor'] = {
                    'id': profesor.id,
                    'hash_credencial': session_hash,
                    'rol': profesor.rol_usuario
                }
                request.session['ultima_actividad'] = timezone.now().isoformat()

                messages.success(request, f'Bienvenido Prof. {profesor.nombre_completo}')
                return redirect('profesores:dashboard_profesor')

            except Profesor.DoesNotExist:
                form.add_error('correo_electronico', 'Credenciales incorrectas')
    else:
        form = LoginProfesorForm()

    return render(request, 'profesores/login.html', {'form': form})


def generate_session_hash(profesor):
    """Genera un hash seguro para la sesión"""
    data = f"{profesor.correo_electronico}-{profesor.ultima_fecha_sesion}-{timezone.now().timestamp()}"
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def logout_profesor_view(request):
    if 'credenciales_profesor' in request.session:
        # Opcional: Registrar el logout si necesitas auditoría
        # profesor_id = request.session['credenciales_profesor']['id']
        # profesor = Profesor.objects.get(id=profesor_id)
        # profesor.ultimo_logout = timezone.now()
        # profesor.save()

        # Limpiar la sesión
        del request.session['credenciales_profesor']
        del request.session['ultima_actividad']

        # Mensaje de confirmación
        messages.add_message(
            request,
            messages.SUCCESS,
            'Has cerrado sesión correctamente.',
            extra_tags='logout_message'
        )

    return redirect('profesores:login_profesor')


def dashboard_profesor_view(request):
    # 1. Verificación básica de sesión
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        # 2. Obtener profesor y validar sesión
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])

        # Generar hash esperado con los mismos datos que en login
        expected_hash = f"{profesor.correo_electronico}-{profesor.ultima_fecha_sesion}".encode('utf-8').hex()
        session_hash = request.session['credenciales_profesor'].get('hash_credencial', '')

        if session_hash != expected_hash:
            logger.warning(f"Hash de sesión inválido para profesor {profesor.id}")
            messages.error(request, 'Sesión inválida')
            return redirect('profesores:logout_profesor')

        # 3. Verificar inactividad (manejo más robusto)
        ultima_actividad_str = request.session.get('ultima_actividad')
        if ultima_actividad_str:
            try:
                ultima_actividad = datetime.strptime(ultima_actividad_str, '%Y-%m-%d %H:%M:%S')
                ultima_actividad = timezone.make_aware(ultima_actividad)

                if (timezone.now() - ultima_actividad).total_seconds() > 1800:  # 30 minutos
                    messages.warning(request, 'Sesión expirada por inactividad')
                    return redirect('profesores:logout_profesor')
            except ValueError as e:
                logger.error(f"Error al parsear fecha de actividad: {str(e)}")
                # No redirigir por error de formato, solo registrar

        # 4. Actualizar actividad
        request.session['ultima_actividad'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        profesor.ultima_fecha_sesion = timezone.now().date()
        profesor.save(update_fields=['ultima_fecha_sesion'])

        # 5. Obtener datos para el dashboard
        notificaciones = profesor.get_notificaciones() if hasattr(profesor, 'get_notificaciones') else []
        notificaciones_no_leidas = [n for n in notificaciones if not n.get('is_read', True)]
        notificaciones_recientes = notificaciones[:5]
        contador_no_leidas = len(notificaciones_no_leidas)

        # Verificar encuesta pendiente
        encuesta_pendiente = False
        encuesta_aplicada = EncuestaAplicada.objects.filter(activa=True).first()

        if encuesta_aplicada:
            encuesta_pendiente = not Respuesta.objects.filter(
                encuesta_aplicada=encuesta_aplicada,
                profesor=profesor
            ).exists()

        # Consulta optimizada de citas
        citas = Cita.objects.filter(
            models.Q(profesor=profesor) | models.Q(asistentes_profesores=profesor)
        ).distinct().select_related('solicitante').order_by('-fecha_hora_inicio')

        # 6. Obtener datos en paralelo (optimizado)
        profesor_ct = ContentType.objects.get_for_model(Profesor)
        estado_filtro = request.GET.get('estado')

        ahora = timezone.now()

        citas_base = Cita.objects.filter(
            (models.Q(profesor=profesor) | models.Q(asistentes_profesores=profesor)) &
            ~models.Q(estado='completada') &  # Excluir completadas
            models.Q(fecha_hora_inicio__gte=ahora)  # Solo citas que no hayan iniciado aún
        ).select_related(
            'solicitante', 'profesor', 'servicio_escolar'
        ).distinct()

        citas_creadas = citas_base.filter(
            creador_tipo=profesor_ct,
            creador_id=profesor.id
        )

        citas_solicitadas = citas_base.filter(
            profesor=profesor,
            solicitante__isnull=False
        ).exclude(
            creador_tipo=profesor_ct,
            creador_id=profesor.id
        )

        citas_prioritarias = CitaPrioritaria.objects.filter(
            models.Q(profesor=profesor) |
            models.Q(asistentes_profesores=profesor),
            fecha_hora_fin__gte=timezone.now()
        ).select_related(
            'solicitante', 'profesor', 'servicio_escolar'
        ).order_by('nivel_prioridad', '-fecha_hora_inicio')

        # Obtener la fecha y hora actual
        ahora = timezone.now()
        # Aplicar filtros si existen
        if estado_filtro in dict(Cita.ESTADOS):
            citas_creadas = citas_creadas.filter(
                estado=estado_filtro
            ).exclude(
                estado='completada'
            ).filter(
                fecha_hora_inicio__gte=ahora
            )

            citas_solicitadas = citas_solicitadas.filter(
                estado=estado_filtro
            ).exclude(
                estado='completada'
            ).filter(
                fecha_hora_inicio__gte=ahora
            )

            citas_prioritarias = citas_prioritarias.filter(
                estado=estado_filtro
            ).exclude(
                estado='completada'
            ).filter(
                fecha_hora_inicio__gte=ahora
            )

        # --- Obtener citas para completar ---
        citas_para_completar = Cita.objects.filter(
            profesor=profesor,  # Cambio principal: filtramos por profesor en lugar de servicio escolar
            estado__in=['confirmada', 'pendiente'],
            fecha_hora_fin__lt=timezone.now()
        ).exclude(estado='completada').distinct().order_by('-fecha_hora_inicio')

        # --- Citas con retroalimentación pendiente ---
        citas_con_retro_pendiente = Cita.objects.filter(
            profesor=profesor,  # Cambio principal: filtramos por profesor
            estado='completada',
            retroalimentacion__completada=False
        ).distinct().select_related('solicitante', 'retroalimentacion')

        logger.debug(f"Citas encontradas: {citas.count()}")

        # Verificar encuesta pendiente
        encuesta_pendiente = False
        encuesta_aplicada = EncuestaAplicada.objects.filter(activa=True).first()

        if encuesta_aplicada:
            encuesta_pendiente = not Respuesta.objects.filter(
                encuesta_aplicada=encuesta_aplicada,
                profesor=profesor
            ).exists()

        # 6. Preparar datos del calendario
        now = timezone.localtime(timezone.now())
        current_date = now.date()

        # Semana actual
        start_week = now - timedelta(days=now.weekday())
        week_days = [start_week + timedelta(days=i) for i in range(7)]

        # Mes actual
        year, month = now.year, now.month
        _, num_days = monthrange(year, month)
        calendar_days = [{
            'date': date(year, month, day),
            'current_month': True,
            'is_today': day == now.day
        } for day in range(1, num_days + 1)]

        month_weeks = [calendar_days[i:i + 7] for i in range(0, len(calendar_days), 7)]

        # 7. Procesar asignaturas de forma segura
        asignaturas = []
        if profesor.asignaturas_impartidas:
            try:
                asignaturas = json.loads(profesor.asignaturas_impartidas)
            except (json.JSONDecodeError, AttributeError):
                asignaturas = profesor.asignaturas_impartidas.split(',') if profesor.asignaturas_impartidas else []

        return render(request, 'profesores/index.html', {
            'profesor': profesor,
            'asignaturas': asignaturas,
            'encuesta_pendiente': encuesta_pendiente,
            'encuesta_url': reverse('formularios:contestar_encuesta') if encuesta_pendiente else None,
            'current_date': current_date,
            'week_days': week_days,
            'month_weeks': month_weeks,
            'horas': ["8:00", "10:00", "12:00", "14:00", "16:00", "18:00"],
            'citas_data': {
                'creadas': citas_creadas.order_by('-fecha_hora_inicio'),
                'solicitadas': citas_solicitadas.order_by('-fecha_hora_inicio'),
                'pendientes_creadas': citas_creadas.filter(estado='pendiente'),
                'pendientes_solicitadas': citas_solicitadas.filter(estado='pendiente'),
                'total': citas_creadas.count() + citas_solicitadas.count()
            },
            'citas_prioritarias': citas_prioritarias,
            'notificaciones_data': {
                'todas': notificaciones,
                'recientes': notificaciones_recientes,
                'no_leidas': notificaciones_no_leidas,
                'contador': contador_no_leidas
            },
            'citas_para_completar': citas_para_completar,
            'citas_con_retro_pendiente': citas_con_retro_pendiente,
        })

    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        logger.error(f"Profesor no encontrado en sesión: {request.session.get('credenciales_profesor', {}).get('id')}")
        return redirect('profesores:logout_profesor')
    except Exception as e:
        messages.error(request, 'Error al cargar el dashboard')
        logger.error(f"Error en dashboard_profesor_view: {str(e)}", exc_info=True)
        return redirect('profesores:logout_profesor')


def configuracion_view(request):
    # Verificar autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        print(f"Credenciales en sesión: {request.session.get('credenciales_profesor')}")
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')

    return render(request, 'profesores/configuracion.html', {
        'profesor': profesor
    })


def editar_perfil_view(request):
    # Verificar autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        # Obtener el profesor actual
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        print(f"Credenciales en sesión: {request.session.get('credenciales_profesor')}")
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')
    except Exception as e:
        messages.error(request, f'Error al obtener perfil: {str(e)}')
        return redirect('profesores:configuracion_profesor')

    if request.method == 'POST':
        form = EditarPerfilForm(request.POST, request.FILES, instance=profesor)

        # Depuración: Mostrar datos recibidos
        print("\n=== Datos del formulario ===")
        print("POST:", request.POST)
        print("FILES:", request.FILES)

        if form.is_valid():
            try:
                # Guardar los datos básicos primero
                profesor = form.save(commit=False)

                # Manejo especial para la contraseña
                nueva_contraseña = form.cleaned_data.get('nueva_contraseña')
                if nueva_contraseña:
                    profesor.contraseña = make_password(nueva_contraseña)
                    print("Contraseña actualizada")

                # Guardar todos los cambios
                profesor.save()

                # Depuración: Verificar cambios
                print("\n=== Después de guardar ===")
                print("Nombre:", profesor.nombre_completo)
                print("Email:", profesor.correo_electronico)
                print("Teléfono:", profesor.telefono_principal)
                if profesor.imagen_usuario:
                    print("Imagen:", profesor.imagen_usuario.url)

                messages.success(request, 'Perfil actualizado correctamente')
                return redirect('profesores:configuracion_profesor')

            except Exception as e:
                messages.error(request, f'Error al guardar los cambios: {str(e)}')
                print("Error al guardar:", str(e))
        else:
            # Mostrar errores de validación
            messages.error(request, 'Por favor corrige los errores en el formulario')
            print("\n=== Errores del formulario ===")
            for field, errors in form.errors.items():
                print(f"Campo {field}: {', '.join(errors)}")
    else:
        form = EditarPerfilForm(instance=profesor)

    return render(request, 'profesores/editar_perfil.html', {
        'form': form,
        'profesor': profesor
    })


def profesor_dashboard(request):
    # Verificar autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')

    ciclo_actual = CicloEscolar.obtener_actual()

    # --- Obtener citas para completar ---
    citas_para_completar = Cita.objects.filter(
        profesor=profesor,
        estado__in=['confirmada', 'pendiente'],
        fecha_hora_fin__lt=timezone.now()
    ).exclude(estado='completada').distinct().order_by('-fecha_hora_inicio')

    # --- Citas con retroalimentación pendiente ---
    citas_con_retro_pendiente = Cita.objects.filter(
        profesor=profesor,
        estado='completada',
        retroalimentacion__completada=False
    ).distinct().select_related('solicitante', 'retroalimentacion')

    # Imprimir resultados
    print("\n=== Citas para completar ===")
    for cita in citas_para_completar:
        print(f"ID: {cita.id} | Estado: {cita.estado} | Fecha: {cita.fecha_hora_inicio}")
        print(f"Padre: {cita.solicitante.nombre_completo}")
        print("-" * 50)

    print("\n=== Citas con retroalimentación pendiente ===")
    for cita in citas_con_retro_pendiente:
        print(f"ID: {cita.id} | Estado: {cita.estado} | Fecha: {cita.fecha_hora_inicio}")
        print(f"Padre: {cita.solicitante.nombre_completo}")
        print(f"Retroalimentación ID: {cita.retroalimentacion.id if cita.retroalimentacion else 'N/A'}")
        print("-" * 50)

    print(f"\nTotal citas para completar: {citas_para_completar.count()}")
    print(f"Total citas con retro pendiente: {citas_con_retro_pendiente.count()}")

    # Obtener todas las clases del profesor para el ciclo actual
    clases = Clase.objects.filter(
        profesor=profesor,
        ciclo_escolar=ciclo_actual
    ).select_related('grupo', 'ciclo_escolar').prefetch_related('horarios')

    # Obtener tiempos libres del profesor
    tiempos_libres = TiempoLibreProfesor.objects.filter(
        profesor=profesor,
        ciclo_escolar=ciclo_actual
    )

    # Preparar datos para el calendario semanal
    dias_semana = HorarioClase.DIAS_SEMANA
    horas = generar_rango_horas(7, 22)  # De 7am a 10pm

    # Preparar eventos para FullCalendar (si decides implementarlo)
    eventos_calendario = []
    for clase in clases:
        for horario in clase.horarios.all():
            eventos_calendario.append({
                'title': f"{clase.nombre} - {clase.grupo}",
                'start': f"2023-01-0{horario.dia_semana}T{horario.hora_inicio.strftime('%H:%M:%S')}",
                'end': f"2023-01-0{horario.dia_semana}T{horario.hora_fin.strftime('%H:%M:%S')}",
                'color': '#3a87ad',
                'extendedProps': {
                    'tipo': 'clase',
                    'aula': horario.aula,
                    'clase_id': clase.id
                }
            })

    for tiempo in tiempos_libres:
        eventos_calendario.append({
            'title': 'Tiempo Libre' + (f" - {tiempo.motivo}" if tiempo.motivo else ""),
            'start': f"2023-01-0{tiempo.dia_semana}T{tiempo.hora_inicio.strftime('%H:%M:%S')}",
            'end': f"2023-01-0{tiempo.dia_semana}T{tiempo.hora_fin.strftime('%H:%M:%S')}",
            'color': '#5cb85c',
            'extendedProps': {
                'tipo': 'tiempo_libre',
                'tiempo_id': tiempo.id
            }
        })

    context = {
        'profesor': profesor,
        'clases': clases,
        'dias_semana': dias_semana,
        'horas': horas,
        'tiempos_libres': tiempos_libres,
        'eventos_calendario': json.dumps(eventos_calendario),
        'ciclo_actual': ciclo_actual,
        'citas_para_completar': citas_para_completar,
        'citas_con_retro_pendiente': citas_con_retro_pendiente,
    }

    return render(request, 'profesores/horario/profesor_dashboard.html', context)


def generar_rango_horas(inicio, fin):
    from datetime import time
    return [time(hour=h) for h in range(inicio, fin)]


def agregar_clase(request):
    # Verificar autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')

    ciclo_actual = CicloEscolar.obtener_actual()
    if not ciclo_actual:
        messages.error(request, 'No hay un ciclo escolar activo')
        return redirect('profesores:panel_horario')

    if request.method == 'POST':
        form = ClaseForm(request.POST, profesor=profesor)
        formset = HorarioFormSet(request.POST, prefix='horarios')

        if form.is_valid():
            # Guardar la clase primero para tener un grupo asignado
            clase = form.save(commit=False)
            clase.profesor = profesor
            clase.ciclo_escolar = ciclo_actual
            clase.save()

            # Validar los horarios con la clase ya creada
            formset = HorarioFormSet(request.POST, prefix='horarios', instance=clase)
            if formset.is_valid():
                formset.save()
                messages.success(request, 'Clase y horarios guardados correctamente')
                return redirect('profesores:panel_horario')
            else:
                # Si falla el formset, eliminar la clase recién creada
                clase.delete()
                messages.error(request, 'Error al guardar horarios. La clase ha sido eliminada.')
    else:
        form = ClaseForm(profesor=profesor)
        formset = HorarioFormSet(prefix='horarios')

    # -------------------------------
    # Aquí obtenemos la configuración de tema y permisos
    # -------------------------------
    ThemeConfig = apps.get_model('servicios_escolares.ThemeConfig')
    theme_config = ThemeConfig.objects.first()

    personal_theme = getattr(profesor, 'personal_theme', None)
    global_theme = theme_config.global_theme if theme_config else 'css/themes/default.css'
    active_theme = personal_theme if personal_theme else global_theme
    can_change_theme = theme_config.allow_profesors if theme_config else False
    # -------------------------------

    context = {
        'form': form,
        'formset': formset,
        'ciclo_actual': ciclo_actual,
        # Contexto de tema y permisos:
        'es_profesor': True,
        'profesor': profesor,
        'can_change_theme': can_change_theme,
        'active_theme': active_theme,
        'personal_theme': personal_theme,
    }

    return render(request, 'profesores/horario/agregar_clase.html', context)


def editar_clase(request, clase_id):
    # Verificar autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')

    # Obtener la clase a editar (solo si pertenece al profesor)
    clase = get_object_or_404(Clase, id=clase_id, profesor=profesor)
    ciclo_actual = clase.ciclo_escolar

    if request.method == 'POST':
        form = ClaseForm(request.POST, instance=clase, profesor=profesor)
        formset = HorarioFormSet(request.POST, prefix='horarios', instance=clase)

        if form.is_valid():
            # Guardar los cambios en la clase
            clase_editada = form.save()

            # Validar y guardar los horarios
            if formset.is_valid():
                formset.save()
                messages.success(request, 'Clase y horarios actualizados correctamente')
                return redirect('profesores:panel_horario')
            else:
                # Si hay errores en los horarios, mostrar mensaje
                messages.error(request, 'Por favor corrige los errores en los horarios')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario')
    else:
        # Cargar formulario con datos existentes
        form = ClaseForm(instance=clase, profesor=profesor)
        formset = HorarioFormSet(prefix='horarios', instance=clase)

    return render(request, 'profesores/horario/editar_clase.html', {
        'form': form,
        'formset': formset,
        'clase': clase,
        'ciclo_actual': ciclo_actual
    })


def eliminar_clase(request, clase_id):
    # Verificar autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')

    clase = get_object_or_404(Clase, id=clase_id, profesor=profesor)

    if request.method == 'POST':
        clase.delete()
        messages.success(request, f'Clase "{clase.nombre}" eliminada correctamente')
        return redirect('profesores:panel_horario')

    # Obtener horarios asociados para mostrar en la confirmación
    horarios = clase.horarios.all().order_by('dia_semana', 'hora_inicio')

    return render(request, 'profesores/horario/eliminar_clase.html', {
        'clase': clase,
        'horarios': horarios
    })


def gestionar_horarios(request, clase_id):
    # Verificar autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')

    clase = get_object_or_404(Clase, id=clase_id, profesor=profesor)
    horarios = HorarioClase.objects.filter(clase=clase).order_by('dia_semana', 'hora_inicio')

    if request.method == 'POST':
        form = HorarioClaseForm(request.POST)
        if form.is_valid():
            horario = form.save(commit=False)
            horario.clase = clase
            try:
                horario.full_clean()
                horario.save()
                messages.success(request, 'Horario agregado correctamente')
                return redirect('profesores:gestionar_horarios', clase_id=clase.id)
            except ValidationError as e:
                messages.error(request, f'Error en el horario: {e}')
                form.add_error(None, e)
    else:
        form = HorarioClaseForm()

    return render(request, 'profesores/horario/gestionar_horarios.html', {
        'clase': clase,
        'horarios': horarios,
        'form': form,
    })


def eliminar_horario(request, horario_id):
    # Verificar autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')

    horario = get_object_or_404(HorarioClase, id=horario_id, clase__profesor=profesor)
    clase_id = horario.clase.id

    if request.method == 'POST':
        horario.delete()
        messages.success(request, 'Horario eliminado correctamente')
        return redirect('profesores:gestionar_horarios', clase_id=clase_id)

    return render(request, 'profesores/horario/eliminar_horario.html', {'horario': horario})


def asignar_calificaciones_grupo(profesor, clase_id, periodo_id, calificaciones_data):
    """
    Asigna calificaciones a los estudiantes de un grupo en una clase específica

    Parámetros:
        profesor (Profesor): Instancia del profesor que asigna las calificaciones
        clase_id (int): ID de la clase/materia
        periodo_id (int): ID del periodo escolar
        calificaciones_data (dict): Diccionario con {estudiante_id: {'calificacion': float, 'faltas': int}}

    Retorna:
        tuple: (calificaciones_creadas, calificaciones_actualizadas)

    Lanza:
        ValidationError: Si hay problemas con los datos
    """
    try:
        # Verificar que el profesor tiene asignada esta clase
        clase = Clase.objects.select_related('grupo', 'ciclo_escolar').get(
            pk=clase_id,
            profesor=profesor
        )

        periodo = PeriodoEscolar.objects.select_related('ciclo').get(pk=periodo_id)

        # Validar que el periodo pertenezca al ciclo de la clase
        if periodo.ciclo != clase.ciclo_escolar:
            raise ValidationError("El periodo no corresponde al ciclo escolar de esta clase")

        # Validar que la fecha actual esté dentro del periodo
        hoy = date.today()
        if not (periodo.fecha_inicio <= hoy <= periodo.fecha_fin):
            raise ValidationError("No se pueden asignar calificaciones fuera del periodo escolar")

        creadas = 0
        actualizadas = 0

        with transaction.atomic():
            for estudiante_id, datos in calificaciones_data.items():
                try:
                    estudiante = Estudiante.objects.get(
                        pk=estudiante_id,
                        grupo_actual=clase.grupo
                    )

                    # Validar que la calificación esté en el rango correcto (0-10)
                    calificacion_val = float(datos['calificacion'])
                    if not (0 <= calificacion_val <= 10):
                        raise ValidationError(
                            f"La calificación debe estar entre 0 y 10 (estudiante ID: {estudiante_id})")

                    # Crear o actualizar la calificación
                    calificacion, created = Calificacion.objects.update_or_create(
                        estudiante=estudiante,
                        clase=clase,
                        periodo=periodo,
                        defaults={
                            'calificacion': calificacion_val,
                            'faltas': datos.get('faltas', 0),
                            'fecha_registro': hoy
                        }
                    )

                    if created:
                        creadas += 1
                    else:
                        actualizadas += 1

                except Estudiante.DoesNotExist:
                    raise ValidationError(f"El estudiante {estudiante_id} no pertenece a este grupo")
                except ValueError:
                    raise ValidationError(f"Calificación inválida para el estudiante {estudiante_id}")

        return creadas, actualizadas

    except Clase.DoesNotExist:
        raise ValidationError("No tienes asignada esta clase o no existe")
    except PeriodoEscolar.DoesNotExist:
        raise ValidationError("El periodo escolar no existe")


def obtener_estudiantes_calificaciones(profesor, clase_id, periodo_id):
    """
    Obtiene los estudiantes y sus calificaciones actuales para una clase y periodo

    Parámetros:
        profesor (Profesor): Instancia del profesor
        clase_id (int): ID de la clase
        periodo_id (int): ID del periodo

    Retorna:
        dict: {
            'clase': Objeto Clase,
            'periodo': Objeto PeriodoEscolar,
            'estudiantes': QuerySet de estudiantes,
            'calificaciones_existentes': {estudiante_id: calificacion_data}
        }
    """
    try:
        # Verificar que el profesor tiene esta clase asignada
        clase = Clase.objects.select_related('grupo', 'ciclo_escolar').get(
            pk=clase_id,
            profesor=profesor
        )

        periodo = PeriodoEscolar.objects.get(pk=periodo_id)

        # Obtener todos los estudiantes del grupo
        estudiantes = Estudiante.objects.filter(
            grupo_actual=clase.grupo
        ).order_by('apellido_paterno', 'apellido_materno')

        # Obtener calificaciones existentes
        calificaciones = Calificacion.objects.filter(
            clase=clase,
            periodo=periodo
        ).select_related('estudiante')

        # Formatear calificaciones existentes
        calificaciones_existentes = {
            cal.estudiante.id: {
                'calificacion': float(cal.calificacion),
                'faltas': cal.faltas
            } for cal in calificaciones
        }

        return {
            'clase': clase,
            'periodo': periodo,
            'estudiantes': estudiantes,
            'calificaciones_existentes': calificaciones_existentes
        }

    except Clase.DoesNotExist:
        raise ValidationError("No tienes asignada esta clase o no existe")
    except PeriodoEscolar.DoesNotExist:
        raise ValidationError("El periodo escolar no existe")


def agregar_tiempo_libre(request):
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    profesor = get_object_or_404(Profesor, id=request.session['credenciales_profesor']['id'])
    ciclo_actual = CicloEscolar.obtener_actual()

    if not ciclo_actual:
        messages.error(request, 'No hay un ciclo escolar activo')
        return redirect('profesores:panel_horario')

    if request.method == 'POST':
        form = TiempoLibreForm(request.POST, profesor=profesor, ciclo_escolar=ciclo_actual)
        if form.is_valid():
            # Verificar si ya existe este horario
            existe = TiempoLibreProfesor.objects.filter(
                profesor=profesor,
                dia_semana=form.cleaned_data['dia_semana'],
                hora_inicio=form.cleaned_data['hora_inicio'],
                ciclo_escolar=ciclo_actual
            ).exists()

            if existe:
                messages.error(request, 'Ya tienes registrado este horario como tiempo libre')
            else:
                try:
                    form.save()
                    messages.success(request, 'Tiempo libre registrado correctamente')
                    return redirect('profesores:panel_horario')
                except ValidationError as e:
                    form.add_error(None, e)
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, f"{field}: {error}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = TiempoLibreForm()

    # --- Agregar contexto de temas personalizados ---
    ThemeConfig = apps.get_model('servicios_escolares.ThemeConfig')
    theme_config = ThemeConfig.objects.first()
    personal_theme = getattr(profesor, 'personal_theme', None)
    global_theme = theme_config.global_theme if theme_config else 'css/themes/default.css'
    active_theme = personal_theme if personal_theme else global_theme
    can_change_theme = theme_config.allow_profesors if theme_config else False

    context = {
        'form': form,
        'ciclo_actual': ciclo_actual,
        'es_profesor': True,
        'profesor': profesor,
        'can_change_theme': can_change_theme,
        'active_theme': active_theme,
        'personal_theme': personal_theme,
    }

    return render(request, 'profesores/horario/agregar_tiempo_libre.html', context)


def editar_tiempo_libre(request, id):
    tiempo_libre = get_object_or_404(TiempoLibreProfesor, id=id,
                                     profesor_id=request.session['credenciales_profesor']['id'])

    if request.method == 'POST':
        form = TiempoLibreForm(request.POST, instance=tiempo_libre)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Tiempo libre actualizado correctamente')
                return redirect('profesores:panel_horario')
            except ValidationError as e:
                for field, errors in e.error_dict.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
    else:
        form = TiempoLibreForm(instance=tiempo_libre)

    return render(request, 'profesores/horario/editar_tiempo_libre.html', {
        'form': form,
        'tiempo_libre': tiempo_libre
    })


def eliminar_tiempo_libre(request, id):
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    profesor = get_object_or_404(Profesor, id=request.session['credenciales_profesor']['id'])
    tiempo_libre = get_object_or_404(TiempoLibreProfesor, id=id, profesor=profesor)

    if request.method == 'POST':
        tiempo_libre.delete()
        messages.success(request, 'Tiempo libre eliminado correctamente')
        return redirect('profesores:dashboard_profesor')

    # --- Agregar contexto de temas personalizados ---
    ThemeConfig = apps.get_model('servicios_escolares.ThemeConfig')
    theme_config = ThemeConfig.objects.first()
    personal_theme = getattr(profesor, 'personal_theme', None)
    global_theme = theme_config.global_theme if theme_config else 'css/themes/default.css'
    active_theme = personal_theme if personal_theme else global_theme
    can_change_theme = theme_config.allow_profesors if theme_config else False

    context = {
        'tiempo_libre': tiempo_libre,
        'es_profesor': True,
        'profesor': profesor,
        'can_change_theme': can_change_theme,
        'active_theme': active_theme,
        'personal_theme': personal_theme,
    }

    return render(request, 'profesores/horario/eliminar_tiempo_libre.html', context)


class PanelCitasProfesor(ListView):
    template_name = 'profesores/citas/panel_citas.html'
    context_object_name = 'clases'

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('credenciales_profesor'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('profesores:login_profesor')

        try:
            self.profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        except Profesor.DoesNotExist:
            messages.error(request, 'Profesor no encontrado')
            return redirect('profesores:logout_profesor')

        # Cargar configuración de tema y permisos para profesores
        ThemeConfig = apps.get_model('servicios_escolares.ThemeConfig')
        theme_config = ThemeConfig.objects.first()
        self.personal_theme = getattr(self.profesor, 'personal_theme', None)
        self.global_theme = theme_config.global_theme if theme_config else 'css/themes/default.css'
        self.active_theme = self.personal_theme if self.personal_theme else self.global_theme
        self.can_change_theme = theme_config.allow_profesors if theme_config else False

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Clase.objects.filter(profesor=self.profesor).select_related(
            'grupo', 'ciclo_escolar'
        ).prefetch_related(
            Prefetch('grupo__estudiantes', queryset=Estudiante.objects.select_related('padre'))
        ).order_by('grupo__grado__nivel__orden', 'grupo__grado__numero', 'grupo__letra')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['citas_proximas'] = Cita.objects.filter(
            profesor=self.profesor,
            fecha_hora_inicio__gte=timezone.now()
        ).order_by('fecha_hora_inicio')[:5]

        # Agregar contexto para temas y permisos
        context.update({
            'es_profesor': True,
            'profesor': self.profesor,
            'can_change_theme': self.can_change_theme,
            'active_theme': self.active_theme,
            'personal_theme': self.personal_theme,
        })

        return context


class ListaEstudiantesCitas(ListView):
    template_name = 'profesores/citas/lista_estudiantes_citas.html'
    context_object_name = 'estudiantes'

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('credenciales_profesor'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('profesores:login_profesor')

        try:
            self.profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        except Profesor.DoesNotExist:
            messages.error(request, 'Profesor no encontrado')
            return redirect('profesores:logout_profesor')

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        clase_id = self.kwargs['clase_id']
        self.clase = get_object_or_404(Clase, id=clase_id)

        # Verificar que el profesor es el titular de la clase
        if self.clase.profesor != self.profesor:
            messages.error(self.request, 'No tienes permiso para acceder a esta clase')
            return redirect('profesores:panel_citas')

        return Estudiante.objects.filter(
            grupo_actual=self.clase.grupo
        ).select_related('padre').order_by('apellido_paterno', 'apellido_materno')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Contexto de la clase
        context['clase'] = self.clase

        # -------------------------------
        # Agregar el contexto del tema
        # -------------------------------
        ThemeConfig = apps.get_model('servicios_escolares.ThemeConfig')
        theme_config = ThemeConfig.objects.first()

        personal_theme = getattr(self.profesor, 'personal_theme', None)
        global_theme = theme_config.global_theme if theme_config else 'css/themes/default.css'
        active_theme = personal_theme if personal_theme else global_theme
        can_change_theme = theme_config.allow_profesors if theme_config else False

        context.update({
            'es_profesor': True,
            'profesor': self.profesor,
            'can_change_theme': can_change_theme,
            'active_theme': active_theme,
            'personal_theme': personal_theme,
        })

        return context


class CrearCitaEstudiante(CreateView):
    model = Cita
    template_name = 'profesores/citas/crear_cita.html'
    fields = ['titulo', 'tipo', 'fecha_hora_inicio', 'duracion', 'motivo', 'ubicacion']

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('credenciales_profesor'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('profesores:login_profesor')

        try:
            self.profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        except Profesor.DoesNotExist:
            messages.error(request, 'Profesor no encontrado')
            return redirect('profesores:logout_profesor')

        self.estudiante = get_object_or_404(Estudiante, id=self.kwargs['estudiante_id'])

        if not Clase.objects.filter(profesor=self.profesor, grupo=self.estudiante.grupo_actual).exists():
            messages.error(request, 'No tienes permiso para agendar citas con este estudiante')
            return redirect('profesores:panel_citas')

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        tomorrow = timezone.now() + timedelta(days=1)
        default_date = datetime.combine(tomorrow.date(), datetime.strptime('08:00', '%H:%M').time())
        default_date = timezone.make_aware(default_date)

        initial.update({
            'fecha_hora_inicio': default_date,
            'duracion': 30,
            'titulo': f"Reunión sobre {self.estudiante.nombre_completo()}",
            'motivo': f"Analizar el desempeño académico de {self.estudiante.nombre_completo()}",
            'ubicacion': 'Sala de profesores'
        })
        return initial

    def form_valid(self, form):
        form.instance.solicitante = self.estudiante.padre
        form.instance.profesor = self.profesor

        # Asignar el creador genérico (GenericForeignKey)
        profesor_ct = ContentType.objects.get_for_model(Profesor)
        form.instance.creador_tipo = profesor_ct
        form.instance.creador_id = self.profesor.id

        # Asignar automáticamente al estudiante involucrado
        response = super().form_valid(form)
        self.object.estudiantes.add(self.estudiante)

        messages.success(self.request, 'Cita agendada exitosamente')
        return response

    def get_success_url(self):
        return reverse_lazy('profesores:lista_estudiantes_citas',
                            kwargs={'clase_id': self.estudiante.grupo_actual.clases.first().id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['estudiante'] = self.estudiante
        context['clase_id'] = self.estudiante.grupo_actual.clases.first().id
        context['mostrar_boton_prioritario'] = True

        # -------------------------------
        # Contexto del tema y permisos
        # -------------------------------
        ThemeConfig = apps.get_model('servicios_escolares.ThemeConfig')
        theme_config = ThemeConfig.objects.first()

        personal_theme = getattr(self.profesor, 'personal_theme', None)
        global_theme = theme_config.global_theme if theme_config else 'css/themes/default.css'
        active_theme = personal_theme if personal_theme else global_theme
        can_change_theme = theme_config.allow_profesors if theme_config else False

        context['es_profesor'] = True
        context['profesor'] = self.profesor
        context['can_change_theme'] = can_change_theme
        context['active_theme'] = active_theme
        context['personal_theme'] = personal_theme
        # -------------------------------

        return context


class CrearCitaPrioritariaView(CreateView):
    model = CitaPrioritaria
    form_class = CitaPrioritariaForm
    template_name = 'profesores/citas/crear_cita_prioritaria.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['estudiante'] = self.estudiante
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        ahora = timezone.localtime(timezone.now())
        initial.update({
            'fecha_hora_inicio': (ahora + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'duracion': 30,
            'ubicacion': 'Escuela'
        })
        return initial

    def form_invalid(self, form):
        print("\n=== FORMULARIO INVÁLIDO ===")
        print(f"[DEBUG] Errores del formulario: {form.errors}")
        print(f"[DEBUG] Non-field errors: {form.non_field_errors()}")
        self.object = None
        return super().form_invalid(form)

    def get(self, request, *args, **kwargs):
        print("\n=== INICIO GET ===")
        form = self.get_form()
        print(f"[DEBUG] Formulario inicial: {form}")
        print(f"[DEBUG] Valores iniciales: {form.initial}")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        print("\n=== INICIO POST ===")
        form = self.get_form()
        print(f"[DEBUG] Formulario bound: {form.is_bound}")
        print(f"[DEBUG] Datos POST: {request.POST}")
        print(f"[DEBUG] Archivos: {request.FILES}")

        if form.is_valid():
            print("[DEBUG] Formulario válido, procediendo a form_valid")
            return self.form_valid(form)
        else:
            print("[DEBUG] Formulario inválido, procediendo a form_invalid")
            return self.form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        print("\n=== INICIO DISPATCH ===")
        if not request.session.get('credenciales_profesor'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('profesores:login_profesor')

        try:
            self.profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        except Profesor.DoesNotExist:
            messages.error(request, 'Profesor no encontrado')
            return redirect('profesores:logout_profesor')

        self.estudiante = get_object_or_404(Estudiante, id=self.kwargs['estudiante_id'])

        if not hasattr(self.estudiante, 'grupo_actual') or not self.estudiante.grupo_actual:
            messages.error(request, 'El estudiante no tiene grupo asignado')
            return redirect('profesores:panel_citas')

        try:
            self.clase = Clase.objects.get(profesor=self.profesor, grupo=self.estudiante.grupo_actual)
        except Clase.DoesNotExist:
            messages.error(request, 'No tienes permiso para agendar citas con este estudiante')
            return redirect('profesores:panel_citas')

        print("=== FIN DISPATCH ===")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        self.object = None
        context = super().get_context_data(**kwargs)
        tz_mexico = pytz.timezone('America/Mexico_City')
        ahora = timezone.localtime(timezone.now(), tz_mexico)

        hora_minima_hoy = ahora + timedelta(hours=1)
        if hora_minima_hoy.time() < time(8, 0):
            hora_minima_hoy = hora_minima_hoy.replace(hour=8, minute=0)

        hora_minima_futuro = ahora.replace(hour=8, minute=0, second=0, microsecond=0)
        hora_maxima_diaria = ahora.replace(hour=17, minute=30, second=0, microsecond=0)

        # Aquí agregamos la lógica del tema
        theme_config = getattr(self.profesor, 'theme_config', None)  # suponiendo que existe esa relación
        personal_theme = getattr(self.profesor, 'personal_theme', None)
        global_theme = theme_config.global_theme if theme_config else 'css/themes/default.css'
        active_theme = personal_theme if personal_theme else global_theme
        can_change_theme = theme_config.allow_profesors if theme_config else False

        context.update({
            'estudiante': self.estudiante,
            'clase_id': self.clase.id,
            'now': ahora,
            'hora_minima_hoy': hora_minima_hoy,
            'hora_minima_futuro': hora_minima_futuro,
            'hora_maxima_diaria': hora_maxima_diaria,
            'hora_minima_legible': hora_minima_hoy.strftime('%H:%M'),
            'hora_maxima_legible': hora_maxima_diaria.strftime('%H:%M'),
            'es_profesor': True,
            'profesor': self.profesor,
            'can_change_theme': can_change_theme,
            'active_theme': active_theme,
            'personal_theme': personal_theme,
        })
        return context

    def form_valid(self, form):
        print("\n=== INICIO FORM_VALID ===")
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
        except Exception as e:
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
            form.add_error('fecha_hora_inicio', 'Último horario disponible: 17:30 (para permitir 30 min de duración)')
            return self.form_invalid(form)

        if fecha_hora.weekday() >= 5:
            form.add_error('fecha_hora_inicio', 'No se pueden agendar citas los fines de semana')
            return self.form_invalid(form)

        cita = form.save(commit=False)
        cita.profesor = self.profesor
        cita.solicitante = self.estudiante.padre
        cita.tipo = 'emergencia'  # si el campo sigue existiendo

        try:
            cita.save()
            form.save_m2m()
            cita.estudiantes.add(self.estudiante)
            self.object = cita
            messages.success(self.request, 'Cita prioritaria creada con éxito')
            return HttpResponseRedirect(self.get_success_url())
        except Exception as e:
            print(f"[DEBUG] Error al guardar: {str(e)}")
            return self.form_invalid(form)

    def get_success_url(self):
        try:
            url = reverse('profesores:lista_estudiantes_citas', args=[self.clase.id])
            return url
        except Exception:
            return f'/profesores/citas/clase/{self.clase.id}/estudiantes/'


class CalendarioCitasProfesor(TemplateView):
    template_name = 'profesores/citas/calendario_citas.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('credenciales_profesor'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('profesores:login_profesor')

        try:
            self.profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        except Profesor.DoesNotExist:
            messages.error(request, 'Profesor no encontrado')
            return redirect('profesores:logout_profesor')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        today = now.date()

        # Manejo de mes/año seleccionado
        year = int(self.request.GET.get('year', now.year))
        month = int(self.request.GET.get('month', now.month))

        # Fechas para el calendario
        first_day = datetime(year, month, 1)
        last_day = datetime(year, month + 1, 1) - timedelta(days=1) if month < 12 else datetime(year + 1, 1,
                                                                                                1) - timedelta(days=1)

        creador_tipo_profesor = ContentType.objects.get_for_model(Profesor)

        # Obtener todas las citas del mes
        citas_mes = Cita.objects.filter(
            profesor=self.profesor,
            fecha_hora_inicio__range=[first_day, last_day]
        ).select_related('solicitante').order_by('fecha_hora_inicio')

        # Obtener citas para las secciones adicionales
        citas_hoy = Cita.objects.filter(
            profesor=self.profesor,
            fecha_hora_inicio__date=today
        ).order_by('fecha_hora_inicio')

        citas_proximas = Cita.objects.filter(
            profesor=self.profesor,
            fecha_hora_inicio__gt=now,
            estado__in=['pendiente', 'confirmada']
        ).exclude(fecha_hora_inicio__date=today).order_by('fecha_hora_inicio')[:5]

        citas_pendientes = Cita.objects.filter(
            creador_tipo=creador_tipo_profesor,
            creador_id=self.profesor.id,
            profesor=self.profesor,
            estado__in=['pendiente', 'reprogramada'],
            fecha_hora_inicio__gt=now
        ).order_by('fecha_hora_inicio')[:5]

        # Organizar citas por día para el calendario
        citas_por_dia = {}
        for cita in citas_mes:
            dia = cita.fecha_hora_inicio.day
            if dia not in citas_por_dia:
                citas_por_dia[dia] = []
            citas_por_dia[dia].append(cita)

        # Construir el calendario
        cal = []
        week = []

        # Días del mes anterior
        for i in range((first_day.weekday() + 1) % 7):
            week.append({'day': None, 'citas': []})

        # Días del mes actual
        for day in range(1, last_day.day + 1):
            week.append({
                'day': day,
                'citas': citas_por_dia.get(day, []),
                'hoy': day == today.day and month == today.month and year == today.year
            })

            if len(week) == 7:
                cal.append(week)
                week = []

        # Días del siguiente mes
        if week:
            while len(week) < 7:
                week.append({'day': None, 'citas': []})
            cal.append(week)

        context.update({
            'calendario': cal,
            'mes_actual': first_day.strftime('%B %Y'),
            'mes_anterior': (first_day - timedelta(days=1)).strftime('%Y-%m'),
            'mes_siguiente': (first_day + timedelta(days=31)).strftime('%Y-%m'),
            'hoy': today,
            'mes': month,
            'year': year,
            'profesor': self.profesor,
            'citas_hoy': citas_hoy,
            'citas_proximas': citas_proximas,
            'citas_pendientes': citas_pendientes,
            'now': now
        })

        return context


'''
class HistorialCitasView(ListView):
    template_name = 'profesores/citas/historial_citas.html'
    context_object_name = 'citas'
    paginate_by = 10  # Paginación de 10 citas por página

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('credenciales_profesor'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('profesores:login_profesor')

        try:
            self.profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        except Profesor.DoesNotExist:
            messages.error(request, 'Profesor no encontrado')
            return redirect('profesores:logout_profesor')

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Obtener todas las citas ordenadas por fecha descendente (más recientes primero)
        return Cita.objects.filter(
            profesor=self.profesor
        ).select_related('solicitante').order_by('-fecha_hora_inicio')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profesor'] = self.profesor

        # Estadísticas básicas
        context['total_citas'] = self.get_queryset().count()
        context['citas_pasadas'] = self.get_queryset().filter(fecha_hora_inicio__lt=timezone.now()).count()
        context['citas_futuras'] = self.get_queryset().filter(fecha_hora_inicio__gte=timezone.now()).count()

        return context

'''


class HistorialCitasView(ListView):
    template_name = 'profesores/citas/historial_citas.html'
    context_object_name = 'citas'
    paginate_by = 10  # Paginación de 10 citas por página

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('credenciales_profesor'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('profesores:login_profesor')

        try:
            self.profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        except Profesor.DoesNotExist:
            messages.error(request, 'Profesor no encontrado')
            return redirect('profesores:logout_profesor')

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Obtener ContentTypes necesarios
        profesor_ct = ContentType.objects.get_for_model(Profesor)
        padre_ct = ContentType.objects.get_for_model(Padre)
        servicio_ct = ContentType.objects.get_for_model(ServicioEscolar)

        # Filtro opcional por estado
        estado = self.request.GET.get('estado')

        # Base queryset que incluye tanto Cita como CitaPrioritaria
        base_queryset = Cita.objects.all()

        # Citas creadas por el profesor
        citas_creadas = base_queryset.filter(
            creador_tipo=profesor_ct,
            creador_id=self.profesor.id,
            profesor=self.profesor
        )

        # Citas solicitadas por padres (solicitante es un Padre) para este profesor
        citas_solicitadas_por_padres = Cita.objects.filter(
            profesor=self.profesor,
            solicitante__isnull=False
        ).filter(solicitante__in=Padre.objects.all())

        # Citas creadas por el Servicio Escolar
        citas_servicio_profesor = Cita.objects.filter(
            profesor=self.profesor,
            creador_tipo=servicio_ct
        )

        # Todas las citas asignadas al profesor, excluyendo las que él creó
        citas_asignadas = Cita.objects.filter(
            profesor=self.profesor
        ).exclude(creador_tipo=profesor_ct, creador_id=self.profesor.id)

        # Combinar
        citas = (citas_creadas | citas_solicitadas_por_padres |
                 citas_servicio_profesor | citas_asignadas)

        # Aplicar filtro de estado si existe
        if estado and estado in dict(Cita.ESTADOS):
            citas = citas.filter(estado=estado)

        return citas.order_by('-fecha_hora_inicio').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profesor'] = self.profesor
        context['filtro_estado'] = self.request.GET.get('estado')
        context['estados_cita'] = Cita.ESTADOS

        # Llama a get_queryset() sin paginación
        queryset = self.get_queryset()

        # Estadísticas
        context['total_citas'] = queryset.count()
        context['citas_pasadas'] = queryset.filter(fecha_hora_inicio__lt=timezone.now()).count()
        context['citas_futuras'] = queryset.filter(fecha_hora_inicio__gte=timezone.now()).count()

        # Citas prioritarias (lista completa)
        context['lista_citas_prioritarias'] = queryset.filter(
            citaprioritaria__isnull=False
        ).order_by('-fecha_hora_inicio')

        # ContentTypes
        profesor_ct = ContentType.objects.get_for_model(Profesor)
        padre_ct = ContentType.objects.get_for_model(Padre)

        context['citas_creadas_por_profesor'] = queryset.filter(
            creador_tipo=profesor_ct,
            creador_id=self.profesor.id
        )

        context['citas_solicitadas_por_padres'] = queryset.filter(
            solicitante__in=Padre.objects.all()
        )

        return context


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
        elif 'credenciales_servicio' in self.request.session:
            context['base_template'] = 'servicios_escolares/base.html'
        else:
            context['base_template'] = 'base_generico.html'  # Template por defecto

        return context


def panel_notificaciones_profesor(request):
    # Autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')

    # Obtener todas las notificaciones del profesor
    notificaciones = profesor.get_notificaciones()
    # Filtrar las no leídas manualmente porque son dicts
    notificaciones_no_leidas = [n for n in notificaciones if not n['is_read']]

    # Tomar las 5 más recientes (ya depende del orden en get_notificaciones)
    notificaciones_recientes = notificaciones[:5]

    # Contar no leídas
    contador_no_leidas = len(notificaciones_no_leidas)

    # Tipos de notificaciones para el filtro
    tipos_notificaciones = {
        'profesor_cita_creada': 'Nuevas citas',
        'profesor_cita_modificada': 'Cambios en citas',
        'profesor_cita_cancelada': 'Citas canceladas',
        'profesor_feedback_pendiente': 'Feedback pendiente',
        'profesor_cita_proxima': 'Recordatorios',
        'profesor_incidencia': 'Incidencias',
        'custom': 'Personalizadas',
    }

    # Filtrado por tipo si se especifica
    tipo_filtro = request.GET.get('tipo')
    if tipo_filtro and tipo_filtro in tipos_notificaciones:
        notificaciones = [n for n in notificaciones if n.get('event_type') == tipo_filtro]

    # Marcar como leídas si se recibe el parámetro
    if request.GET.get('marcar_leidas'):
        content_type = ContentType.objects.get_for_model(Profesor)
        Notification.objects.filter(
            recipient_ct=content_type,
            recipient_id=profesor.id,
            is_read=False
        ).update(is_read=True)
        messages.success(request, 'Todas las notificaciones marcadas como leídas')
        return redirect('profesores:panel_notificaciones')

    context = {
        'profesor': profesor,
        'notificaciones': notificaciones,
        'tipos_notificaciones': tipos_notificaciones,
        'tipo_filtro_actual': tipo_filtro,
        'notificaciones_no_leidas': profesor.notificaciones_no_leidas(),
        'notificaciones_recientes': notificaciones_recientes,
        'contador_no_leidas': contador_no_leidas,
    }

    return render(request, 'profesores/notificaciones/panel_notificaciones.html', context)


def marcar_notificacion_leida(request, notificacion_id):
    # Autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')

    try:
        notificacion = Notification.objects.get(
            id=notificacion_id,
            recipient_ct=ContentType.objects.get_for_model(Profesor),
            recipient_id=profesor.id
        )
        notificacion.mark_as_read()
        messages.success(request, 'Notificación marcada como leída')
    except Notification.DoesNotExist:
        messages.error(request, 'Notificación no encontrada')

    return redirect(request.META.get('HTTP_REFERER', 'profesores:dashboard_profesor'))


'''
class ReprogramarCitaProfesorView(FormView):
    template_name = 'profesores/citas/reprogramar_cita.html'
    form_class = ReprogramarCitaForm

    def dispatch(self, request, *args, **kwargs):
        # Verificar sesión del profesor
        credenciales = request.session.get('credenciales_profesor', {})
        if not credenciales.get('id'):
            messages.error(request, 'Debe iniciar sesión como profesor')
            return redirect('profesores:login_profesor')

        self.profesor = get_object_or_404(Profesor, id=credenciales['id'])
        self.cita = get_object_or_404(Cita, id=kwargs['cita_id'])

        # Verificar que el profesor es el destinatario de la cita
        if self.cita.profesor != self.profesor:
            messages.error(request, 'No tiene permiso para reprogramar esta cita')
            return redirect('profesores:dashboard_profesor')

        # Verificar que la cita puede ser reprogramada
        if self.cita.estado not in ['pendiente', 'confirmada']:
            messages.error(request, 'Solo se pueden reprogramar citas pendientes o confirmadas')
            return redirect('profesores:dashboard_profesor')

        # Validación: No permitir reprogramación si faltan menos de 60 minutos
        hora_minima_reprogramacion = self.cita.fecha_hora_inicio - timedelta(hours=1)
        if timezone.now() > hora_minima_reprogramacion:
            messages.error(
                request,
                f"No puede reprogramar esta cita porque falta menos de 1 hora para la misma. "
                f"Límite para reprogramar: {hora_minima_reprogramacion.strftime('%d/%m/%Y %H:%M')}"
            )
            return redirect('profesores:dashboard_profesor')

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cita'] = self.cita
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cita'] = self.cita
        context['profesor'] = self.profesor
        return context

    def form_valid(self, form):
        try:
            # Registrar la reprogramación antes de modificar la cita
            ReprogramacionCita.objects.create(
                cita_original=self.cita,
                fecha_hora_original=self.cita.fecha_hora_inicio,
                fecha_hora_nueva=form.cleaned_data['fecha_hora_inicio'],
                motivo=form.cleaned_data['motivo_reprogramacion'],
                realizado_por_tipo=ContentType.objects.get_for_model(self.profesor),
                realizado_por_id=self.profesor.id
            )

            # Actualizar la cita
            self.cita.fecha_hora_inicio = form.cleaned_data['fecha_hora_inicio']
            self.cita.duracion = form.cleaned_data['duracion']
            self.cita.fecha_hora_fin = self.cita.fecha_hora_inicio + timedelta(minutes=self.cita.duracion)
            self.cita.estado = 'reprogramada'
            self.cita.save()

            # Enviar notificaciones
            self._enviar_notificaciones()

            messages.success(self.request, '¡Cita reprogramada correctamente!')
            return redirect(self.get_success_url())

        except Exception as e:
            messages.error(self.request, f'Error al reprogramar la cita: {str(e)}')
            return redirect('profesores:reprogramar_cita', cita_id=self.cita.id)

    def get_success_url(self):
        return reverse('profesores:dashboard_profesor')

    def _enviar_notificaciones(self):
        # Notificación al profesor
        Notification.objects.create(
            sender_ct=ContentType.objects.get_for_model(self.profesor),
            sender_id=self.profesor.id,
            recipient_ct=ContentType.objects.get_for_model(self.profesor),
            recipient_id=self.profesor.id,
            event_type='profesor_cita_reprogramada',
            title=f'Cita reprogramada: {self.cita.titulo}',
            message=f"Has reprogramado tu cita para el {self.cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}",
            target_ct=ContentType.objects.get_for_model(self.cita),
            target_id=self.cita.id
        )

        # Notificación al padre
        Notification.objects.create(
            sender_ct=ContentType.objects.get_for_model(self.profesor),
            sender_id=self.profesor.id,
            recipient_ct=ContentType.objects.get_for_model(Padre),
            recipient_id=self.cita.solicitante.id,
            event_type='cita_reprogramada_por_profesor',
            title=f'Cita reprogramada por {self.profesor.nombre_completo}',
            message=f"La cita '{self.cita.titulo}' ha sido reprogramada para el {self.cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}. Motivo: {self.request.POST.get('motivo_reprogramacion', 'No especificado')}",
            target_ct=ContentType.objects.get_for_model(self.cita),
            target_id=self.cita.id
        )
        '''


class ReprogramarCitaProfesorView(FormView):
    template_name = 'profesores/citas/reprogramar_cita.html'
    form_class = ReprogramarCitaForm
    success_url = reverse_lazy('profesores:dashboard_profesor')

    def dispatch(self, request, *args, **kwargs):
        # Verificar sesión del profesor
        credenciales = request.session.get('credenciales_profesor', {})
        if not credenciales.get('id'):
            messages.error(request, 'Debe iniciar sesión como profesor')
            return redirect('profesores:login_profesor')

        self.profesor = get_object_or_404(Profesor, id=credenciales['id'])
        self.cita = get_object_or_404(Cita, id=kwargs['cita_id'])

        # Verificar que el profesor es el destinatario de la cita
        if self.cita.profesor != self.profesor:
            messages.error(request, 'No tiene permiso para reprogramar esta cita')
            return redirect('profesores:dashboard_profesor')

        # Verificar que la cita puede ser reprogramada
        # if self.cita.estado not in ['pendiente', 'confirmada', 'reprogramada']:
        if self.cita.estado not in ['pendiente', 'reprogramada']:
            messages.error(request, 'Solo se pueden reprogramar citas pendientes o reprogramadas')
            return redirect('profesores:dashboard_profesor')

        # Validación: No permitir reprogramación si faltan menos de 60 minutos
        hora_minima_reprogramacion = self.cita.fecha_hora_inicio - timedelta(hours=1)
        if timezone.now() > hora_minima_reprogramacion:
            messages.error(
                request,
                f"No puede reprogramar esta cita porque falta menos de 1 hora para la misma. "
                f"Límite para reprogramar: {hora_minima_reprogramacion.strftime('%d/%m/%Y %H:%M')}"
            )
            return redirect('profesores:dashboard_profesor')

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cita'] = self.cita
        kwargs['profesor'] = self.profesor
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cita'] = self.cita
        context['profesor'] = self.profesor
        return context

    def form_valid(self, form):
        try:
            # Registrar la reprogramación antes de modificar la cita
            ReprogramacionCita.objects.create(
                cita_original=self.cita,
                fecha_hora_original=self.cita.fecha_hora_inicio,
                fecha_hora_nueva=form.cleaned_data['fecha_hora_inicio'],
                motivo=form.cleaned_data['motivo_reprogramacion'],
                realizado_por_tipo=ContentType.objects.get_for_model(self.profesor),
                realizado_por_id=self.profesor.id
            )

            # Actualizar la cita
            self.cita.fecha_hora_inicio = form.cleaned_data['fecha_hora_inicio']
            self.cita.duracion = form.cleaned_data['duracion']
            self.cita.fecha_hora_fin = self.cita.fecha_hora_inicio + timedelta(minutes=self.cita.duracion)
            self.cita.estado = 'reprogramada'
            self.cita.save()

            # Enviar notificaciones
            self._enviar_notificaciones()

            messages.success(self.request, '¡Cita reprogramada correctamente!')
            return redirect(self.get_success_url())

        except Exception as e:
            logger.error(f"Error al reprogramar cita {self.cita.id}: {str(e)}", exc_info=True)
            messages.error(self.request, f'Error al reprogramar la cita: {str(e)}')
            return self.render_to_response(self.get_context_data(form=form))

    def _enviar_notificaciones(self):
        # Notificación al profesor
        Notification.objects.create(
            sender_ct=ContentType.objects.get_for_model(self.profesor),
            sender_id=self.profesor.id,
            recipient_ct=ContentType.objects.get_for_model(self.profesor),
            recipient_id=self.profesor.id,
            event_type='profesor_cita_reprogramada',
            title=f'Cita reprogramada: {self.cita.titulo}',
            message=f"Has reprogramado tu cita para el {self.cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}",
            target_ct=ContentType.objects.get_for_model(self.cita),
            target_id=self.cita.id
        )

        # Notificación al padre
        Notification.objects.create(
            sender_ct=ContentType.objects.get_for_model(self.profesor),
            sender_id=self.profesor.id,
            recipient_ct=ContentType.objects.get_for_model(Padre),
            recipient_id=self.cita.solicitante.id,
            event_type='cita_reprogramada_por_profesor',
            title=f'Cita reprogramada por {self.profesor.nombre_completo}',
            message=f"La cita '{self.cita.titulo}' ha sido reprogramada para el {self.cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}. Motivo: {self.request.POST.get('motivo_reprogramacion', 'No especificado')}",
            target_ct=ContentType.objects.get_for_model(self.cita),
            target_id=self.cita.id
        )


@require_POST
@transaction.atomic
def marcar_cita_como_completada(request, cita_id):
    """
    Vista para que un profesor marque una cita como completada
    y se asigne automáticamente la retroalimentación al padre.
    """
    # Validar sesión
    credenciales = request.session.get('credenciales_profesor')
    if not credenciales:
        messages.error(request, "Debes iniciar sesión.")
        return redirect('profesores:login_profesor')

    try:
        # Obtener al usuario autenticado y la cita correspondiente
        profesor = Profesor.objects.get(id=credenciales['id'])
        cita = get_object_or_404(Cita, id=cita_id)

        # Ejecutar la lógica de completar la cita con retroalimentación
        success, mensaje, retro_aplicada = profesor.marcar_cita_como_completada_con_retroalimentacion(cita)

        if not success:
            messages.error(request, mensaje)
        else:
            messages.success(request, "Cita marcada como completada y retroalimentación asignada al padre.")

        return redirect('profesores:dashboard_profesor')

    except Profesor.DoesNotExist:
        messages.error(request, "Usuario no válido. Inicia sesión nuevamente.")
        return redirect('profesores:login_profesor')

    except Exception as e:
        messages.error(request, f"Ocurrió un error inesperado: {str(e)}")
        transaction.set_rollback(True)
        return redirect('profesores:dashboard_profesor')


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


@requiere_profesor
def profesor_theme_settings(request):
    theme_config = ThemeConfig.objects.first()

    # Verificar si tiene permiso para cambiar tema
    if not theme_config or not theme_config.allow_profesors:
        messages.error(request, 'No tienes permiso para cambiar el tema')
        return redirect('profesores:configuracion_profesor')

    if request.method == 'POST':
        new_theme = request.POST.get('personal_theme')
        if new_theme in [choice[0] for choice in ThemeConfig.THEME_CHOICES]:
            request.user_obj.personal_theme = new_theme
            request.user_obj.save()
            messages.success(request, 'Tema personal actualizado')
        return redirect('profesores:theme_settings')

    return render(request, 'profesores/theme_settings.html', {
        'THEME_CHOICES': ThemeConfig.THEME_CHOICES,
        'current_theme': request.user_obj.personal_theme,
        'theme_config': theme_config  # <-- necesario para el bloque de vista previa
    })


@require_GET
@requiere_profesor
def api_eventos_profesor(request):
    print("===> Iniciando api_eventos_profesor")

    profesor = getattr(request, 'user_obj', None)
    eventos = []

    if profesor and profesor.__class__.__name__ == 'Profesor':
        print(f"[INFO] Profesor autenticado: {profesor}")

        profesor_ct = ContentType.objects.get_for_model(Profesor)
        print(f"[DEBUG] ContentType para Profesor: {profesor_ct}")

        estado_filtro = request.GET.get('estado')
        print(f"[INFO] Filtro de estado recibido: {estado_filtro}")

        citas_base = Cita.objects.filter(
            models.Q(profesor=profesor) |
            models.Q(asistentes_profesores=profesor)
        ).select_related(
            'solicitante', 'profesor', 'servicio_escolar'
        ).distinct()
        print(f"[DEBUG] Total citas base encontradas: {citas_base.count()}")

        citas_creadas = citas_base.filter(
            creador_tipo=profesor_ct,
            creador_id=profesor.id
        )
        print(f"[DEBUG] Citas creadas por el profesor: {citas_creadas.count()}")

        citas_solicitadas = citas_base.filter(
            profesor=profesor,
            solicitante__isnull=False
        ).exclude(creador_tipo=profesor_ct)
        print(f"[DEBUG] Citas solicitadas por otros: {citas_solicitadas.count()}")

        citas_prioritarias = CitaPrioritaria.objects.filter(
            models.Q(profesor=profesor) |
            models.Q(asistentes_profesores=profesor),
            fecha_hora_fin__gte=timezone.now()
        ).select_related(
            'solicitante', 'profesor', 'servicio_escolar'
        ).order_by('nivel_prioridad', '-fecha_hora_inicio')
        print(f"[DEBUG] Citas prioritarias encontradas: {citas_prioritarias.count()}")

        if estado_filtro and estado_filtro in dict(Cita.ESTADOS):
            citas_creadas = citas_creadas.filter(estado=estado_filtro)
            citas_solicitadas = citas_solicitadas.filter(estado=estado_filtro)
            citas_prioritarias = citas_prioritarias.filter(estado=estado_filtro)
            print(
                f"[INFO] Filtro aplicado. Nuevas cantidades: creadas={citas_creadas.count()}, solicitadas={citas_solicitadas.count()}, prioritarias={citas_prioritarias.count()}")

        todas_citas = list(citas_creadas) + list(citas_solicitadas) + list(citas_prioritarias)
        print(f"[DEBUG] Total citas combinadas (con duplicados): {len(todas_citas)}")

        citas_unicas = []
        ids_vistos = set()
        for cita in todas_citas:
            if cita.id not in ids_vistos:
                citas_unicas.append(cita)
                ids_vistos.add(cita.id)
        print(f"[INFO] Total citas únicas para mostrar: {len(citas_unicas)}")

        for cita in citas_unicas:
            es_prioritaria = isinstance(cita, CitaPrioritaria)

            evento = {
                'id': cita.id,
                'title': cita.titulo,
                'start': cita.fecha_hora_inicio.isoformat(),
                'end': cita.fecha_hora_fin.isoformat(),
                'backgroundColor': estado_color(cita.estado),
                'borderColor': estado_color(cita.estado),
                'textColor': 'white',
                'extendedProps': {
                    'estado': cita.get_estado_display(),
                    'tipo': cita.get_tipo_display(),
                    'descripcion': cita.motivo,
                    'ubicacion': cita.ubicacion,
                    'solicitante': str(cita.solicitante) if cita.solicitante else '',
                    'es_prioritaria': es_prioritaria,
                    'prioridad': getattr(cita, 'nivel_prioridad', None),
                    'creador': 'Tú' if cita.creador_id == profesor.id and cita.creador_tipo == profesor_ct else '',
                    'asistentes': [str(p) for p in cita.asistentes_profesores.all()] if hasattr(cita,
                                                                                                'asistentes_profesores') else []
                }
            }

            eventos.append(evento)
        print(f"[INFO] Total eventos generados para FullCalendar: {len(eventos)}")
    else:
        print("[WARNING] Usuario no es un profesor o no autenticado correctamente.")

    print("===> Finalizando api_eventos_profesor")
    return JsonResponse(eventos, safe=False)


def estado_color(estado):
    colores = {
        'pendiente': '#f1c40f',  # amarillo
        'confirmada': '#2ecc71',  # verde
        'completada': '#3498db',  # azul
        'cancelada': '#e74c3c',  # rojo
        'reprogramada': '#e67e22',  # naranja
    }
    return colores.get(estado, '#95a5a6')  # gris por defecto


@require_GET
def detalles_cita(request, cita_id):
    try:
        cita = Cita.objects.get(id=cita_id)
        data = {
            'success': True,
            'cita': {
                'titulo': cita.titulo,
                'tipo': cita.get_tipo_display(),
                'estado': cita.get_estado_display(),
                'fecha_hora_inicio': cita.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M'),
                'duracion': cita.duracion,
                'ubicacion': cita.ubicacion,
                'motivo': cita.motivo,
                'observaciones': cita.observaciones,
                'solicitante': str(cita.solicitante),
                'profesor': str(cita.profesor) if cita.profesor else None,
                'servicio_escolar': str(cita.servicio_escolar) if cita.servicio_escolar else None,
            },
            'estudiantes': [str(e) for e in cita.estudiantes.all()]
        }
        return JsonResponse(data)
    except Cita.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'La cita no existe o no tienes permiso para verla'
        }, status=404)
