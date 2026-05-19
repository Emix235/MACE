from datetime import timezone, datetime, time
import logging
import re
import re
from datetime import datetime, timedelta
import pytz
from django.http import JsonResponse
from django.utils import timezone
from django.apps import apps
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, UpdateView, FormView, TemplateView
from django.db import models, IntegrityError, transaction  # Para models.Q
from citas.models import Cita, CitaPrioritaria, ReprogramacionCita  # Para el modelo Cita
from estudiantes.models import Estudiante, CicloEscolar
from formularios.models import EncuestaAplicada, Respuesta, RetroalimentacionAplicada
from notificaciones.utils import notificar_registro_padre
from profesores.models import Profesor, Clase, HorarioClase
from servicios_escolares.models import ServicioEscolar, ThemeConfig
from ticket_soporte.models import TicketSoporte
from .models import Padre
from .forms import RegistroPadreForm, LoginPadreForm, EditarPerfilPadreForm, ReprogramarCitaForm
from django.utils.timezone import now, localtime, is_naive
from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth.hashers import check_password, make_password
from .forms import CitaForm
from profesores.models import TiempoLibreProfesor
from django.views.generic import ListView
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from notificaciones.models import Notification
from django.contrib.contenttypes.models import ContentType
from datetime import datetime, timedelta
from django.db.models import Prefetch, Q
from profesores.models import TiempoLibreProfesor, HorarioClase


def registro_padre_view(request):
    if request.method == 'POST':
        form = RegistroPadreForm(request.POST, request.FILES)
        if form.is_valid():
            padre = form.save(commit=False)
            padre.contraseña = make_password(form.cleaned_data['contraseña'])
            padre.fecha_registro = now().date()
            padre.estado_cuenta = "Activo"
            padre.save()
            messages.success(request, '¡Registro exitoso! Por favor inicia sesión.')
            return redirect('padres:login_padre')
    else:
        form = RegistroPadreForm()
    return render(request, 'padres/registro.html', {'form': form})


'''
    for message in storage:
        if hasattr(message, 'extra_tags') and message.extra_tags and 'logout_message' in message.extra_tags:
            logout_message = message
        else:
            messages.add_message(request, message.level, message.message,
                                 extra_tags=message.extra_tags if hasattr(message, 'extra_tags') else '')
    storage.used = True
'''


def login_padre_view(request):
    # Verificar si el padre ya está logueado
    if request.session.get('credenciales_padre'):
        return redirect('padres:dashboard_padre')

    # Limpiar mensajes existentes o manejarlos de forma más simple
    storage = messages.get_messages(request)
    for message in storage:
        # Los mensajes se marcan como usados al iterar, así que no los vuelvas a agregar
        pass

    if request.method == 'POST':
        form = LoginPadreForm(request.POST)
        if form.is_valid():
            correo = form.cleaned_data['correo_electronico']
            try:
                padre = Padre.objects.get(correo_electronico=correo)

                if not check_password(form.cleaned_data['contraseña'], padre.contraseña):
                    form.add_error('contraseña', 'Credenciales incorrectas')
                    return render(request, 'padres/login.html', {'form': form})

                # Guardar credenciales en sesión
                request.session['credenciales_padre'] = {
                    'id': padre.id,
                    'hash_credencial': f"{padre.correo_electronico}-{padre.ultima_fecha_sesion}".encode('utf-8').hex(),
                    'rol': padre.rol_usuario
                }

                request.session['ultima_actividad'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')

                padre.ultima_fecha_sesion = timezone.now().date()
                padre.save()

                messages.success(
                    request,
                    f'Bienvenido {padre.nombre_completo}',
                    extra_tags='login_message'
                )
                return redirect('padres:dashboard_padre')
            except Padre.DoesNotExist:
                form.add_error('correo_electronico', 'Credenciales incorrectas')
    else:
        form = LoginPadreForm()

    return render(request, 'padres/login.html', {'form': form})


def logout_padre_view(request):
    try:
        # Eliminar credenciales de la sesión de manera segura
        if 'credenciales_padre' in request.session:
            del request.session['credenciales_padre']

        # Eliminar última actividad si existe
        request.session.pop('ultima_actividad', None)

        # Limpiar toda la sesión
        request.session.flush()

        messages.success(request, 'Has cerrado sesión correctamente.', extra_tags='logout_message')
    except Exception as e:
        logger.error(f"Error al cerrar sesión: {str(e)}")
        messages.error(request, 'Ocurrió un error al cerrar sesión.')

    return redirect('padres:login_padre')


def dashboard_padre_view(request):
    if not request.session.get('credenciales_padre'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    try:
        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
        estudiantes = Estudiante.objects.filter(padre=padre)
        notificaciones_no_leidas = padre.notificaciones_no_leidas()

        # Obtenemos los content types relevantes
        padre_ct = ContentType.objects.get_for_model(Padre)
        profesor_ct = ContentType.objects.get_for_model(Profesor)
        servicio_ct = ContentType.objects.get_for_model(ServicioEscolar)

        # Filtro por estado si viene en la request
        estado = request.GET.get('estado')

        now = timezone.now()

        # 1. Citas creadas directamente por el padre
        citas_creadas = Cita.objects.filter(
            creador_tipo=padre_ct,
            creador_id=padre.id,
            fecha_hora_inicio__gte=now
        )

        # 2. Citas donde el padre es el solicitante (pueden ser diferentes de las creadas)
        citas_como_solicitante = Cita.objects.filter(
            solicitante=padre,
            fecha_hora_inicio__gte=now
        ).exclude(
            creador_tipo=padre_ct, creador_id=padre.id
        )

        # 3. Citas donde el padre está como asistente
        citas_como_asistente = Cita.objects.filter(
            asistentes_padres=padre,
            fecha_hora_inicio__gte=now
        ).exclude(
            Q(creador_tipo=padre_ct, creador_id=padre.id) | Q(solicitante=padre)
        )

        # 4. Citas creadas por profesores donde el padre es asistente
        citas_de_profesores = Cita.objects.filter(
            solicitante=padre,
            creador_tipo=profesor_ct,
            fecha_hora_inicio__gte=now
        )

        # 5. Citas creadas por servicios escolares donde el padre es asistente
        citas_de_servicios = Cita.objects.filter(
            creador_tipo=servicio_ct,
            solicitante=padre,
            fecha_hora_inicio__gte=now
        )

        # Verificar encuesta pendiente
        encuesta_pendiente = False
        encuesta_aplicada = EncuestaAplicada.objects.filter(activa=True).first()

        if encuesta_aplicada:
            encuesta_pendiente = not Respuesta.objects.filter(
                encuesta_aplicada=encuesta_aplicada,
                padre=padre
            ).exists()

        # Aplicar filtro de estado si existe
        if estado and estado in dict(Cita.ESTADOS):
            citas_creadas = citas_creadas.filter(estado=estado)
            citas_como_solicitante = citas_como_solicitante.filter(estado=estado)
            citas_como_asistente = citas_como_asistente.filter(estado=estado)
            citas_de_profesores = citas_de_profesores.filter(estado=estado)
            citas_de_servicios = citas_de_servicios.filter(estado=estado)
        else:
            # Por defecto solo mostramos pendientes en el dashboard
            citas_creadas = citas_creadas.filter(estado='pendiente')
            citas_como_solicitante = citas_como_solicitante.filter(estado='pendiente')
            citas_como_asistente = citas_como_asistente.filter(estado='pendiente')
            citas_de_profesores = citas_de_profesores.filter(estado='pendiente')
            citas_de_servicios = citas_de_servicios.filter(estado='pendiente')

        try:
            citas_prioritarias = CitaPrioritaria.objects.filter(
                (
                        models.Q(solicitante=padre) |
                        models.Q(estudiantes__padre=padre)
                ) &
                models.Q(estado__in=['pendiente', 'confirmada', 'reprogramada']) &
                models.Q(fecha_hora_inicio__gte=timezone.now())
            ).distinct().order_by('nivel_prioridad', 'fecha_hora_inicio')

            citas_prioritarias_dict = {cita.id: cita for cita in citas_prioritarias}

        except Exception as e:
            logger.error(f"Error al obtener citas prioritarias: {str(e)}")
            citas_prioritarias_dict = {}

        # Obtener retroalimentación pendiente más reciente
        retro_pendiente = RetroalimentacionAplicada.objects.filter(
            cita__solicitante=padre,
            completada=False,
            cita__estado='completada'
        ).order_by('-fecha_aplicacion').first()

        horarios_clases = HorarioClase.objects.filter(
            clase__grupo__estudiantes__in=estudiantes
        ).select_related('clase__profesor', 'clase__grupo').order_by('dia_semana', 'hora_inicio')

        descansos_profesores = TiempoLibreProfesor.objects.filter(
            profesor__clases__grupo__estudiantes__in=estudiantes
        ).select_related('profesor').order_by('dia_semana', 'hora_inicio')

        horarios_por_dia = {i: [] for i in range(1, 7)}
        descansos_por_dia = {i: [] for i in range(1, 7)}

        for horario in horarios_clases:
            horarios_por_dia[horario.dia_semana].append(horario)
        for descanso in descansos_profesores:
            descansos_por_dia[descanso.dia_semana].append(descanso)

        now = timezone.localtime(timezone.now())
        start_week = now - timedelta(days=now.weekday())
        week_days = [start_week + timedelta(days=i) for i in range(6)]

        context = {
            'padre': padre,
            'retro_pendiente': retro_pendiente,
            'week_days': week_days,
            'horarios_por_dia': horarios_por_dia,
            'descansos_por_dia': descansos_por_dia,
            'current_date': now.date(),
            'horas': [f"{h:02d}:00" for h in range(7, 19)],
            'active_tab': request.GET.get('tab', 'clases'),
            'notificaciones_no_leidas': notificaciones_no_leidas.count(),
            'notificaciones': padre.get_notificaciones(), '''[:5] sin limites'''
            'citas_creadas': citas_creadas.order_by('-fecha_hora_inicio'),
            'citas_como_solicitante': citas_como_solicitante.order_by('-fecha_hora_inicio'),
            'citas_como_asistente': citas_como_asistente.order_by('-fecha_hora_inicio'),
            'citas_de_profesores': citas_de_profesores.order_by('-fecha_hora_inicio'),
            'citas_de_servicios': citas_de_servicios.order_by('-fecha_hora_inicio'),
            'citas_prioritarias': citas_prioritarias_dict,
            'encuesta_pendiente': encuesta_pendiente,
            'encuesta_url': reverse('formularios:contestar_encuesta') if encuesta_pendiente else None
        }
        return render(request, 'padres/index.html', context)

    except Padre.DoesNotExist:
        messages.error(request, 'Cuenta no encontrada')
        return redirect('padres:logout_padre')


def configuracion_padre_view(request):
    # Verificar autenticación
    if not request.session.get('credenciales_padre'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    try:
        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
    except Padre.DoesNotExist:
        messages.error(request, 'Padre no encontrado')
        return redirect('padres:logout_padre')

    return render(request, 'padres/configuracion.html', {
        'padre': padre
    })


def editar_perfil_padre_view(request):
    # Verificar autenticación
    if not request.session.get('credenciales_padre'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    try:
        # Obtener el padre actual
        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
    except Padre.DoesNotExist:
        messages.error(request, 'Padre no encontrado')
        return redirect('padres:logout_padre')
    except Exception as e:
        messages.error(request, f'Error al obtener perfil: {str(e)}')
        return redirect('padres:configuracion_padre')

    if request.method == 'POST':
        form = EditarPerfilPadreForm(request.POST, request.FILES, instance=padre)

        print("\n=== Datos del formulario ===")
        print("POST:", request.POST)
        print("FILES:", request.FILES)

        if form.is_valid():
            try:
                padre = form.save(commit=False)

                nueva_contraseña = form.cleaned_data.get('nueva_contraseña')
                if nueva_contraseña:
                    padre.contraseña = make_password(nueva_contraseña)
                    print("Contraseña actualizada")

                padre.save()

                print("\n=== Después de guardar ===")
                print("Nombre:", padre.nombre_completo)
                print("Email:", padre.correo_electronico)
                print("Teléfono:", padre.telefono_principal)
                if padre.imagen_usuario:
                    print("Imagen:", padre.imagen_usuario.url)

                messages.success(request, 'Perfil actualizado correctamente')
                return redirect('padres:dashboard_padre')

            except Exception as e:
                messages.error(request, f'Error al guardar los cambios: {str(e)}')
                print("Error al guardar:", str(e))
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario')
            print("\n=== Errores del formulario ===")
            for field, errors in form.errors.items():
                print(f"Campo {field}: {', '.join(errors)}")
    else:
        form = EditarPerfilPadreForm(instance=padre)

    return render(request, 'padres/editar_perfil.html', {
        'form': form,
        'padre': padre
    })


def registro_padre_personalizado(request, estudiante_id=None):
    estudiante = get_object_or_404(Estudiante, pk=estudiante_id) if estudiante_id else None

    if request.method == 'POST':
        form = RegistroPadreForm(request.POST, request.FILES)
        if form.is_valid():
            padre = form.save(commit=False)
            padre.contraseña = make_password(form.cleaned_data['contraseña'])
            padre.fecha_registro = now().date()
            padre.estado_cuenta = "Activo"
            padre.save()

            # Vincular al padre con el estudiante si se proporcionó ID
            if estudiante:
                estudiante.padre = padre
                estudiante.save()

            messages.success(request, '¡Registro exitoso! Por favor inicia sesión.')
            return redirect('padres:login_padre')
    else:
        form = RegistroPadreForm()

    return render(request, 'padres/registro.html', {
        'form': form,
        'estudiante': estudiante
    })


def registro_padre_token(request, token):
    estudiante = get_object_or_404(Estudiante, registro_token=token)

    if request.method == 'POST':
        form = RegistroPadreForm(request.POST, request.FILES)
        if form.is_valid():
            padre = form.save(commit=False)
            padre.contraseña = make_password(form.cleaned_data['contraseña'])
            padre.rol_usuario = 'Padre'
            padre.estado_cuenta = 'Activo'
            padre.fecha_registro = now().date()
            padre.save()

            # Vincular automáticamente
            estudiante.padre = padre
            estudiante.save()

            # Notificar a servicios escolares
            notificar_registro_padre(padre, estudiante)

            messages.success(request, '¡Registro exitoso! Ahora puedes iniciar sesión.')
            return redirect('padres:login_padre')
    else:
        form = RegistroPadreForm()

    return render(request, 'padres/registro_token.html', {
        'form': form,
        'estudiante': estudiante,
        'titulo': f'Registro para padre de {estudiante.nombre_completo}'
    })


def panel_estudiante(request):
    # Verificar autenticación
    if not request.session.get('credenciales_padre'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    try:
        # Obtener el padre desde la sesión (esto ya es suficiente)
        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
    except Padre.DoesNotExist:
        messages.error(request, 'Padre no encontrado')
        return redirect('padres:logout_padre')
    except KeyError:
        messages.error(request, 'Sesión inválida')
        return redirect('padres:login_padre')

    # Obtener todos los estudiantes asociados a este padre
    hijos = Estudiante.objects.filter(padre=padre).select_related('grupo_actual', 'ciclo_inscripcion')

    return render(request, 'padres/panel_estudiantes.html', {
        'padre': padre,
        'hijos': hijos
    })


def detalles_estudiante(request, estudiante_id):
    # Verificar autenticación
    if not request.session.get('credenciales_padre'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    try:
        # Obtener el padre desde la sesión
        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
    except (Padre.DoesNotExist, KeyError):
        messages.error(request, 'Sesión inválida o padre no encontrado')
        return redirect('padres:login_padre')

    # Solo permitir acceso si el estudiante está asociado al padre
    estudiante = get_object_or_404(
        Estudiante,
        id=estudiante_id,
        padre=padre  # Usamos el objeto padre obtenido de la sesión
    )

    return render(request, 'padres/detalles_estudiante.html', {
        'estudiante': estudiante,
        'padre': padre 
    })


def profesores_disponibles(request):
    try:
        # Obtener el padre desde la sesión
        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
    except Padre.DoesNotExist:
        messages.error(request, 'Padre no encontrado')
        return redirect('padres:logout_padre')
    except KeyError:
        messages.error(request, 'Sesión inválida')
        return redirect('padres:login_padre')

    # Obtener estudiantes del padre con grupo asignado, ordenados por grado y grupo
    estudiantes = Estudiante.objects.filter(
        padre=padre,
        grupo_actual__isnull=False
    ).select_related(
        'grupo_actual',
        'grupo_actual__grado',
        'grupo_actual__grado__nivel'
    ).order_by(
        'grupo_actual__grado__nivel__orden',
        'grupo_actual__grado__numero',
        'grupo_actual__letra'
    )

    # Obtener IDs de grupos únicos
    grupos_ids = estudiantes.values_list('grupo_actual__id', flat=True).distinct()

    # Obtener profesores que enseñan en esos grupos, ordenados por grado y grupo
    profesores = Profesor.objects.filter(
        clases__grupo__id__in=grupos_ids
    ).distinct().prefetch_related(
        Prefetch('clases', queryset=Clase.objects.filter(
            grupo__id__in=grupos_ids
        ).select_related(
            'grupo',
            'grupo__grado',
            'grupo__grado__nivel'
        ).order_by(
            'grupo__grado__nivel__orden',
            'grupo__grado__numero',
            'grupo__letra'
        ))
    ).order_by('nombre_completo')

    # Obtener servicio escolar
    servicio_escolar = ServicioEscolar.objects.filter(
        estado_cuenta='Activo',
        estado_disponibilidad='Disponible'
    ).first()

    # Obtener nombres de grupos para mostrar en el template
    grupos_estudiantes = estudiantes.values_list(
        'grupo_actual__grado__numero',
        'grupo_actual__letra'
    ).distinct()

    return render(request, 'padres/citas/profesores_disponibles.html', {
        'profesores': profesores,
        'estudiantes': estudiantes,
        'padre': padre,
        'servicio_escolar': servicio_escolar,
        'grupos_estudiantes': grupos_estudiantes
    })


def debug_session(request):
    return JsonResponse({
        'session_keys': list(request.session.keys()),
        'credenciales_padre': request.session.get('credenciales_padre'),
        'user': str(request.user),
        'is_authenticated': request.user.is_authenticated
    })


logger = logging.getLogger(__name__)


# LA ORIGINAL PERO YA NO ES PARTE DEL PROCESO
class CrearCitaView(CreateView):
    model = Cita
    form_class = CitaForm
    template_name = 'padres/citas/crear_cita.html'
    success_url = reverse_lazy('padres:mis_citas')

    def dispatch(self, request, *args, **kwargs):
        """Determina si es cita con profesor o servicio escolar"""
        try:
            # Obtener padre desde sesión
            credenciales = request.session.get('credenciales_padre', {})
            if not credenciales.get('id'):
                messages.error(request, 'Debe iniciar sesión como padre')
                return redirect('padres:inicio')

            self.padre = Padre.objects.get(id=credenciales['id'])

            # Configurar tipo de cita
            if 'profesor_id' in kwargs:
                self.profesor = Profesor.objects.get(id=kwargs['profesor_id'])
                self.servicio_escolar = None
                self.tipo_cita = 'profesor'
            elif 'servicio_escolar_id' in kwargs:
                self.profesor = None
                self.servicio_escolar = ServicioEscolar.objects.get(
                    id=kwargs['servicio_escolar_id'],
                    estado_cuenta='Activo',
                    estado_disponibilidad='Disponible'
                )
                self.tipo_cita = 'servicio_escolar'
            else:
                messages.error(request, 'Destino de la cita no especificado')
                return redirect('padres:inicio')

            return super().dispatch(request, *args, **kwargs)

        except (Padre.DoesNotExist, Profesor.DoesNotExist, ServicioEscolar.DoesNotExist) as e:
            logger.error(f"Error en dispatch de CrearCitaView: {str(e)}")
            messages.error(request, 'No se pudo identificar el destinatario')
            return redirect('padres:inicio')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'padre': self.padre,
            'profesor': self.profesor,
            'servicio_escolar': self.servicio_escolar,
            'estudiantes_queryset': Estudiante.objects.filter(
                padre=self.padre,
                grupo_actual__isnull=False
            ).select_related('grupo_actual')
        })
        return kwargs

    def form_valid(self, form):
        try:
            cita = form.save(commit=False)

            # Configuración base
            cita.solicitante = self.padre
            cita.creador_tipo = ContentType.objects.get_for_model(self.padre)
            cita.creador_id = self.padre.id
            cita.estado = 'pendiente'

            # Configurar destinatario principal
            if self.tipo_cita == 'profesor':
                cita.profesor = self.profesor
                if form.cleaned_data.get('incluir_servicio_escolar'):
                    servicio = ServicioEscolar.objects.filter(
                        estado_cuenta='Activo',
                        estado_disponibilidad='Disponible'
                    ).first()
                    if servicio:
                        cita.servicio_escolar = servicio
            else:
                cita.servicio_escolar = self.servicio_escolar

            # Calcular fecha de fin
            cita.fecha_hora_fin = cita.fecha_hora_inicio + timedelta(minutes=cita.duracion)

            # Guardar cita y relaciones many-to-many
            cita.save()
            form.save_m2m()  # Guarda los estudiantes seleccionados

            # Registrar participantes
            self._registrar_participantes(cita)

            # Enviar notificaciones
            self._enviar_notificaciones(cita)

            messages.success(self.request, '¡Cita agendada correctamente!')
            return super().form_valid(form)

        except Exception as e:
            logger.error(f"Error al crear cita: {str(e)}", exc_info=True)
            messages.error(self.request, 'Ocurrió un error al agendar la cita')
            return self.form_invalid(form)

    def _registrar_participantes(self, cita):
        """Registra todos los participantes de la cita"""
        cita.asistentes_padres.add(self.padre)

        if cita.profesor:
            cita.asistentes_profesores.add(cita.profesor)
        if cita.servicio_escolar:
            cita.asistentes_servicio.add(cita.servicio_escolar)

    def _enviar_notificaciones(self, cita):
        """Envía notificaciones a los involucrados"""
        estudiantes = ", ".join([e.nombre_completo() for e in cita.estudiantes.all()])
        fecha = cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')

        # Notificación al padre
        Notification.objects.create(
            usuario=self.padre.usuario,
            mensaje=f"Cita agendada para el {fecha} sobre: {estudiantes}",
            relacion_contenido=ContentType.objects.get_for_model(cita),
            relacion_id=cita.id,
            tipo='cita_agendada'
        )

        # Notificación al profesor (si aplica)
        if cita.profesor:
            Notification.objects.create(
                usuario=cita.profesor.usuario,
                mensaje=f"Nueva cita con {self.padre.nombre_completo} el {fecha}",
                relacion_contenido=ContentType.objects.get_for_model(cita),
                relacion_id=cita.id,
                tipo='cita_asignada'
            )

        # Notificación a servicio escolar (si aplica)
        if cita.servicio_escolar:
            Notification.objects.create(
                usuario=cita.servicio_escolar.usuario,
                mensaje=f"Incluido en cita el {fecha} con {self.padre.nombre_completo}",
                relacion_contenido=ContentType.objects.get_for_model(cita),
                relacion_id=cita.id,
                tipo='cita_asignada'
            )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Horarios ocupados para citas con profesor
        if self.tipo_cita == 'profesor':
            context['horarios_ocupados'] = [
                {'start': c.fecha_hora_inicio.isoformat(),
                 'end': c.fecha_hora_fin.isoformat()}
                for c in Cita.objects.filter(
                    profesor=self.profesor,
                    fecha_hora_inicio__gte=timezone.now()
                )[:50]  # Limitar a 50 citas futuras
            ]

        context.update({
            'tipo_cita': self.tipo_cita,
            'profesor': self.profesor,
            'servicio_escolar': self.servicio_escolar
        })
        return context


# PARA AGENDAR CITA CON EL PROFESOR
class CrearCitaProfesorView(CreateView):
    model = Cita
    form_class = CitaForm
    template_name = 'padres/citas/crear_cita.html'
    success_url = reverse_lazy('padres:mis_citas')

    def dispatch(self, request, *args, **kwargs):
        print("Iniciando dispatch...")
        try:
            # Verificar sesión del padre
            credenciales = request.session.get('credenciales_padre', {})
            print(f"Credenciales obtenidas: {credenciales}")
            if not credenciales.get('id'):
                messages.error(request, 'Debe iniciar sesión como padre')
                return redirect('padres:inicio')

            self.padre = Padre.objects.get(id=credenciales['id'])
            self.profesor = Profesor.objects.get(id=kwargs['profesor_id'])

            print(f"Padre: {self.padre}, Profesor: {self.profesor}")

            return super().dispatch(request, *args, **kwargs)

        except (Padre.DoesNotExist, Profesor.DoesNotExist) as e:
            print(f"Error en dispatch de CrearCitaProfesorView: {str(e)}")
            messages.error(request, 'No se pudo identificar el profesor')
            return redirect('padres:inicio')

    def get_form_kwargs(self):
        print("Obteniendo kwargs para el formulario...")
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'padre': self.padre,
            'profesor': self.profesor,
            'estudiantes_queryset': Estudiante.objects.filter(
                padre=self.padre,
                grupo_actual__isnull=False
            ).select_related('grupo_actual')
        })
        print(f"Form kwargs actualizados: {kwargs}")
        return kwargs

    def form_valid(self, form):
        print("Formulario válido, guardando cita...")
        try:
            cita = form.save(commit=False)
            cita.solicitante = self.padre
            cita.creador_tipo = ContentType.objects.get_for_model(self.padre)
            cita.creador_id = self.padre.id
            cita.estado = 'pendiente'
            cita.profesor = self.profesor

            # Opción para incluir servicio escolar
            if form.cleaned_data.get('incluir_servicio_escolar'):
                servicio = ServicioEscolar.objects.filter(
                    estado_cuenta='Activo',
                    estado_disponibilidad='Disponible'
                ).first()
                if servicio:
                    cita.servicio_escolar = servicio
                    print(f"Servicio escolar asignado: {servicio}")

            cita.fecha_hora_fin = cita.fecha_hora_inicio + timedelta(minutes=cita.duracion)
            cita.save()
            form.save_m2m()

            self._registrar_participantes(cita)
            self._enviar_notificaciones(cita)

            messages.success(self.request, '¡Cita con profesor agendada correctamente!')
            print("Cita agendada correctamente")
            return super().form_valid(form)

        except Exception as e:
            print(f"Error al crear cita con profesor: {str(e)}")
            messages.error(self.request, 'Ocurrió un error al agendar la cita')
            return self.form_invalid(form)

    def _registrar_participantes(self, cita):
        print(f"Registrando participantes para la cita {cita.id}...")
        cita.asistentes_padres.add(self.padre)
        cita.asistentes_profesores.add(cita.profesor)
        if cita.servicio_escolar:
            cita.asistentes_servicio.add(cita.servicio_escolar)
        print(f"Participantes registrados: Padres, Profesores, Servicio Escolar (si aplica)")

    def _enviar_notificaciones(self, cita):
        print(f"Enviando notificaciones para la cita {cita.id}...")
        estudiantes = ", ".join([e.nombre_completo() for e in cita.estudiantes.all()])
        fecha = cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')

        # Notificación para el padre
        if self.padre.user:  # Cambiado de 'usuario' a 'user'
            Notification.objects.create(
                usuario=self.padre.user,  # Cambiado aquí
                mensaje=f"Cita con profesor agendada para el {fecha} sobre: {estudiantes}",
                relacion_contenido=ContentType.objects.get_for_model(cita),
                relacion_id=cita.id,
                tipo='cita_agendada'
            )

        # Notificación para el profesor
        if hasattr(cita.profesor, 'user'):  # Asumiendo que Profesor también usa 'user'
            Notification.objects.create(
                usuario=cita.profesor.user,  # Cambiado aquí
                mensaje=f"Nueva cita con {self.padre.nombre_completo} el {fecha}",
                relacion_contenido=ContentType.objects.get_for_model(cita),
                relacion_id=cita.id,
                tipo='cita_asignada'
            )

        # Notificación para servicio escolar (si aplica)
        if cita.servicio_escolar and hasattr(cita.servicio_escolar, 'user'):
            Notification.objects.create(
                usuario=cita.servicio_escolar.user,  # Cambiado aquí
                mensaje=f"Incluido en cita con profesor el {fecha}",
                relacion_contenido=ContentType.objects.get_for_model(cita),
                relacion_id=cita.id,
                tipo='cita_asignada'
            )

        print(f"Notificaciones enviadas para la cita {cita.id}")

    def get_context_data(self, **kwargs):
        print("Obteniendo contexto de la vista...")
        context = super().get_context_data(**kwargs)
        context['horarios_ocupados'] = [
            {'start': c.fecha_hora_inicio.isoformat(),
             'end': c.fecha_hora_fin.isoformat()}
            for c in Cita.objects.filter(
                profesor=self.profesor,
                fecha_hora_inicio__gte=timezone.now()
            )[:50]
        ]
        context['profesor'] = self.profesor
        print(f"Contexto actualizado: {context}")
        return context


# PARA AGENDAR CITA CON EL SERVICIO ESCOLAR
class CrearCitaServicioView(CreateView):
    model = Cita
    form_class = CitaForm
    template_name = 'padres/citas/crear_cita.html'
    success_url = reverse_lazy('padres:mis_citas')

    def dispatch(self, request, *args, **kwargs):
        try:
            # Verificar sesión del padre
            credenciales = request.session.get('credenciales_padre', {})
            if not credenciales.get('id'):
                messages.error(request, 'Debe iniciar sesión como padre')
                return redirect('padres:login_padre')

            self.padre = Padre.objects.get(id=credenciales['id'])
            self.servicio_escolar = ServicioEscolar.objects.get(
                id=kwargs['servicio_id'],
                estado_cuenta='Activo',
                estado_disponibilidad='Disponible'
            )

            return super().dispatch(request, *args, **kwargs)

        except Padre.DoesNotExist:
            logger.error("Padre no encontrado en la base de datos")
            messages.error(request, 'No se pudo identificar su cuenta de padre')
            return redirect('padres:inicio')

        except ServicioEscolar.DoesNotExist:
            logger.error(f"Servicio escolar no disponible (ID: {kwargs.get('servicio_id')})")
            messages.error(request, 'El servicio escolar seleccionado no está disponible')
            return redirect('padres:servicio_escolar')

        except Exception as e:
            logger.error(f"Error inesperado en dispatch: {str(e)}", exc_info=True)
            messages.error(request, 'Error inesperado al iniciar la solicitud')
            return redirect('padres:inicio')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        try:
            estudiantes = Estudiante.objects.filter(
                padre=self.padre,
                grupo_actual__isnull=False
            ).select_related('grupo_actual')

            if not estudiantes.exists():
                messages.warning(self.request, 'No tienes estudiantes disponibles para agendar citas')

            kwargs.update({
                'padre': self.padre,
                'servicio_escolar': self.servicio_escolar,
                'estudiantes_queryset': estudiantes
            })
            return kwargs

        except Exception as e:
            logger.error(f"Error en get_form_kwargs: {str(e)}", exc_info=True)
            messages.error(self.request, 'Error al preparar el formulario')
            raise

    def form_valid(self, form):
        try:
            cita = form.save(commit=False)

            # Configuración básica
            cita.solicitante = self.padre
            cita.creador_tipo = ContentType.objects.get_for_model(self.padre)
            cita.creador_id = self.padre.id
            cita.estado = 'pendiente'
            cita.servicio_escolar = self.servicio_escolar
            cita.tipo = 'administrativa'
            cita.fecha_hora_fin = cita.fecha_hora_inicio + timedelta(minutes=cita.duracion)

            # Guardar cita
            cita.save()
            form.save_m2m()

            # Registrar participantes y notificaciones
            self._registrar_participantes(cita)
            self._enviar_notificaciones(cita)

            messages.success(self.request, '¡Cita con servicio escolar agendada correctamente!')
            return super().form_valid(form)

        except IntegrityError as e:
            logger.error(f"Error de integridad: {str(e)}", exc_info=True)
            messages.error(self.request, 'Error: Datos inconsistentes en la solicitud')
            return self.form_invalid(form)

        except ValidationError as e:
            logger.error(f"Error de validación: {str(e)}", exc_info=True)
            messages.error(self.request, f'Error en los datos: {str(e)}')
            return self.form_invalid(form)

        except Exception as e:
            logger.error(f"Error inesperado: {str(e)}", exc_info=True)
            messages.error(self.request, 'Error técnico al agendar la cita')
            return self.form_invalid(form)

    def _registrar_participantes(self, cita):
        try:
            cita.asistentes_padres.add(self.padre)
            cita.asistentes_servicio.add(cita.servicio_escolar)
        except Exception as e:
            logger.error(f"Error al registrar participantes: {str(e)}", exc_info=True)
            raise

    def _enviar_notificaciones(self, cita):
        try:
            estudiantes = ", ".join([e.nombre_completo() for e in cita.estudiantes.all()])
            fecha = cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')

            # Obtener ContentTypes
            padre_ct = ContentType.objects.get_for_model(self.padre)
            servicio_ct = ContentType.objects.get_for_model(self.servicio_escolar)
            cita_ct = ContentType.objects.get_for_model(cita)

            # Notificación al padre
            Notification.objects.create(
                sender_ct=servicio_ct,
                sender_id=self.servicio_escolar.id,
                recipient_ct=padre_ct,
                recipient_id=self.padre.id,
                event_type='padre_cita_creada',
                title='Cita con Servicio Escolar agendada',
                message=f"Has agendado una cita con Servicio Escolar para el {fecha} sobre: {estudiantes}",
                rol_destinatario='padre',
                target_ct=cita_ct,
                target_id=cita.id
            )

            # Notificación a servicio escolar
            Notification.objects.create(
                sender_ct=padre_ct,
                sender_id=self.padre.id,
                recipient_ct=servicio_ct,
                recipient_id=self.servicio_escolar.id,
                event_type='servicio_cita_confirmada',
                title=f'Nueva cita con {self.padre.nombre_completo}',
                message=f"Tienes una nueva cita con {self.padre.nombre_completo} el {fecha}",
                rol_destinatario='servicio',
                target_ct=cita_ct,
                target_id=cita.id
            )

        except Exception as e:
            logger.error(f"Error al enviar notificaciones: {str(e)}", exc_info=True)
            raise

    def form_invalid(self, form):
        logger.error("Formulario inválido - Errores: %s", form.errors.as_json())

        # Mostrar errores específicos por campo
        for field, errors in form.errors.items():
            field_name = form.fields[field].label if field in form.fields else field
            for error in errors:
                messages.error(self.request, f"{field_name}: {error}")

        return super().form_invalid(form)


# NUEVA VERSION
class VerDisponibilidadProfesorView(TemplateView):
    template_name = 'padres/citas/calendario_cita.html'

    def dispatch(self, request, *args, **kwargs):
        print("\nIniciando dispatch de VerDisponibilidadProfesorView...")
        try:
            # Verificar sesión del padre (igual que en CrearCitaProfesorView)
            credenciales = request.session.get('credenciales_padre', {})
            print(f"Credenciales obtenidas: {credenciales}")

            if not credenciales.get('id'):
                messages.error(request, 'Debe iniciar sesión como padre')
                return redirect('padres:inicio')

            # Obtener padre y profesor con el mismo método que funciona
            self.padre = Padre.objects.get(id=credenciales['id'])
            self.profesor = Profesor.objects.get(id=kwargs['profesor_id'])

            print(f"Padre obtenido: {self.padre}")
            print(f"Profesor obtenido: ID={self.profesor.id}, Nombre={self.profesor.nombre_completo}")

            return super().dispatch(request, *args, **kwargs)

        except Exception as e:
            print(f"ERROR CRÍTICO en dispatch: {str(e)}")
            messages.error(request, f'Error al cargar disponibilidad: {str(e)}')
            return redirect('padres:inicio')

    def get_context_data(self, **kwargs):
        context = {}
        print("\nIniciando get_context_data...")

        try:
            # Validación estricta como en CrearCitaProfesorView
            if not hasattr(self, 'profesor') or not self.profesor.id:
                raise ValueError("Profesor no disponible en el contexto")

            print(f"Profesor en contexto: ID={self.profesor.id}, Nombre={self.profesor.nombre_completo}")

            # Configuración de fecha
            today = timezone.now().date()
            try:
                year = int(self.request.GET.get('year', today.year))
                month = int(self.request.GET.get('month', today.month))
                current_date = timezone.make_aware(datetime(year=year, month=month, day=1))
            except (ValueError, TypeError):
                current_date = timezone.make_aware(datetime(year=today.year, month=today.month, day=1))

            # Obtener ciclo escolar (con validación)
            ciclo_escolar = CicloEscolar.objects.filter(
                fecha_inicio__lte=today,
                fecha_fin__gte=today
            ).first()

            if not ciclo_escolar:
                raise ValueError("No hay ciclo escolar activo")

            print(f"Ciclo escolar: {ciclo_escolar}")

            # Consultas con el mismo enfoque que en CrearCitaProfesorView
            tiempos_libres = TiempoLibreProfesor.objects.filter(
                profesor_id=self.profesor.id,  # Usando ID directamente
                ciclo_escolar_id=ciclo_escolar.id
            ).order_by('dia_semana', 'hora_inicio')

            horarios_clase = HorarioClase.objects.filter(
                clase__profesor_id=self.profesor.id,
                clase__ciclo_escolar_id=ciclo_escolar.id
            ).select_related('clase')

            citas = Cita.objects.filter(
                profesor_id=self.profesor.id,
                fecha_hora_inicio__gte=timezone.now()
            )

            print(f"Tiempos libres encontrados: {tiempos_libres.count()}")
            print(f"Horarios clase encontrados: {horarios_clase.count()}")
            print(f"Citas encontradas: {citas.count()}")

            # Preparar eventos como en la vista que funciona
            eventos = []
            for tiempo in tiempos_libres:
                eventos.append({
                    'title': f"Disponible: {tiempo.motivo or 'Consulta'}",
                    'start': datetime.combine(today, tiempo.hora_inicio).isoformat(),
                    'end': datetime.combine(today, tiempo.hora_fin).isoformat(),
                    'tipo': 'tiempo_libre',
                    'color': '#28a745',
                    'clickable': True,
                    'dia_semana': tiempo.dia_semana
                })

            for horario in horarios_clase:
                eventos.append({
                    'title': f"Clase: {horario.clase.nombre}",
                    'start': datetime.combine(today, horario.hora_inicio).isoformat(),
                    'end': datetime.combine(today, horario.hora_fin).isoformat(),
                    'tipo': 'clase',
                    'color': '#dc3545',
                    'clickable': False,
                    'dia_semana': horario.dia_semana
                })

            for cita in citas:
                eventos.append({
                    'title': f"Cita: {cita.titulo}",
                    'start': cita.fecha_hora_inicio.isoformat(),
                    'end': cita.fecha_hora_fin.isoformat(),
                    'tipo': 'cita',
                    'color': '#6c757d',
                    'clickable': False
                })

            # Contexto con los mismos nombres que en la vista funcional
            context = {
                'profesor': self.profesor,
                'profesor_id': self.profesor.id,  # Asegurando que el ID está disponible
                'current_date': current_date,
                'eventos': eventos,
                'cita_form': CitaForm(
                    padre=self.padre,
                    profesor=self.profesor,
                    estudiantes_queryset=Estudiante.objects.filter(
                        padre=self.padre,
                        grupo_actual__isnull=False
                    )
                ),
                'debug_data': {
                    'profesor_id': self.profesor.id,
                    'profesor_nombre': self.profesor.nombre_completo,
                    'eventos_count': len(eventos)
                }
            }

            print("Contexto preparado correctamente")

        except Exception as e:
            print(f"ERROR en get_context_data: {str(e)}")
            context['error'] = str(e)

        return context


#

class ReprogramarCitaView(FormView):
    template_name = 'padres/citas/reprogramar_cita.html'
    form_class = ReprogramarCitaForm

    # views.py - Método dispatch actualizado
    def dispatch(self, request, *args, **kwargs):
        # Verificar sesión del padre
        credenciales = request.session.get('credenciales_padre', {})
        if not credenciales.get('id'):
            messages.error(request, 'Debe iniciar sesión como padre')
            return redirect('padres:login_padre')

        self.padre = get_object_or_404(Padre, id=credenciales['id'])
        self.cita = get_object_or_404(Cita, id=kwargs['cita_id'])

        # Verificar que el padre es el solicitante
        if self.cita.solicitante != self.padre:
            messages.error(request, 'No tiene permiso para reprogramar esta cita')
            return redirect('padres:mis_citas')

        # Verificar que la cita puede ser reprogramada
        if self.cita.estado not in ['pendiente', 'confirmada']:
            messages.error(request, 'Solo se pueden reprogramar citas pendientes o confirmadas')
            return redirect('padres:mis_citas')

        # Nueva validación: No permitir reprogramación si faltan menos de 60 minutos
        hora_minima_reprogramacion = self.cita.fecha_hora_inicio - timedelta(hours=1)
        if timezone.now() > hora_minima_reprogramacion:
            messages.error(
                request,
                f"No puede reprogramar esta cita porque falta menos de 1 hora para la misma. "
                f"Límite para reprogramar: {hora_minima_reprogramacion.strftime('%d/%m/%Y %H:%M')}"
            )
            return redirect('padres:mis_citas')

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cita'] = self.cita
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cita'] = self.cita
        return context

    def form_valid(self, form):
        try:
            # Registrar la reprogramación antes de modificar la cita
            ReprogramacionCita.objects.create(
                cita_original=self.cita,
                fecha_hora_original=self.cita.fecha_hora_inicio,
                fecha_hora_nueva=form.cleaned_data['fecha_hora_inicio'],
                motivo=form.cleaned_data['motivo_reprogramacion'],
                realizado_por_tipo=ContentType.objects.get_for_model(self.padre),
                realizado_por_id=self.padre.id
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
            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f'Error al reprogramar la cita: {str(e)}')
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse('padres:mis_citas')

    def _enviar_notificaciones(self):
        # Notificación al padre
        Notification.objects.create(
            sender_ct=ContentType.objects.get_for_model(self.padre),
            sender_id=self.padre.id,
            recipient_ct=ContentType.objects.get_for_model(self.padre),
            recipient_id=self.padre.id,
            event_type='padre_cita_reprogramada',
            title=f'Cita reprogramada: {self.cita.titulo}',
            message=f"Has reprogramado tu cita para el {self.cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}",
            target_ct=ContentType.objects.get_for_model(self.cita),
            target_id=self.cita.id
        )

        # Notificación al profesor o servicio escolar
        if self.cita.profesor:
            recipient = self.cita.profesor
            recipient_ct = ContentType.objects.get_for_model(Profesor)
        else:
            recipient = self.cita.servicio_escolar
            recipient_ct = ContentType.objects.get_for_model(ServicioEscolar)

        Notification.objects.create(
            sender_ct=ContentType.objects.get_for_model(self.padre),
            sender_id=self.padre.id,
            recipient_ct=recipient_ct,
            recipient_id=recipient.id,
            event_type='cita_reprogramada',
            title=f'Cita reprogramada por {self.padre.nombre_completo}',
            message=f"La cita '{self.cita.titulo}' ha sido reprogramada para el {self.cita.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')}. Motivo: {self.request.POST.get('motivo_reprogramacion', 'No especificado')}",
            target_ct=ContentType.objects.get_for_model(self.cita),
            target_id=self.cita.id
        )


'''
def mis_citas(request):
    print("\n=== INICIANDO VISTA MIS_CITAS ===")

    if not request.session.get('credenciales_padre'):
        print("¡No hay sesión activa! Redirigiendo a login...")
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    try:
        # Datos básicos del padre
        padre_id = request.session['credenciales_padre']['id']
        padre = Padre.objects.get(id=padre_id)
        print(f"\nPadre: {padre.nombre_completo} (ID: {padre_id})")

        # Consultas principales
        citas_creadas = Cita.objects.filter(solicitante=padre)
        citas_invitado = Cita.objects.filter(asistentes_padres=padre).exclude(solicitante=padre)

        print(f"\nCitas encontradas:")
        print(f"- Creadas: {citas_creadas.count()}")
        print(f"- Invitado: {citas_invitado.count()}")

        # Filtrado por estado
        estado = request.GET.get('estado')
        if estado:
            print(f"\nFiltrando por estado: {estado}")
            citas_creadas = citas_creadas.filter(estado=estado)
            citas_invitado = citas_invitado.filter(estado=estado)
            print(f"- Creadas después de filtrar: {citas_creadas.count()}")
            print(f"- Invitado después de filtrar: {citas_invitado.count()}")

        # Preparar respuesta
        context = {
            'citas_creadas': citas_creadas.order_by('-fecha_hora_inicio'),
            'citas_invitado': citas_invitado.order_by('-fecha_hora_inicio'),
            'filtro_estado': estado,
            'padre': padre,
            'estados_cita': Cita.ESTADOS,
        }

        print("\n=== FIN DE VISTA - TODO CORRECTO ===")
        return render(request, 'padres/citas/mis_citas.html', context)

    except Padre.DoesNotExist:
        print("\n¡ERROR! Padre no existe en la base de datos")
        messages.error(request, 'Padre no encontrado')
        return redirect('padres:logout_padre')
    except Exception as e:
        print(f"\n¡ERROR INESPERADO! {str(e)}")
        messages.error(request, 'Error al cargar las citas')
        return redirect('padres:inicio')

'''


# print(f"Mensaje de depuración: Padre encontrado - {padre.nombre_completo}")
def mis_citas(request):
    # Verificar que el padre esté en sesión
    if not request.session.get('credenciales_padre'):
        # print("Mensaje de depuración: El padre no está en sesión.")
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    try:
        # Obtener el padre desde la sesión
        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
    except (Padre.DoesNotExist, KeyError):
        # print("Mensaje de depuración: Error al obtener el padre o sesión inválida.")
        messages.error(request, 'Sesión inválida o padre no encontrado')
        return redirect('padres:login_padre')

    # Obtener ContentTypes
    padre_ct = ContentType.objects.get_for_model(Padre)
    # Obtener el ContentType del modelo Profesor
    profesor_ct = ContentType.objects.get_for_model(Profesor)
    servicio_ct = ContentType.objects.get_for_model(ServicioEscolar)
    # print("Mensaje de depuración: ContentTypes obtenidos.")

    # Filtro opcional por estado
    estado = request.GET.get('estado')
    # print(f"Mensaje de depuración: Filtro de estado recibido: {estado}")

    # --- Sección 1: Citas creadas por el padre ---
    citas_creadas = Cita.objects.filter(
        creador_tipo=padre_ct,
        creador_id=padre.id
    )
    # print(f"Mensaje de depuración: Se encontraron {citas_creadas.count()} citas creadas por el padre.")

    # --- Sección 2: Citas donde el padre es el solicitante (asistente) ---
    citas_como_solicitante = Cita.objects.filter(
        solicitante=padre
    )
    # print( f"Mensaje de depuración: Se encontraron {citas_como_solicitante.count()} citas donde el padre es solicitante.")

    # Imprimir los datos completos de cada cita

    # --- Sección 3: Citas solicitadas por el padre y creadas por el Servicio Escolar ---
    citas_solicitante_servicio = Cita.objects.filter(
        solicitante=padre,
        creador_tipo=servicio_ct
    )
    # print(f"Mensaje de depuración: Se encontraron {citas_solicitante_servicio.count()} citas solicitadas por el padre y creadas por Servicio Escolar.")

    # --- Sección 4: Citas solicitadas por el padre y creadas por el Profesor ---
    citas_solicitante_profesor = Cita.objects.filter(
        solicitante=padre,
        creador_tipo=profesor_ct
    )
    # print(f"Mensaje de depuración: Se encontraron {citas_solicitante_profesor.count()} citas solicitadas por el padre y creadas por Profesor.")

    # --- Sección 5: Citas creadas por el profesor y el padre involucrado como solicitante o asistente ---
    citas_profesor_solicitante = Cita.objects.filter(
        solicitante=padre,
        creador_tipo=profesor_ct
    )
    # print(f" Depuración: Se encontraron {citas_profesor_solicitante.count()} citas donde el padre '{padre}' es solicitante y el creador es un profesor.")

    # Filtrar por estado si aplica
    if estado and estado in dict(Cita.ESTADOS):
        # print(f"Mensaje de depuración: Aplicando filtro de estado '{estado}'")
        citas_creadas = citas_creadas.filter(estado=estado)
        citas_como_solicitante = citas_como_solicitante.filter(estado=estado)
        citas_solicitante_servicio = citas_solicitante_servicio.filter(estado=estado)
        citas_solicitante_profesor = citas_solicitante_profesor.filter(estado=estado)
        citas_profesor_solicitante = citas_profesor_solicitante.filter(estado=estado)

    # Preparar contexto
    context = {
        'citas_creadas': citas_creadas.order_by('-fecha_hora_inicio'),
        'citas_como_solicitante': citas_como_solicitante.order_by('-fecha_hora_inicio'),
        'citas_solicitante_servicio': citas_solicitante_servicio.order_by('-fecha_hora_inicio'),
        'citas_solicitante_profesor': citas_solicitante_profesor.order_by('-fecha_hora_inicio'),
        'citas_profesor_solicitante': citas_profesor_solicitante.order_by('-fecha_hora_inicio'),
        'filtro_estado': estado,
        'padre': padre,
        'estados_cita': Cita.ESTADOS,
    }

    return render(request, 'padres/citas/mis_citas.html', context)


'''
 for cita in citas_como_solicitante:
        print("\n Detalles de la Cita:")
        print(f" Fecha y hora de inicio: {cita.fecha_hora_inicio}")
        print(f" Duración: {cita.duracion} minutos")
        print(f" Título: {cita.titulo}")
        print(f" Tipo: {cita.get_tipo_display()}")
        print(f" Ubicación: {cita.ubicacion}")
        print(f" Estado: {cita.get_estado_display()}")
        print(f" Motivo: {cita.motivo}")
        print(f" Observaciones: {cita.observaciones}")
        print(f" Profesor asignado: {cita.profesor if cita.profesor else 'Ninguno'}")
        print(f" Servicio Escolar asignado: {cita.servicio_escolar if cita.servicio_escolar else 'Ninguno'}")
        print(f" Creador ID: {cita.creador_id}")
        print(f" Tipo de creador: {cita.creador_tipo}")
        print(f" Creado por (objeto): {cita.creado_por}")
'''


def confirmar_cita(request, cita_id):
    if not request.session.get('credenciales_padre'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    padre = get_object_or_404(Padre, id=request.session['credenciales_padre']['id'])
    cita = get_object_or_404(Cita, id=cita_id)

    if cita.solicitante != padre:
        messages.error(request, 'No puedes confirmar esta cita.')
        return redirect('padres:mis_citas')

    exito, notif_data = cita.confirmar_por_padre(padre)

    if exito:
        # Cuando un padre confirma:
        cita.generar_notificacion_confirmacion(padre, user_type='padre')
        messages.success(request, 'La cita ha sido confirmada con éxito.')
    else:
        messages.warning(request, 'La cita no pudo ser confirmada.')

    return redirect('padres:mis_citas')


def padre_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('credenciales_padre'):
            messages.warning(request, 'Debes iniciar sesión como padre.')
            return redirect('padres:login_padre')
        return view_func(request, *args, **kwargs)

    return wrapper


class MisTicketsView(ListView):
    model = TicketSoporte
    template_name = 'soporte/tickets_padre.html'
    context_object_name = 'tickets'
    paginate_by = 10

    def get_queryset(self):
        if not self.request.session.get('credenciales_padre'):
            return TicketSoporte.objects.none()

        padre_id = self.request.session['credenciales_padre']['id']
        content_type = ContentType.objects.get_for_model(Padre)

        return TicketSoporte.objects.filter(
            usuario_ct=content_type,
            usuario_id=padre_id
        ).order_by('-creado_en')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['es_padre'] = True
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


class NotificacionesPadreListView(ListView):
    template_name = 'padres/notificaciones/panel_notificaciones.html'
    context_object_name = 'notificaciones'
    paginate_by = 15

    def get_queryset(self):
        padre = get_object_or_404(Padre, id=self.request.session['credenciales_padre']['id'])
        todas = padre.get_notificaciones()

        filtro = self.request.GET.get('filtro')
        if filtro == 'leidas':
            return [n for n in todas if n.is_read]
        elif filtro == 'no-leidas':
            return [n for n in todas if not n.is_read]
        return todas

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        padre = get_object_or_404(Padre, id=self.request.session['credenciales_padre']['id'])
        todas = padre.get_notificaciones()

        # Datos del tema
        ThemeConfig = apps.get_model('servicios_escolares.ThemeConfig')
        theme_config = ThemeConfig.objects.first()
        default_theme = 'css/themes/default.css'
        global_theme = theme_config.global_theme if theme_config else default_theme

        personal_theme = getattr(padre, 'personal_theme', None)
        active_theme = personal_theme if personal_theme else global_theme

        context.update({
            'contador_no_leidas': sum(1 for n in todas if not n.is_read),
            'filtro_actual': self.request.GET.get('filtro', 'todas'),
            'total_notificaciones': len(todas),

            # Contexto extendido estilo padre_context + get_user_role_and_base
            'es_padre': True,
            'padre': padre,
            'can_change_theme': theme_config.allow_padres if theme_config else False,
            'active_theme': active_theme,
            'personal_theme': personal_theme,
        })

        return context


@require_POST
def marcar_notificacion_leida(request, notificacion_id):
    # Autenticación para padre (ajusta según necesites)
    if not request.session.get('credenciales_padre'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    try:
        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
    except Padre.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('padres:logout_padre')

    try:
        notificacion = Notification.objects.get(
            id=notificacion_id,
            recipient_ct=ContentType.objects.get_for_model(Padre),
            recipient_id=padre.id
        )
        notificacion.mark_as_read()
        messages.success(request, 'Notificación marcada como leída')
    except Notification.DoesNotExist:
        messages.error(request, 'Notificación no encontrada')

    return redirect(request.META.get('HTTP_REFERER', 'padres:dashboard_padre'))


@require_POST
def marcar_todas_leidas(request):
    if not request.session.get('credenciales_padre'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    try:
        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
        content_type = ContentType.objects.get_for_model(Padre)

        # Marcar todas como leídas
        notificaciones = Notification.objects.filter(
            recipient_ct=content_type,
            recipient_id=padre.id,
            is_read=False
        )

        count = notificaciones.count()
        notificaciones.update(is_read=True)

        messages.success(request, f'{count} notificaciones marcadas como leídas')
    except Padre.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('padres:logout_padre')

    return redirect(request.META.get('HTTP_REFERER', 'padres:dashboard_padre'))


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


@requiere_padre
def padre_theme_settings(request):
    ThemeConfig = apps.get_model('servicios_escolares.ThemeConfig')
    theme_config = ThemeConfig.objects.first()

    # Verificar permisos
    if not theme_config or not theme_config.allow_padres:
        messages.error(request, 'No tienes permiso para cambiar el tema')
        return redirect('padres:configuracion_padre')

    if request.method == 'POST':
        new_theme = request.POST.get('personal_theme')
        if new_theme in [choice[0] for choice in ThemeConfig.THEME_CHOICES]:
            request.user_obj.personal_theme = new_theme
            request.user_obj.save()
            messages.success(request, 'Tema personal actualizado')

            # Actualizar quién modificó la configuración
            if theme_config:
                theme_config.set_last_updated_by(request.user_obj)
                theme_config.save()

        return redirect('padres:theme_settings')

    return render(request, 'padres/theme_settings.html', {
        'THEME_CHOICES': ThemeConfig.THEME_CHOICES,
        'current_theme': getattr(request.user_obj, 'personal_theme', None),
        'can_change_theme': theme_config.allow_padres if theme_config else False,
        'theme_config': theme_config
    })


def calendar_view(request):
    now = datetime.now()
    context = {
        'current_month': now.strftime("%B"),
        'current_year': now.year,
        'current_day': now.day,
        'current_hour': now.strftime("%I"),
        'current_minute': now.strftime("%M"),
        'am_pm': now.strftime("%p").lower(),
        'today_events': [
            "Reunión de equipo 9:00 AM",
            "Almuerzo con cliente 1:00 PM",
            "Revisión de proyecto 4:00 PM"
        ],
        'weather': {
            'type': 'Soleado',
            'icon': 'fa-sun',
            'max_temp': '28º',
            'min_temp': '20º C'
        }
    }
    return render(request, 'calendar.html', context)


class SeleccionarFechaCitaView(TemplateView):
    template_name = 'padres/citas/seleccionar_fecha.html'

    def dispatch(self, request, *args, **kwargs):
        try:
            credenciales = request.session.get('credenciales_padre', {})
            if not credenciales.get('id'):
                messages.error(request, 'Debe iniciar sesión como padre')
                return redirect('padres:inicio')

            self.padre = Padre.objects.get(id=credenciales['id'])
            self.profesor = Profesor.objects.get(id=kwargs['profesor_id'])
            return super().dispatch(request, *args, **kwargs)

        except (Padre.DoesNotExist, Profesor.DoesNotExist) as e:
            messages.error(request, 'No se pudo identificar el profesor')
            return redirect('padres:inicio')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profesor'] = self.profesor

        # Obtener el ciclo escolar activo
        ciclo_activo = CicloEscolar.objects.filter(activo=True).first()
        context['ciclo_activo'] = ciclo_activo

        return context


class CrearCitaProfesorCalendarioView(CrearCitaProfesorView):
    template_name = 'padres/citas/crear_cita_calendario.html'

    def get(self, request, *args, **kwargs):
        # Verificar que viene de la selección de fecha
        if 'fecha_seleccionada' not in request.GET:
            return redirect('padres:seleccionar_fecha_cita', profesor_id=kwargs['profesor_id'])

        return super().get(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        fecha_seleccionada = self.request.GET.get('fecha_seleccionada')
        if fecha_seleccionada:
            try:
                initial['fecha_hora_inicio'] = timezone.datetime.strptime(fecha_seleccionada, '%Y-%m-%d')
            except (ValueError, TypeError):
                pass
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fecha_seleccionada'] = self.request.GET.get('fecha_seleccionada')
        return context


def obtener_horarios_disponibles(request, profesor_id):
    print("\n=== INICIO obtener_horarios_disponibles ===")
    print(f"Parámetros recibidos: {request.GET}")

    fecha = request.GET.get('fecha')
    start = request.GET.get('start')
    end = request.GET.get('end')

    try:
        credenciales = request.session.get('credenciales_padre', {})
        if not credenciales.get('id'):
            messages.error(request, 'Debe iniciar sesión como padre')
            return redirect('padres:login_padre')

        padre = Padre.objects.get(id=request.session['credenciales_padre']['id'])
        profesor = Profesor.objects.get(id=profesor_id)
        print(f"Profesor encontrado: {profesor.nombre_completo}")

        ciclo_activo = CicloEscolar.obtener_actual()
        print(f"Ciclo actual obtenido: {ciclo_activo}")

        response_data = {
            'horarios_ocupados': [],
            'tiempos_libres': []
        }

        # Define zona horaria local (ajustar según tu configuración)
        local_tz = pytz.timezone('America/Mexico_City')

        def make_aware(dt_naive):
            # Convierte datetime naive a aware en zona local
            if dt_naive.tzinfo is None:
                return local_tz.localize(dt_naive)
            return dt_naive

        if fecha and fecha != 'all':
            # Modo fecha específica
            fecha_dt = datetime.strptime(fecha, '%Y-%m-%d').date()
            dia_semana = fecha_dt.isoweekday()
            print(f"Fecha procesada: {fecha_dt} (día semana: {dia_semana})")

            citas = Cita.objects.filter(
                profesor=profesor,
                fecha_hora_inicio__date=fecha_dt
            ).values('fecha_hora_inicio', 'fecha_hora_fin')

            print(f"Citas encontradas: {citas.count()}")

            response_data['horarios_ocupados'] = [
                {
                    'start': cita['fecha_hora_inicio'].isoformat(),
                    'end': cita['fecha_hora_fin'].isoformat(),
                    'title': 'Espacio ocupado',
                    'color': '#dc3545',
                    'textColor': '#ffffff',
                    'extendedProps': {'tipo': 'ocupado'}
                }
                for cita in citas
            ]

            if ciclo_activo:
                tiempos_libres = TiempoLibreProfesor.objects.filter(
                    profesor=profesor,
                    dia_semana=dia_semana,
                    ciclo_escolar=ciclo_activo
                )
                print(f"Tiempos libres encontrados: {tiempos_libres.count()}")

                for tiempo in tiempos_libres:
                    tiempo_inicio = make_aware(datetime.combine(fecha_dt, tiempo.hora_inicio))
                    tiempo_fin = make_aware(datetime.combine(fecha_dt, tiempo.hora_fin))

                    # Verificar cruce con citas
                    cruza_cita = False
                    for cita in citas:
                        ci = make_aware(cita['fecha_hora_inicio'])
                        cf = make_aware(cita['fecha_hora_fin'])
                        if not (cf <= tiempo_inicio or ci >= tiempo_fin):
                            cruza_cita = True
                            break

                    if cruza_cita:
                        print(f"Tiempo libre omitido el {fecha_dt} por cruce con cita: {tiempo}")
                        continue

                    response_data['tiempos_libres'].append({
                        'start': tiempo_inicio.isoformat(),
                        'end': tiempo_fin.isoformat(),
                        'title': tiempo.motivo or 'Disponible',
                        'color': '#28a745',
                        'textColor': '#ffffff',
                        'extendedProps': {'tipo': 'tiempo_libre_recurrente'}
                    })

        elif fecha == 'all':
            print("\nModo: Consulta completa (vista mensual)")

            if not start or not end:
                return JsonResponse({'error': 'Parámetros start y end son requeridos para vista all'}, status=400)

            start_date = parse_fecha_iso(start)
            end_date = parse_fecha_iso(end)
            print(f"Rango fechas: {start_date} a {end_date}")

            citas = Cita.objects.filter(
                profesor=profesor,
                solicitante=padre,
                fecha_hora_inicio__date__gte=start_date,
                fecha_hora_inicio__date__lte=end_date
            ).values('fecha_hora_inicio', 'fecha_hora_fin', 'titulo')

            print(f"Citas futuras encontradas: {citas.count()}")

            response_data['horarios_ocupados'] = [
                {
                    'start': cita['fecha_hora_inicio'].isoformat(),
                    'end': cita['fecha_hora_fin'].isoformat(),
                    'title': cita['titulo'],
                    'color': '#dc3545',
                    'textColor': '#ffffff',
                    'extendedProps': {'tipo': 'ocupado'}
                }
                for cita in citas
            ]

            if ciclo_activo:
                tiempos_libres = TiempoLibreProfesor.objects.filter(
                    profesor=profesor,
                    ciclo_escolar=ciclo_activo
                )
                print(f"Tiempos libres recurrentes encontrados: {tiempos_libres.count()}")

                citas_por_fecha = {}
                for cita in citas:
                    fecha_cita = cita['fecha_hora_inicio'].date()
                    citas_por_fecha.setdefault(fecha_cita, []).append(cita)

                current_date = start_date
                while current_date <= end_date:
                    dia_semana = current_date.isoweekday()
                    citas_dia = citas_por_fecha.get(current_date, [])

                    for tiempo in tiempos_libres:
                        if tiempo.dia_semana != dia_semana:
                            continue

                        tiempo_inicio = make_aware(datetime.combine(current_date, tiempo.hora_inicio))
                        tiempo_fin = make_aware(datetime.combine(current_date, tiempo.hora_fin))

                        cruza_cita = False
                        for cita in citas_dia:
                            ci = make_aware(cita['fecha_hora_inicio'])
                            cf = make_aware(cita['fecha_hora_fin'])
                            if not (cf <= tiempo_inicio or ci >= tiempo_fin):
                                cruza_cita = True
                                break

                        if cruza_cita:
                            print(f"Omitiendo tiempo libre recurrente {tiempo.id} en {current_date} por cruce con cita")
                            continue

                        response_data['tiempos_libres'].append({
                            'start': tiempo_inicio.isoformat(),
                            'end': tiempo_fin.isoformat(),
                            'title': tiempo.motivo or 'Disponible',
                            'color': '#28a745',
                            'textColor': '#ffffff',
                            'extendedProps': {'tipo': 'tiempo_libre_recurrente'}
                        })

                    current_date += timedelta(days=1)

            else:
                print("No hay ciclo escolar activo para filtrar tiempos libres")

        else:
            print("Parámetro 'fecha' inválido o no proporcionado")
            return JsonResponse({'error': "Parámetro 'fecha' requerido"}, status=400)

        print(f"\nHorarios ocupados: {len(response_data['horarios_ocupados'])}")
        print(f"Tiempos libres: {len(response_data['tiempos_libres'])}")
        print("=== FIN obtener_horarios_disponibles ===\n")

        return JsonResponse(response_data['horarios_ocupados'] + response_data['tiempos_libres'], safe=False)

    except Profesor.DoesNotExist:
        print("ERROR: Profesor no encontrado")
        return JsonResponse({'error': 'Profesor no encontrado'}, status=404)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


def parse_fecha_iso(fecha_str):
    # Quitar la parte de zona horaria para que strptime funcione
    # Ejemplo: '2025-04-28T00:00:00-06:00' -> '2025-04-28T00:00:00'
    fecha_sin_tz = re.sub(r'([+-]\d{2}:\d{2})$', '', fecha_str)
    return datetime.strptime(fecha_sin_tz, '%Y-%m-%dT%H:%M:%S').date()


def obtener_estudiantes_lista(cita):
    if hasattr(cita, 'estudiantes_list') and callable(cita.estudiantes_list):
        return cita.estudiantes_list()
    if hasattr(cita, 'estudiantes'):
        try:
            return [str(est) for est in cita.estudiantes.all()]
        except Exception:
            pass
    return []


@requiere_padre
def api_eventos_padre(request):
    padre = getattr(request, 'user_obj', None)
    eventos = []

    if padre and padre.__class__.__name__ == 'Padre':
        # Obtenemos los content types relevantes
        padre_ct = ContentType.objects.get_for_model(Padre)
        profesor_ct = ContentType.objects.get_for_model(Profesor)
        servicio_ct = ContentType.objects.get_for_model(ServicioEscolar)

        # Filtro por estado si viene en la request
        estado = request.GET.get('estado')

        # 1. Citas creadas directamente por el padre
        citas_creadas = Cita.objects.filter(
            creador_tipo=padre_ct,
            creador_id=padre.id
        )

        # 2. Citas donde el padre es el solicitante
        citas_como_solicitante = Cita.objects.filter(
            solicitante=padre
        ).exclude(
            creador_tipo=padre_ct, creador_id=padre.id
        )

        # 3. Citas donde el padre está como asistente
        citas_como_asistente = Cita.objects.filter(
            asistentes_padres=padre
        ).exclude(
            Q(creador_tipo=padre_ct, creador_id=padre.id) | Q(solicitante=padre)
        )

        # 4. Citas creadas por profesores donde el padre es asistente
        citas_de_profesores = Cita.objects.filter(
            solicitante=padre,
            creador_tipo=profesor_ct
        )

        # 5. Citas creadas por servicios escolares donde el padre es asistente
        citas_de_servicios = Cita.objects.filter(
            creador_tipo=servicio_ct,
            solicitante=padre,
        )

        # Aplicar filtro de estado si existe
        if estado and estado in dict(Cita.ESTADOS):
            citas_creadas = citas_creadas.filter(estado=estado)
            citas_como_solicitante = citas_como_solicitante.filter(estado=estado)
            citas_como_asistente = citas_como_asistente.filter(estado=estado)
            citas_de_profesores = citas_de_profesores.filter(estado=estado)
            citas_de_servicios = citas_de_servicios.filter(estado=estado)
        else:
            # Por defecto mostramos todas las citas en el calendario
            pass

        # Combinar todas las citas
        todas_citas = (
                list(citas_creadas) +
                list(citas_como_solicitante) +
                list(citas_como_asistente) +
                list(citas_de_profesores) +
                list(citas_de_servicios)
        )

        # Eliminar duplicados
        citas_unicas = list({cita.id: cita for cita in todas_citas}.values())

        # Procesar citas prioritarias si existen
        try:
            citas_prioritarias = CitaPrioritaria.objects.filter(
                (models.Q(solicitante=padre) | models.Q(estudiantes__padre=padre)) &
                models.Q(estado__in=['pendiente', 'confirmada', 'reprogramada']) &
                models.Q(fecha_hora_inicio__gte=timezone.now())
            ).distinct().order_by('nivel_prioridad', 'fecha_hora_inicio')

            # Agregar citas prioritarias a la lista
            citas_unicas.extend(citas_prioritarias)
        except Exception as e:
            print(f"Error al obtener citas prioritarias: {e}")

        for cita in citas_unicas:
            estudiantes = obtener_estudiantes_lista(cita)
            if not isinstance(estudiantes, list):
                print(f"¡ALERTA! estudiantes NO es lista para cita {cita.id}: {estudiantes}")
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
                    'solicitante': str(cita.solicitante) if hasattr(cita, 'solicitante') else '',
                    'estudiantes': estudiantes,  # Aquí pasas la lista, no string
                    'prioridad': getattr(cita, 'nivel_prioridad', None),
                    'es_prioritaria': isinstance(cita, CitaPrioritaria)
                }
            })

        # Obtener estudiantes del padre
        estudiantes = padre.hijos.all()

        # Agregar horarios de clases de los estudiantes
        horarios_clases = HorarioClase.objects.filter(
            clase__grupo__estudiantes__in=estudiantes
        ).select_related('clase__profesor', 'clase__grupo').order_by('dia_semana', 'hora_inicio')

        for horario in horarios_clases:
            # Convertir a evento de calendario (ejemplo simplificado)
            eventos.append({
                'id': f"clase_{horario.id}",
                'title': f"Clase: {horario.clase.nombre}",
                'start': f"{horario.dia_semana}T{horario.hora_inicio}",
                'end': f"{horario.dia_semana}T{horario.hora_fin}",
                'backgroundColor': '#9b59b6',  # Morado para clases
                'borderColor': '#9b59b6',
                'textColor': 'white',
                'extendedProps': {
                    'tipo': 'horario_clase',
                    'profesor': str(horario.clase.profesor),
                    'grupo': str(horario.clase.grupo),
                    'materia': horario.clase.nombre
                },
                'display': 'background'  # Para mostrarlo como fondo
            })

        # Agregar tiempos libres de profesores
        descansos_profesores = TiempoLibreProfesor.objects.filter(
            profesor__clases__grupo__estudiantes__in=estudiantes
        ).select_related('profesor').order_by('dia_semana', 'hora_inicio')

        for descanso in descansos_profesores:
            eventos.append({
                'id': f"descanso_{descanso.id}",
                'title': f"Descanso: {descanso.profesor}",
                'start': f"{descanso.dia_semana}T{descanso.hora_inicio}",
                'end': f"{descanso.dia_semana}T{descanso.hora_fin}",
                'backgroundColor': '#f39c12',  # Naranja para descansos
                'borderColor': '#f39c12',
                'textColor': 'white',
                'extendedProps': {
                    'tipo': 'tiempo_libre_profesor',
                    'profesor': str(descanso.profesor)
                },
                'display': 'background'  # Para mostrarlo como fondo
            })

    return JsonResponse(eventos, safe=False)


def seguro_localtime(dt):
    return localtime(dt) if is_naive(dt) else dt


def estado_color(estado, es_prioritaria=False, tipo=None):
    # Colores base por estado
    colores = {
        'pendiente': '#f1c40f',  # amarillo
        'confirmada': '#2ecc71',  # verde
        'completada': '#3498db',  # azul
        'cancelada': '#e74c3c',  # rojo
        'reprogramada': '#e67e22',  # naranja
    }

    # Colores especiales por tipo de cita
    tipo_colores = {
        'reunión': '#9b59b6',  # morado
        'tutoría': '#1abc9c',  # turquesa
        'entrega': '#e91e63',  # rosa
        'general': '#34495e',  # azul oscuro
    }

    # Si es prioritaria, usamos tonos más intensos
    if es_prioritaria:
        colores = {
            'pendiente': '#f39c12',  # naranja más fuerte
            'confirmada': '#27ae60',  # verde más oscuro
            'completada': '#2980b9',  # azul más oscuro
            'cancelada': '#c0392b',  # rojo más oscuro
            'reprogramada': '#d35400',  # naranja más oscuro
        }

    # Prioridad 1: tipo de cita
    if tipo and tipo.lower() in tipo_colores:
        return tipo_colores[tipo.lower()]

    # Prioridad 2: estado
    return colores.get(estado, '#95a5a6')  # gris por defecto
