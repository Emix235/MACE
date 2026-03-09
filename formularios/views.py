from datetime import timezone
from functools import wraps
from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.forms import models, modelformset_factory, inlineformset_factory, BaseInlineFormSet
from django.http import Http404
from profesores.models import Profesor
from .forms import EncuestaForm, AplicarEncuestaForm, get_pregunta_retroalimentacion_formset, \
    PreguntaRetroalimentacionFormSet
from django.db import models
from servicios_escolares.models import ServicioEscolar
from estudiantes.models import CicloEscolar
from .matrices import obtener_metricas_satisfaccion
from .models import Encuesta, EncuestaAplicada, Respuesta, \
    RetroalimentacionCita  # Asegúrate de que Pregunta y Respuesta estén en el mismo app
from .models import Encuesta
from .forms import EditarEncuestaForm, get_pregunta_formset
from django.db.models import Avg, Count, Q, Max, Min
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from .forms import (
    RetroalimentacionForm,
    EditarRetroalimentacionForm,
    PreguntaRetroalimentacionForm,
    AplicarRetroalimentacionForm,
    RespuestaRetroalimentacionForm
)
from .models import (
    RetroalimentacionCita,
    PreguntaRetroalimentacion,
    RetroalimentacionAplicada,
    RespuestaRetroalimentacion
)
from padres.models import Padre
from citas.models import Cita
from django.forms import formset_factory, BaseFormSet
import logging

logger = logging.getLogger(__name__)


def requiere_servicio_escolar(view_func):
    def wrapper(request, *args, **kwargs):
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
        return view_func(request, *args, **kwargs)

    return wrapper


def requiere_profesor(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('credenciales_profesor'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('profesores:login_profesor')

        try:
            profesor = Profesor.objects.get(
                id=request.session['credenciales_profesor']['id'],
                estado_cuenta='Activo'
            )
        except ServicioEscolar.DoesNotExist:
            messages.error(request, 'Usuario no encontrado o cuenta inactiva')
            return redirect('profesores:login_profesor')
        return view_func(request, *args, **kwargs)

    return wrapper


def requiere_padre(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('credenciales_padre'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('padres:login_padre')

        try:
            padre = Padre.objects.get(
                id=request.session['credenciales_padre']['id'],
                estado_cuenta='Activo'
            )
        except Padre.DoesNotExist:
            messages.error(request, 'Usuario padre no encontrado o cuenta inactiva')
            return redirect('padres:login_padre')
        return view_func(request, *args, **kwargs)

    return wrapper


def requiere_servicio_o_profesor(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Verificar si es Servicio Escolar
        if request.session.get('credenciales'):
            try:
                servicio_escolar = ServicioEscolar.objects.get(
                    id=request.session['credenciales']['id'],
                    estado_cuenta='Activo'
                )
                request.user_rol = 'servicio_escolar'
                request.usuario = servicio_escolar
                return view_func(request, *args, **kwargs)
            except ServicioEscolar.DoesNotExist:
                messages.error(request, 'Servicio escolar no encontrado o cuenta inactiva')
                return redirect('servicios_escolares:logout')

        # Verificar si es Profesor
        elif request.session.get('credenciales_profesor'):
            try:
                profesor = Profesor.objects.get(
                    id=request.session['credenciales_profesor']['id'],
                    estado_cuenta='Activo'
                )
                request.user_rol = 'profesor'
                request.usuario = profesor
                return view_func(request, *args, **kwargs)
            except Profesor.DoesNotExist:
                messages.error(request, 'Profesor no encontrado o cuenta inactiva')
                return redirect('profesores:login_profesor')

        # Si no es ninguno
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('padres:login_padre')

    return wrapper


def contestar_encuesta(request):
    ThemeConfig = apps.get_model('servicios_escolares.ThemeConfig')
    theme_config = ThemeConfig.objects.first()
    default_theme = 'css/themes/default.css'
    global_theme = theme_config.global_theme if theme_config else default_theme

    usuario = None
    tipo_usuario = None
    index_url = None
    login_url = None
    base_personalizada = None
    active_theme = global_theme
    personal_theme = None
    can_change_theme = False
    extra_context = {}

    # Verificar si es padre
    if 'credenciales_padre' in request.session:
        try:
            usuario = get_object_or_404(Padre, id=request.session['credenciales_padre']['id'])
            tipo_usuario = 'padre'
            index_url = 'padres:dashboard_padre'
            login_url = 'padres:login_padre'
            base_personalizada = 'padres/base.html'
            personal_theme = getattr(usuario, 'personal_theme', None)
            active_theme = personal_theme if personal_theme else global_theme
            can_change_theme = theme_config.allow_padres if theme_config else False
            extra_context.update({
                'es_padre': True,
                'padre': usuario,
            })
        except Padre.DoesNotExist:
            messages.error(request, 'Padre no encontrado')
            return redirect('padres:logout_padre')

    # Verificar si es profesor
    elif 'credenciales_profesor' in request.session:
        try:
            usuario = get_object_or_404(Profesor, id=request.session['credenciales_profesor']['id'])
            tipo_usuario = 'profesor'
            index_url = 'profesores:dashboard_profesor'
            login_url = 'profesores:login_profesor'
            base_personalizada = 'profesores/base.html'
            personal_theme = getattr(usuario, 'personal_theme', None)
            active_theme = personal_theme if personal_theme else global_theme
            can_change_theme = theme_config.allow_profesors if theme_config else False
            extra_context.update({
                'es_profesor': True,
                'profesor': usuario,
            })
        except Profesor.DoesNotExist:
            messages.error(request, 'Profesor no encontrado')
            return redirect('profesores:logout_profesor')

    else:
        messages.warning(request, 'No tienes permiso para acceder a esta encuesta')
        return redirect('padres:registro_padre')

    # Verificar encuesta activa
    encuesta_aplicada = EncuestaAplicada.objects.filter(activa=True).first()
    if not encuesta_aplicada:
        return redirect(index_url)

    # Verificar si ya contestó
    if Respuesta.objects.filter(encuesta_aplicada=encuesta_aplicada, **{tipo_usuario: usuario}).exists():
        messages.info(request, 'Ya has completado esta encuesta')
        return redirect(index_url)

    preguntas = encuesta_aplicada.encuesta.preguntas.all().order_by('orden')

    if request.method == 'POST':
        # Validar respuestas obligatorias
        for pregunta in preguntas:
            if pregunta.obligatoria and not request.POST.get(f'pregunta_{pregunta.id}'):
                messages.error(request, f'Debes responder la pregunta: {pregunta.texto}')
                return render(request, 'formularios/encuesta/contestar.html', {
                    'encuesta': encuesta_aplicada,
                    'preguntas': preguntas,
                    'tipo_usuario': tipo_usuario,
                    'base': base_personalizada,
                    'active_theme': active_theme,
                    'can_change_theme': can_change_theme,
                    'personal_theme': personal_theme,
                    'login_url': login_url,
                    'dashboard_url': index_url,
                    **extra_context,
                })

        # Guardar respuestas
        for pregunta in preguntas:
            valor = request.POST.get(f'pregunta_{pregunta.id}')
            if valor:
                Respuesta.objects.create(
                    encuesta_aplicada=encuesta_aplicada,
                    pregunta=pregunta,
                    **{tipo_usuario: usuario},
                    valor_texto=valor if pregunta.tipo == 'texto' else None,
                    valor_numero=int(valor) if pregunta.tipo in ['escala_5', 'si_no'] else None,
                )

        messages.success(request, "¡Gracias por completar la encuesta!")
        return redirect(reverse(index_url))

    return render(request, 'formularios/encuesta/contestar.html', {
        'encuesta': encuesta_aplicada,
        'preguntas': preguntas,
        'tipo_usuario': tipo_usuario,
        'base': base_personalizada,
        'active_theme': active_theme,
        'can_change_theme': can_change_theme,
        'personal_theme': personal_theme,
        'login_url': login_url,
        'dashboard_url': index_url,
        **extra_context,
    })


@requiere_servicio_escolar
def gestionar_encuesta(request, pk=None):
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])

    # 1. Obtener la encuesta default original (nunca se edita directamente)
    encuesta_default_original = Encuesta.obtener_encuesta_default(servicio_escolar)

    # 2. Si no se especifica PK, estamos creando una nueva
    if not pk:
        # Crear nueva versión editable basada en la default original
        encuesta = encuesta_default_original.crear_nueva_version()
        messages.info(request, "Se creó una nueva versión editable basada en la plantilla default")
        return redirect('formularios:editar_encuesta', pk=encuesta.pk)

    # 3. Si se especifica PK, obtener esa encuesta específica
    encuesta = get_object_or_404(Encuesta, pk=pk, creada_por=servicio_escolar)

    # 4. Verificar si es la default original (no debería editarse directamente)
    if encuesta.es_default and encuesta.encuesta_base is None:
        messages.warning(request, "No se puede editar la plantilla default directamente. Se creará una nueva versión.")
        nueva_version = encuesta.crear_nueva_version()
        return redirect('formularios:editar_encuesta', pk=nueva_version.pk)

    # 5. Manejar el POST del formulario
    if request.method == 'POST':
        form = EncuestaForm(request.POST, instance=encuesta)
        formset = PreguntaFormSet(request.POST, instance=encuesta)

        if form.is_valid() and formset.is_valid():
            # Guardar la encuesta (asegurando que no sea marcada como default)
            encuesta_actualizada = form.save(commit=False)
            encuesta_actualizada.es_default = False
            encuesta_actualizada.save()

            # Procesar las preguntas
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()

            for instance in instances:
                instance.encuesta = encuesta_actualizada
                instance.save()

            messages.success(request, 'Encuesta guardada exitosamente!')
            return redirect('formularios:lista_encuestas_servicio')
    else:
        form = EncuestaForm(instance=encuesta)
        formset = PreguntaFormSet(instance=encuesta)

    return render(request, 'formularios/encuesta/editar_encuesta.html', {
        'form': form,
        'formset': formset,
        'encuesta': encuesta,
        'es_version_editable': True,
        'version_original': encuesta_default_original
    })


@requiere_servicio_escolar
def lista_encuestas_servicio(request):
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])

    # Obtener la default original
    default_original = Encuesta.obtener_encuesta_default(servicio_escolar)

    # Obtener todas las versiones editables (excluyendo la default original)
    versiones_editables = Encuesta.objects.filter(
        creada_por=servicio_escolar,
        encuesta_base=default_original
    ).order_by('-version')

    # Obtener encuestas aplicadas (versiones finales no editables)
    encuestas_aplicadas = Encuesta.objects.filter(
        creada_por=servicio_escolar,
        es_plantilla=False
    ).order_by('-fecha_creacion')

    return render(request, 'formularios/encuesta/lista_encuestas.html', {
        'default_original': default_original,
        'versiones_editables': versiones_editables,
        'encuestas_aplicadas': encuestas_aplicadas
    })


@requiere_servicio_escolar
def detalle_versiones_encuesta(request, pk=None):
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])

    # Obtener la default original (si no se especifica pk)
    if not pk:
        encuesta_default = Encuesta.obtener_encuesta_default(servicio_escolar)
        return redirect('formularios:detalle_versiones_encuesta', pk=encuesta_default.pk)

    encuesta = get_object_or_404(Encuesta, pk=pk, creada_por=servicio_escolar)

    # Si es una versión editable, redirigir a su encuesta base
    if encuesta.encuesta_base:
        return redirect('formularios:detalle_versiones_encuesta', pk=encuesta.encuesta_base.pk)

    # Obtener todas las versiones ordenadas por fecha (nueva a vieja)
    versiones = encuesta.versiones.all().order_by('-fecha_creacion')

    # Obtener la versión más reciente (primera en la lista o la default si no hay versiones)
    version_mas_reciente = versiones.first() if versiones.exists() else encuesta

    return render(request, 'formularios/encuesta/detalle_versiones.html', {
        'encuesta_default': encuesta,
        'version_actual': version_mas_reciente,
        'versiones': versiones,
        'total_versiones': versiones.count(),
        'encuestas_aplicadas': EncuestaAplicada.objects.filter(encuesta__in=[encuesta] + list(versiones))
    })


@requiere_servicio_escolar
def aplicar_encuesta(request):
    logger.debug("Entrando a aplicar_encuesta")
    messages.debug(request, "Entrando a aplicar_encuesta")

    servicio_escolar = get_object_or_404(
        ServicioEscolar,
        id=request.session['credenciales']['id']
    )
    logger.debug(f"Servicio escolar ID: {servicio_escolar.id}")
    messages.debug(request, f"Servicio escolar cargado: {servicio_escolar.id}")

    encuesta = Encuesta.obtener_encuesta_default(servicio_escolar)
    logger.debug(f"Encuesta default ID: {encuesta.id}")
    messages.debug(request, f"Encuesta default obtenida: {encuesta.id}")

    # Verificar que no esté ya publicada
    if encuesta.aplicaciones.filter(activa=True).exists():
        logger.warning("La encuesta ya tiene una aplicación activa")
        messages.warning(request, "Esta encuesta ya tiene una versión activa publicada")
        return redirect('formularios:lista_encuestas_servicio')

    if request.method == 'POST':
        logger.debug("Request POST recibido")
        messages.debug(request, "Se recibió un POST")

        form = AplicarEncuestaForm(
            request.POST,
            encuesta=encuesta,
            aplicada_por=servicio_escolar
        )

        logger.debug(f"Formulario válido: {form.is_valid()}")
        messages.debug(request, f"Formulario válido: {form.is_valid()}")

        if form.is_valid():
            encuesta_aplicada = form.save()
            logger.info(f"Encuesta aplicada ID: {encuesta_aplicada.id}")
            messages.debug(request, f"Encuesta aplicada creada: {encuesta_aplicada.id}")

            # Marcar la encuesta como no editable
            encuesta.es_plantilla = False
            encuesta.save()
            logger.debug("Encuesta marcada como no plantilla")

            messages.success(
                request,
                f"Encuesta publicada para el ciclo {encuesta_aplicada.ciclo_escolar}"
            )
            return redirect('formularios:lista_encuestas_servicio')
        else:
            logger.error(f"Errores del formulario: {form.errors}")
            messages.error(request, "El formulario contiene errores")
            messages.debug(request, form.errors.as_text())

    else:
        logger.debug("Request GET recibido")
        messages.debug(request, "Se recibió un GET")

        form = AplicarEncuestaForm(
            encuesta=encuesta,
            aplicada_por=servicio_escolar
        )

    return render(request, 'formularios/encuesta/aplicar_encuesta.html', {
        'form': form,
        'encuesta': encuesta
    })


@requiere_servicio_escolar
def finalizar_encuesta(request):
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])

    # Obtener la única encuesta activa del usuario
    encuesta_aplicada = get_object_or_404(
        EncuestaAplicada,
        aplicada_por=servicio_escolar,
        activa=True
    )

    if request.method == 'POST':
        # Solo cambiamos el estado a inactivo (no eliminamos)
        encuesta_aplicada.activa = False
        encuesta_aplicada.save()

        # Reactivar la encuesta base para edición
        encuesta = encuesta_aplicada.encuesta
        encuesta.es_plantilla = True
        encuesta.save()

        messages.success(request, "Encuesta despublicada. Ahora puedes editarla nuevamente.")
        return redirect('formularios:lista_encuestas_servicio')

    return render(request, 'formularios/encuesta/confirmar_finalizar.html', {
        'encuesta_aplicada': encuesta_aplicada
    })


@requiere_servicio_escolar
def lista_encuestas_servicio(request):
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])

    # Obtener SOLO la encuesta por defecto (no permite crear más)
    # encuesta_default = Encuesta.obtener_encuesta_default(servicio_escolar)

    # Por esto (manteniendo tus variables):
    encuesta_default = Encuesta.obtener_encuesta_default(servicio_escolar)
    encuesta_actual = encuesta_default.versiones.order_by('-fecha_creacion').first() or encuesta_default

    # Modificamos esta parte para contar usuarios únicos en lugar de respuestas
    aplicadas = EncuestaAplicada.objects.filter(
        aplicada_por=servicio_escolar
    ).select_related('encuesta', 'ciclo_escolar').annotate(
        num_usuarios=models.Count('respuesta__profesor', distinct=True) + models.Count('respuesta__padre',
                                                                                       distinct=True)
    )

    encuestas_publicadas = {ea.encuesta_id: ea for ea in aplicadas if ea.activa}

    encuestas_con_info = [{
        'encuesta': encuesta_default,
        'actual': encuesta_actual,
        'publicada': encuestas_publicadas.get(encuesta_default.id),
        'num_preguntas': encuesta_default.preguntas.count(),
        'puede_editar': not encuestas_publicadas.get(encuesta_default.id)
    }]

    return render(request, 'formularios/encuesta/lista_servicio.html', {
        'encuestas_con_info': encuestas_con_info,
        'encuestas_aplicadas': aplicadas,
        'ciclos_disponibles': CicloEscolar.objects.all()
    })


'''
# Resto del código original...
    aplicadas = EncuestaAplicada.objects.filter(
        aplicada_por=servicio_escolar
    ).select_related('encuesta', 'ciclo_escolar').annotate(
        num_respuestas=models.Count('respuesta')
    )
'''


@requiere_servicio_escolar
def editar_encuesta(request):
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])

    # 1. Obtener la verdadera default original (nunca se edita directamente)
    encuesta_default = Encuesta.obtener_encuesta_default(servicio_escolar)

    # 2. Buscar la versión editable más reciente (si existe)
    encuesta_editable = encuesta_default.versiones.filter(
        es_plantilla=True
    ).order_by('-version').first()

    # 3. Si no hay versión editable, crear una nueva basada en la default original
    if not encuesta_editable:
        encuesta_editable = encuesta_default.crear_nueva_version()
        messages.info(request, "Se creó una nueva versión editable basada en la plantilla default")

    if request.method == 'POST':
        form = EditarEncuestaForm(request.POST, instance=encuesta_editable)
        formset = get_pregunta_formset(encuesta=encuesta_editable)(request.POST, instance=encuesta_editable)

        if form.is_valid() and formset.is_valid():
            # Si estamos editando la encuesta default actual, crear una nueva versión primero
            if encuesta_editable.es_default:
                encuesta_editable = encuesta_editable.crear_nueva_version()
                form = EditarEncuestaForm(request.POST, instance=encuesta_editable)
                formset = get_pregunta_formset(encuesta=encuesta_editable)(request.POST, instance=encuesta_editable)

            # Guardar los cambios en la versión editable
            encuesta_actualizada = form.save(commit=False)
            encuesta_actualizada.es_plantilla = True
            encuesta_actualizada.save()

            # Procesar las preguntas
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()

            for instance in instances:
                instance.encuesta = encuesta_actualizada
                instance.save()

            messages.success(request, "Encuesta actualizada correctamente")
            return redirect('formularios:lista_encuestas_servicio')
    else:
        form = EditarEncuestaForm(instance=encuesta_editable)
        formset = get_pregunta_formset(encuesta=encuesta_editable)(instance=encuesta_editable)

    return render(request, 'formularios/encuesta/editar_encuesta.html', {
        'form': form,
        'formset': formset,
        'encuesta': encuesta_editable,
        'version_original': encuesta_default.encuesta_base if encuesta_default.encuesta_base else encuesta_default,
        'es_nueva_version': encuesta_editable != encuesta_default
    })


@requiere_servicio_escolar
def detalle_respuestas_encuesta(request, encuesta_aplicada_id):
    encuesta_aplicada = get_object_or_404(
        EncuestaAplicada.objects.select_related('encuesta', 'ciclo_escolar'),
        id=encuesta_aplicada_id,
        aplicada_por_id=request.session['credenciales']['id']
    )

    # Obtener todas las respuestas ordenadas cronológicamente
    respuestas = Respuesta.objects.filter(
        encuesta_aplicada=encuesta_aplicada
    ).select_related('pregunta', 'profesor', 'padre').order_by('fecha_respuesta')

    # Agrupar respuestas por usuario
    usuarios = []
    usuarios_dict = {}

    for respuesta in respuestas:
        usuario = respuesta.respondiente
        if usuario and usuario.id not in usuarios_dict:
            usuarios_dict[usuario.id] = {
                'objeto': usuario,
                'tipo': respuesta.tipo_respondiente,
                'respuestas': [],
                'fecha_ultima_respuesta': respuesta.fecha_respuesta
            }
            usuarios.append(usuarios_dict[usuario.id])

        if usuario:
            usuarios_dict[usuario.id]['respuestas'].append(respuesta)

    # Estadísticas de las preguntas
    preguntas_stats = []
    for pregunta in encuesta_aplicada.encuesta.preguntas.all():
        stats = {
            'pregunta': pregunta,
            'tipo': pregunta.tipo,
            'respuestas': []
        }

        if pregunta.tipo == 'escala_5':
            # Estadísticas para preguntas de escala
            respuestas_pregunta = respuestas.filter(pregunta=pregunta)
            stats['promedio'] = respuestas_pregunta.aggregate(
                avg=Coalesce(Avg('valor_numero'), 0.0)
            )['avg']
            stats['conteo'] = respuestas_pregunta.count()

            # Distribución de respuestas (1-5)
            distribucion = respuestas_pregunta.values('valor_numero').annotate(
                count=Count('valor_numero')
            ).order_by('valor_numero')

            stats['distribucion'] = {i: 0 for i in range(1, 6)}
            for item in distribucion:
                stats['distribucion'][item['valor_numero']] = item['count']

            # Identificar si es de las mejores o peores
            stats['es_positiva'] = stats['promedio'] >= 3.5
            stats['es_negativa'] = stats['promedio'] <= 2.5

        elif pregunta.tipo == 'si_no':
            # Estadísticas para preguntas Sí/No
            respuestas_pregunta = respuestas.filter(pregunta=pregunta)
            stats['si'] = respuestas_pregunta.filter(valor_numero=1).count()
            stats['no'] = respuestas_pregunta.filter(valor_numero=0).count()
            stats['total'] = stats['si'] + stats['no']

        elif pregunta.tipo == 'texto':
            # Estadísticas para preguntas de texto
            respuestas_pregunta = respuestas.filter(pregunta=pregunta).exclude(
                Q(valor_texto__isnull=True) | Q(valor_texto='')
            )
            stats['conteo'] = respuestas_pregunta.count()
            stats['respuestas'] = [
                (r.nombre_respondiente, r.valor_texto)
                for r in respuestas_pregunta.order_by('-fecha_respuesta')[:5]
            ]

        preguntas_stats.append(stats)

    # Ordenar preguntas por mejor/peor puntuación (solo escalas)
    preguntas_escala = [p for p in preguntas_stats if p['tipo'] == 'escala_5']
    mejores_preguntas = sorted(
        preguntas_escala,
        key=lambda x: x['promedio'],
        reverse=True
    )[:3]
    peores_preguntas = sorted(
        preguntas_escala,
        key=lambda x: x['promedio']
    )[:3]

    # Preguntas de texto con más respuestas
    preguntas_texto = [p for p in preguntas_stats if p['tipo'] == 'texto']
    preguntas_texto_top = sorted(
        preguntas_texto,
        key=lambda x: x['conteo'],
        reverse=True
    )[:3]

    return render(request, 'formularios/encuesta/detalle_respuestas.html', {
        'encuesta_aplicada': encuesta_aplicada,
        'usuarios': sorted(usuarios, key=lambda x: x['fecha_ultima_respuesta'], reverse=True),
        'preguntas_stats': preguntas_stats,
        'mejores_preguntas': mejores_preguntas,
        'peores_preguntas': peores_preguntas,
        'preguntas_texto_top': preguntas_texto_top,
        'total_usuarios': len(usuarios),
    })


# RETROALIMENTACIÓN

@requiere_servicio_escolar
def editar_retroalimentacion(request, pk):
    retroalimentacion = get_object_or_404(RetroalimentacionCita, pk=pk)
    print(f"[DEBUG] Editando retroalimentación ID: {retroalimentacion.pk} - Título: {retroalimentacion.titulo}")

    PreguntaFormSet = inlineformset_factory(
        RetroalimentacionCita,
        PreguntaRetroalimentacion,
        form=PreguntaRetroalimentacionForm,
        formset=PreguntaRetroalimentacionFormSet,
        extra=1,
        can_delete=True,
    )

    if request.method == 'POST':
        print("[DEBUG] Método POST recibido")
        form = EditarRetroalimentacionForm(request.POST, instance=retroalimentacion)
        formset = PreguntaFormSet(request.POST, instance=retroalimentacion, prefix='preguntas')

        print("[DEBUG] Formset TOTAL_FORMS:", formset.total_form_count())
        print("[DEBUG] Formset INITIAL_FORMS:", formset.initial_form_count())

        for i, f in enumerate(formset):
            print(f"  Form #{i} vacío?: {not f.has_changed()} - Datos: {f.data if hasattr(f, 'data') else 'no data'}")

        print(
            f"[DEBUG] Formset: TOTAL_FORMS = {formset.total_form_count()}, INITIAL_FORMS = {formset.initial_form_count()}")
        print(f"[DEBUG] Formularios en formset: {len(formset.forms)}")

        if form.is_valid() and formset.is_valid():
            print("[DEBUG] Formulario principal y formset son válidos")

            try:
                with transaction.atomic():
                    retroalimentacion = form.save()
                    print(f"[DEBUG] Retroalimentación guardada: {retroalimentacion.titulo}")

                    deleted_count = 0
                    print("=== [DEBUG] DATOS COMPLETOS DEL FORMSET ANTES DE VALIDAR ===")
                    for i, f in enumerate(formset):
                        print(f"\n--- Pregunta #{i + 1} ---")
                        print(f"  Form es válido: {f.is_valid()}")
                        print(f"  Datos limpios disponibles: {'sí' if f.is_valid() else 'no'}")
                        print(f"  DELETE marcado: {f.cleaned_data.get('DELETE') if f.is_valid() else 'N/A'}")

                        # Campos visibles
                        for field in ['texto', 'tipo', 'orden', 'obligatoria', 'permite_explicacion']:
                            valor = f.cleaned_data.get(field) if f.is_valid() else 'N/A'
                            print(f"  {field}: {valor}")

                        # PK y datos brutos
                        pregunta = f.instance
                        print(f"  ID: {pregunta.pk}")
                        print(f"  Activa: {pregunta.activa}")
                        print(f"  Texto original: {pregunta.texto}")
                        print(
                            f"  Cambios detectados: {f.has_changed()} - Campos cambiados: {f.changed_data if f.has_changed() else 'ninguno'}")

                    for f in formset:
                        pregunta = f.instance
                        if f.cleaned_data.get('DELETE'):
                            print(f"[DEBUG] Pregunta marcada para eliminar: ID {pregunta.pk}")

                            if pregunta.pk:
                                if not pregunta.respuestas.exists():
                                    pregunta.delete()
                                    print("[DEBUG] Pregunta eliminada físicamente")
                                    deleted_count += 1
                                else:
                                    pregunta.activa = False
                                    pregunta.save()
                                    print("[DEBUG] Pregunta con respuestas desactivada")
                        else:
                            # CASO: Pregunta existente con respuestas
                            if pregunta.pk and pregunta.respuestas.exists():
                                # Neutraliza cambios fantasmas por campos no incluidos
                                if 'activa' in f.changed_data and 'activa' not in f.fields:
                                    f.changed_data.remove('activa')

                                if f.has_changed():
                                    print(f"[DEBUG] Cambios detectados en pregunta ID {pregunta.pk}: {f.changed_data}")
                                    pregunta.activa = False
                                    pregunta.save()
                                    print(f"[DEBUG] Pregunta ID {pregunta.pk} desactivada por edición")

                                    nueva_pregunta = PreguntaRetroalimentacion.objects.create(
                                        retroalimentacion=retroalimentacion,
                                        texto=f.cleaned_data.get('texto'),
                                        tipo=f.cleaned_data.get('tipo'),
                                        orden=f.cleaned_data.get('orden'),
                                        obligatoria=f.cleaned_data.get('obligatoria'),
                                        permite_explicacion=f.cleaned_data.get('permite_explicacion'),
                                        activa=True,
                                    )
                                    print(f"[DEBUG] Pregunta nueva creada: ID {nueva_pregunta.pk}")
                                else:
                                    print(f"[DEBUG] Pregunta sin cambios: ID {pregunta.pk}")
                                    f.save()

                            # CASO: Pregunta nueva (sin .pk) o sin respuestas
                            else:
                                if f.cleaned_data and not f.cleaned_data.get('DELETE') and any(
                                        f.cleaned_data.get(field) not in [None, ''] for field in ['texto', 'tipo']
                                ):
                                    print(f"[DEBUG] cleaned_data: {f.cleaned_data}")
                                    f.save()
                                    print("[DEBUG] Nueva pregunta guardada")
                                else:
                                    print("[DEBUG] Ignorando formulario vacío")

                    messages.success(request, f"Cambios guardados. {deleted_count} preguntas eliminadas/desactivadas.")
                    return redirect('formularios:gestionar_retroalimentacion')

            except Exception as e:
                print(f"[ERROR] Excepción durante guardado: {e}")
                messages.error(request, f"Error crítico: {str(e)}")

        else:
            print("[DEBUG] Errores de validación")
            error_messages = []
            for i, f in enumerate(formset):
                if not f.cleaned_data.get('DELETE') and f.errors:
                    for field, errors in f.errors.items():
                        for error in errors:
                            print(f"[ERROR] Pregunta {i + 1} - Campo {field}: {error}")
                            error_messages.append(f"Pregunta {i + 1}: {error}")
            if error_messages:
                messages.error(request, "Errores: " + "; ".join(error_messages[:3]))

    else:
        print("[DEBUG] Método GET recibido - Cargando formulario")
        form = EditarRetroalimentacionForm(instance=retroalimentacion)
        formset = PreguntaFormSet(
            queryset=retroalimentacion.preguntas.filter(activa=True),
            instance=retroalimentacion,
            prefix='preguntas'
        )

        print("[DEBUG] Formset TOTAL_FORMS:", formset.total_form_count())
        print("[DEBUG] Formset INITIAL_FORMS:", formset.initial_form_count())

        for i, f in enumerate(formset):
            print(f"  Form #{i} vacío?: {not f.has_changed()} - Datos: {f.data if hasattr(f, 'data') else 'no data'}")

        print(
            f"[DEBUG] Formset: TOTAL_FORMS = {formset.total_form_count()}, INITIAL_FORMS = {formset.initial_form_count()}")
        print(f"[DEBUG] Formularios en formset: {len(formset.forms)}")

    return render(request, 'formularios/retroalimentacion/editar.html', {
        'form': form,
        'formset': formset,
        'retroalimentacion': retroalimentacion,
    })


'''
@requiere_servicio_escolar
def editar_retroalimentacion(request, pk):
    retroalimentacion = get_object_or_404(RetroalimentacionCita, pk=pk)

    PreguntaFormSet = inlineformset_factory(
        RetroalimentacionCita,
        PreguntaRetroalimentacion,
        form=PreguntaRetroalimentacionForm,
        formset=PreguntaRetroalimentacionFormSet,
        extra=1,
        can_delete=True,
        validate_min=False
    )

    if request.method == 'POST':
        form = EditarRetroalimentacionForm(request.POST, instance=retroalimentacion)
        formset = PreguntaFormSet(request.POST, instance=retroalimentacion, prefix='preguntas')

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    retroalimentacion = form.save()

                    # Procesar eliminaciones primero
                    deleted_count = 0
                    for form in formset:
                        if form.cleaned_data.get('DELETE') and form.instance.pk:
                            if not form.instance.respuestas.exists():
                                form.instance.delete()
                                deleted_count += 1
                            else:
                                form.instance.activa = False
                                form.instance.save()

                    # Guardar el resto normalmente
                    formset.save()

                    messages.success(request,
                                     f"Cambios guardados. {deleted_count} preguntas eliminadas.")
                    return redirect('formularios:editar_retroalimentacion', pk=retroalimentacion.pk)

            except Exception as e:
                messages.error(request, f"Error crítico: {str(e)}")
        else:
            # Solo mostrar errores de forms no marcados para borrar
            error_messages = []
            for i, form in enumerate(formset):
                if not form.cleaned_data.get('DELETE') and form.errors:
                    error_messages.extend(
                        f"Pregunta {i + 1}: {error}"
                        for field, errors in form.errors.items()
                        for error in errors
                    )

            if error_messages:
                messages.error(request, "Errores: " + "; ".join(error_messages[:3]))  # Mostrar máximo 3 errores
    else:
        form = EditarRetroalimentacionForm(instance=retroalimentacion)
        formset = PreguntaFormSet(instance=retroalimentacion, prefix='preguntas')

    return render(request, 'formularios/retroalimentacion/editar.html', {
        'form': form,
        'formset': formset,
        'retroalimentacion': retroalimentacion,
    })
'''

'''
@requiere_servicio_escolar
def gestionar_retroalimentacion(request):
    """Vista principal para gestionar plantillas de retroalimentación"""
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])

    retroalimentacion_default = RetroalimentacionCita.obtener_retroalimentacion_default(servicio_escolar)
    plantillas = RetroalimentacionCita.objects.filter(
        creada_por=servicio_escolar,
        es_plantilla=True
    ).exclude(pk=retroalimentacion_default.pk)

    return render(request, 'formularios/retroalimentacion/gestion.html', {
        'retroalimentacion_default': retroalimentacion_default,
        'plantillas': plantillas,
    })
'''


@requiere_servicio_escolar
def gestionar_retroalimentacion(request):
    """Vista principal para gestionar plantillas de retroalimentación"""
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])

    try:
        # Obtener las plantillas default con prefetch de preguntas activas
        retro_servicio = RetroalimentacionCita.obtener_retroalimentacion_default(servicio_escolar)
        retro_profesor = RetroalimentacionCita.obtener_retroalimentacion_default(servicio_escolar, para_profesor=True)

        if not retro_servicio or not retro_profesor:
            raise ValueError("No se pudo obtener las plantillas requeridas")

        # Prefetch de preguntas activas para las plantillas principales
        retro_servicio = RetroalimentacionCita.objects.prefetch_related(
            models.Prefetch(
                'preguntas',
                queryset=PreguntaRetroalimentacion.objects.filter(activa=True)
            )
        ).get(pk=retro_servicio.pk)

        retro_profesor = RetroalimentacionCita.objects.prefetch_related(
            models.Prefetch(
                'preguntas',
                queryset=PreguntaRetroalimentacion.objects.filter(activa=True)
            )
        ).get(pk=retro_profesor.pk)

        historial_servicio = retro_servicio.historial() if hasattr(retro_servicio, 'historial') else []
        historial_profesor = retro_profesor.historial() if hasattr(retro_profesor, 'historial') else []

        # Filtramos plantillas (sin cambiar los querysets existentes)
        qs_servicio = RetroalimentacionCita.objects.filter(
            creada_por=servicio_escolar,
            es_plantilla=True,
            es_para_profesor=False
        ).exclude(pk=retro_servicio.pk)

        qs_profesor = RetroalimentacionCita.objects.filter(
            creada_por=servicio_escolar,
            es_plantilla=True,
            es_para_profesor=True
        ).exclude(pk=retro_profesor.pk)

        # Obtener qué tab está activo y qué página mostrar
        tab = request.GET.get('tab', 'servicio')
        page_servicio = request.GET.get('page_servicio', 1)
        page_profesor = request.GET.get('page_profesor', 1)

        paginator_servicio = Paginator(qs_servicio, 5)
        paginator_profesor = Paginator(qs_profesor, 5)

        plantillas_servicio = paginator_servicio.get_page(page_servicio)
        plantillas_profesor = paginator_profesor.get_page(page_profesor)

        return render(request, 'formularios/retroalimentacion/gestion.html', {
            'plantilla_servicio': retro_servicio,
            'plantilla_profesor': retro_profesor,
            'historial_servicio': historial_servicio,
            'historial_profesor': historial_profesor,
            'plantillas_servicio': plantillas_servicio,
            'plantillas_profesor': plantillas_profesor,
            'tab_activa': tab,
        })

    except Exception as e:
        logger.error(f"Error en gestión de retroalimentación: {str(e)}", exc_info=True)
        messages.error(request, "Error al cargar las plantillas. Por favor contacte al administrador.")
        return redirect('servicios_escolares:dashboard')


@requiere_servicio_escolar
def historial_preguntas(request):
    """Vista para mostrar todas las preguntas (activas e inactivas)"""
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])

    # Obtenemos todas las preguntas de las plantillas del servicio escolar
    preguntas = PreguntaRetroalimentacion.objects.filter(
        retroalimentacion__creada_por=servicio_escolar,
        retroalimentacion__es_plantilla=True
    ).select_related('retroalimentacion').order_by('-fecha_creacion')

    # Filtros
    estado = request.GET.get('estado', 'todas')
    tipo = request.GET.get('tipo', None)

    if estado == 'activas':
        preguntas = preguntas.filter(activa=True)
    elif estado == 'inactivas':
        preguntas = preguntas.filter(activa=False)

    if tipo:
        preguntas = preguntas.filter(tipo=tipo)

    paginator = Paginator(preguntas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'formularios/retroalimentacion/historial_preguntas.html', {
        'page_obj': page_obj,
        'estado': estado,
        'tipo': tipo,
        'tipos_preguntas': PreguntaRetroalimentacion.TIPO_RESPUESTA_CHOICES
    })


@requiere_servicio_escolar
def detalle_pregunta(request, pregunta_id):
    """Vista para mostrar el detalle de una pregunta y sus respuestas históricas"""
    pregunta = get_object_or_404(PreguntaRetroalimentacion, pk=pregunta_id)

    # Verificar que la pregunta pertenece al servicio escolar
    if pregunta.retroalimentacion.creada_por.id != request.session['credenciales']['id']:
        raise PermissionDenied

    respuestas = RespuestaRetroalimentacion.objects.filter(
        pregunta=pregunta
    ).select_related('retroalimentacion_aplicada__cita', 'padre').order_by('-fecha_respuesta')

    # Estadísticas para preguntas numéricas
    estadisticas = None
    if pregunta.tipo == 'escala_5':
        estadisticas = respuestas.aggregate(
            promedio=Avg('valor_numero'),
            total=Count('id'),
            maximo=Max('valor_numero'),
            minimo=Min('valor_numero')
        )

    return render(request, 'formularios/retroalimentacion/detalle_pregunta.html', {
        'pregunta': pregunta,
        'respuestas': respuestas[:100],  # Limitar a 100 respuestas
        'estadisticas': estadisticas
    })


@requiere_servicio_escolar
def activar_pregunta(request, pregunta_id):
    """Vista para reactivar una pregunta inactiva"""
    if request.method == 'POST':
        pregunta = get_object_or_404(PreguntaRetroalimentacion, pk=pregunta_id)

        # Verificar permisos
        if pregunta.retroalimentacion.creada_por.id != request.session['credenciales']['id']:
            raise PermissionDenied

        pregunta.activa = True
        pregunta.save()
        messages.success(request, 'Pregunta reactivada correctamente')

    return redirect('formularios:historial_preguntas')


@requiere_servicio_escolar
def eliminar_pregunta(request, pregunta_id):
    """Vista para eliminar permanentemente una pregunta (solo si no tiene respuestas)"""
    if request.method == 'POST':
        pregunta = get_object_or_404(PreguntaRetroalimentacion, pk=pregunta_id)

        # Verificar permisos
        if pregunta.retroalimentacion.creada_por.id != request.session['credenciales']['id']:
            raise PermissionDenied

        if RespuestaRetroalimentacion.objects.filter(pregunta=pregunta).exists():
            messages.error(request, 'No se puede eliminar una pregunta que ya tiene respuestas')
        else:
            pregunta.delete()
            messages.success(request, 'Pregunta eliminada permanentemente')

    return redirect('historial_preguntas')


@requiere_servicio_escolar
def aplicar_retroalimentacion(request, pk):
    """Vista para aplicar una plantilla como retroalimentación final"""
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])
    retroalimentacion = get_object_or_404(RetroalimentacionCita, pk=pk)

    if request.method == 'POST':
        form = AplicarRetroalimentacionForm(
            request.POST,
            retroalimentacion=retroalimentacion,
            aplicada_por=servicio_escolar
        )

        if form.is_valid():
            form.save()
            messages.success(request, "Retroalimentación aplicada exitosamente")
            return redirect('formularios:gestionar_retroalimentacion')
    else:
        form = AplicarRetroalimentacionForm(
            retroalimentacion=retroalimentacion,
            aplicada_por=servicio_escolar
        )

    return render(request, 'formularios/retroalimentacion/aplicar.html', {
        'form': form,
        'retroalimentacion': retroalimentacion,
    })


@requiere_servicio_escolar
class HistorialRetroalimentacionPadres(ListView):
    """Vista para mostrar el historial de retroalimentaciones de padres"""
    model = RespuestaRetroalimentacion
    template_name = 'formularios/retroalimentacion/historial_padres.html'
    context_object_name = 'respuestas'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'padre',
            'retroalimentacion_aplicada__cita',
            'pregunta'
        )

        # Filtros opcionales
        padre_id = self.request.GET.get('padre_id')
        if padre_id:
            queryset = queryset.filter(padre_id=padre_id)

        fecha_inicio = self.request.GET.get('fecha_inicio')
        fecha_fin = self.request.GET.get('fecha_fin')
        if fecha_inicio and fecha_fin:
            queryset = queryset.filter(
                fecha_respuesta__date__gte=fecha_inicio,
                fecha_respuesta__date__lte=fecha_fin
            )

        return queryset.order_by('-fecha_respuesta')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_respuestas'] = self.get_queryset().count()
        context['padres'] = Padre.objects.filter(
            respuestas_retroalimentacion__isnull=False
        ).distinct()
        return context


class RespuestaFormSet(BaseFormSet):
    def __init__(self, *args, **kwargs):
        self.preguntas = kwargs.pop('preguntas')
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['pregunta'] = self.preguntas[i]
        return super()._construct_form(i, **kwargs)


PreguntaFormSet = inlineformset_factory(
    RetroalimentacionCita,
    PreguntaRetroalimentacion,
    form=PreguntaRetroalimentacionForm,
    formset=PreguntaRetroalimentacionFormSet,
    extra=1,
    can_delete=True,
    validate_min=False  # Permite enviar el formulario sin todas las preguntas requeridas
)


class BaseRespuestaFormSet(BaseFormSet):
    def __init__(self, *args, preguntas=None, **kwargs):
        self.preguntas = preguntas or []
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        if hasattr(self, 'preguntas') and index < len(self.preguntas):
            kwargs['pregunta'] = self.preguntas[index]
        return kwargs

    def total_form_count(self):
        return len(self.preguntas)


PreguntaFormSetCopia = formset_factory(
    RespuestaRetroalimentacionForm,
    formset=BaseRespuestaFormSet,
    extra=0
)


@requiere_padre
def responder_retroalimentacion(request, cita_id):
    padre = Padre.objects.get(id=request.session['credenciales_padre']['id'], estado_cuenta='Activo')
    cita = get_object_or_404(Cita, id=cita_id, solicitante=padre)

    if not hasattr(cita, 'retroalimentacion'):
        raise Http404("No hay retroalimentación para esta cita")

    retroalimentacion = cita.retroalimentacion

    if retroalimentacion.completada:
        messages.warning(request, "Ya has completado esta retroalimentación")
        return redirect('padres:mis_citas')

    preguntas = retroalimentacion.retroalimentacion.preguntas.all()
    print(f"[DEBUG] Preguntas encontradas: {preguntas.count()}")

    if request.method == 'POST':
        formset = PreguntaFormSetCopia(request.POST, preguntas=preguntas, prefix='respuestas')
        print(f"[DEBUG] Datos POST recibidos: {request.POST}")

        for form in formset.forms:
            if form.instance:
                form.instance.padre = padre
                form.instance.retroalimentacion_aplicada = retroalimentacion

        if formset.is_valid():
            print("[DEBUG] Formulario válido")

            # Eliminar respuestas existentes para evitar duplicados
            RespuestaRetroalimentacion.objects.filter(
                retroalimentacion_aplicada=retroalimentacion,
                padre=padre
            ).delete()

            for form, pregunta in zip(formset.forms, preguntas):
                print(f"[DEBUG] Procesando pregunta ID: {pregunta.id}")
                print(f"[DEBUG] Datos limpios: {form.cleaned_data}")

                # Crear respuesta con el padre ya asignado
                respuesta = RespuestaRetroalimentacion(
                    retroalimentacion_aplicada=retroalimentacion,
                    pregunta=pregunta,
                    padre=padre,  # ¡ASIGNAR EL PADRE AQUÍ ES CLAVE!
                    valor_numero=form.cleaned_data.get('valor_numero'),
                    respuesta_si_no=form.cleaned_data.get('respuesta_si_no'),
                    explicacion=form.cleaned_data.get('explicacion'),
                    respuesta_texto=form.cleaned_data.get('respuesta_texto'),
                )
                respuesta.save()
                print(f"[DEBUG] Respuesta guardada: {respuesta.id}")

            retroalimentacion.marcar_como_completada()
            messages.success(request, "¡Gracias por tu retroalimentación!")
            return redirect('padres:mis_citas')
        else:
            print(f"[DEBUG] Errores en el formulario: {formset.errors}")
            messages.error(request, "Hubo errores en el formulario. Por favor corrige los datos.")
    else:
        initial_data = [{'pregunta_id': pregunta.id} for pregunta in preguntas]
        formset = PreguntaFormSetCopia(
            initial=initial_data,
            preguntas=preguntas,
            prefix='respuestas'
        )

    context = {
        'cita': cita,
        'retroalimentacion': retroalimentacion,
        'formset': formset,
        'preguntas': preguntas,
        'titulo': f"Retroalimentación: {cita.titulo}"
    }

    return render(request, 'formularios/retroalimentacion/responder.html', context)


# No se si lo necesito
@requiere_servicio_o_profesor
def marcar_cita_completada(request, cita_id):
    cita = get_object_or_404(Cita, pk=cita_id)

    usuario = ''
    tipo_usuario = ''
    index_url = ''
    base_personalizada = ''

    # Obtener tipo de usuario y datos de sesión
    if 'credenciales' in request.session:
        try:
            usuario = ServicioEscolar.objects.get(id=request.session['credenciales']['id'])
            tipo_usuario = 'servicio_escolar'
            index_url = 'servicios_escolares:dashboard'
            base_personalizada = 'servicios_escolares/base.html'
        except ServicioEscolar.DoesNotExist:
            messages.error(request, 'Servicio escolar no encontrado')
            return redirect('servicios_escolares:login')

    elif 'credenciales_profesor' in request.session:
        try:
            usuario = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
            tipo_usuario = 'profesor'
            index_url = 'profesores:dashboard_profesor'
            base_personalizada = 'profesores/base.html'
        except Profesor.DoesNotExist:
            messages.error(request, 'Profesor no encontrado')
            return redirect('profesores:login_profesor')

    # Verificar permisos según el tipo de usuario
    if tipo_usuario == 'profesor':
        if not (cita.profesor == usuario or
                cita.asistentes_profesores.filter(id=usuario.id).exists()):
            raise PermissionDenied("No tienes permiso para completar esta cita")

    # Verificar que la cita pueda marcarse como completada
    if not cita.puede_marcar_como_completada:
        messages.error(request, "Esta cita no puede marcarse como completada aún")
        return redirect(index_url, cita_id=cita.id)

    if request.method == 'POST':
        try:
            if cita.marcar_como_completada(usuario):
                messages.success(request, "Cita marcada como completada correctamente")
            else:
                messages.warning(request, "La cita ya estaba marcada como completada")

            return redirect(index_url)

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

    # Contexto para la plantilla
    context = {
        'cita': cita,
        'tipo_usuario': tipo_usuario,
        'base_personalizada': base_personalizada,
        'index_url': index_url
    }

    return render(request, 'formularios/retroalimentacion/confirmar_completar.html', context)


@requiere_servicio_escolar
def completar_citas_pasadas(request):
    usuario = request.usuario  # Obtenido del decorador
    citas_pendientes = Cita.citas_pasadas_pendientes(usuario)

    if request.method == 'POST':
        cita_id = request.POST.get('cita_id')
        if cita_id:
            cita = get_object_or_404(Cita, pk=cita_id)
            try:
                if cita.marcar_como_completada(usuario):
                    messages.success(request, f"Cita #{cita.id} marcada como completada")
                else:
                    messages.warning(request, f"La cita #{cita.id} ya estaba completada")
            except Exception as e:
                messages.error(request, f"Error al completar cita: {str(e)}")
            return redirect('completar_citas_pasadas')

    return render(request, 'servicios_escolares/citas/completar_citas.html', {
        'citas_pendientes': citas_pendientes,
        'ahora': timezone.now()
    })


'''
            for form, pregunta in zip(formset.forms, preguntas):
                if not RespuestaRetroalimentacion.objects.filter(
                        retroalimentacion_aplicada=retroalimentacion,
                        padre=padre,
                        pregunta=pregunta
                ).exists():
                    respuesta = RespuestaRetroalimentacion(
                        retroalimentacion_aplicada=retroalimentacion,
                        padre=padre,
                        pregunta=pregunta,
                        valor_numero=form.cleaned_data.get('valor_numero'),
                        respuesta_si_no=form.cleaned_data.get('respuesta_si_no'),
                        explicacion=form.cleaned_data.get('explicacion'),
                        respuesta_texto=form.cleaned_data.get('respuesta_texto'),
                    )
                    respuesta.save()
                else:
                    messages.warning(request, f"Ya respondiste la pregunta: {pregunta.texto}")
'''

'''
@requiere_servicio_escolar
def editar_encuesta(request):
    servicio_escolar = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])

    # Obtener la única encuesta por defecto
    encuesta = Encuesta.obtener_encuesta_default(servicio_escolar)

    aplicaciones_activas = encuesta.aplicaciones.filter(activa=True).exists()

    if request.method == 'POST':
        form = EditarEncuestaForm(request.POST, instance=encuesta)
        formset = get_pregunta_formset(encuesta=encuesta)(request.POST, instance=encuesta)

        if form.is_valid() and formset.is_valid():
            if aplicaciones_activas and form.cleaned_data.get('crear_nueva_version'):
                nueva_version = encuesta.crear_nueva_version()
                messages.success(request, "Se creó una nueva versión para editar sin afectar la versión publicada")
                return redirect('editar_encuesta')

            form.save()
            formset.save()
            messages.success(request, "Encuesta actualizada correctamente")
            return redirect('formularios:lista_encuestas_servicio')
    else:
        form = EditarEncuestaForm(instance=encuesta, initial={
            'crear_nueva_version': aplicaciones_activas
        })
        formset = get_pregunta_formset(encuesta=encuesta)(instance=encuesta)

    return render(request, 'formularios/encuesta/editar_encuesta.html', {
        'form': form,
        'formset': formset,
        'encuesta': encuesta,
        'aplicaciones_activas': aplicaciones_activas
    })
'''

'''
@requiere_servicio_escolar
def editar_retroalimentacion(request, pk):
    """Vista para editar una plantilla de retroalimentación"""
    retroalimentacion: RetroalimentacionCita = get_object_or_404(RetroalimentacionCita, pk=pk)
    PreguntaFormSet = get_pregunta_retroalimentacion_formset(extra=1)

    if request.method == 'POST':
        form = EditarRetroalimentacionForm(request.POST, instance=retroalimentacion)
        formset = PreguntaFormSet(request.POST, instance=retroalimentacion)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                crear_nueva = form.cleaned_data.get('#', False)

                if crear_nueva and retroalimentacion.aplicaciones.exists():
                    nueva_version = retroalimentacion.crear_nueva_version()
                    messages.success(request, "Se ha creado una nueva versión editable")
                    return redirect('formularios:editar_retroalimentacion', pk=nueva_version.pk)

                form.save()
                formset.save()
                messages.success(request, "Cambios guardados exitosamente")
                return redirect('formularios:editar_retroalimentacion', pk=retroalimentacion.pk)
    else:
        form = EditarRetroalimentacionForm(instance=retroalimentacion)
        formset = PreguntaFormSet(instance=retroalimentacion)

    return render(request, 'formularios/retroalimentacion/editar.html', {
        'form': form,
        'formset': formset,
        'retroalimentacion': retroalimentacion,
        'es_default': retroalimentacion.es_default,
    })
'''

'''
@requiere_padre
def responder_retroalimentacion(request, cita_id):
    print("\n=== INICIO DE VISTA ===")

    padre = Padre.objects.get(id=request.session['credenciales_padre']['id'], estado_cuenta='Activo')
    cita = get_object_or_404(Cita, id=cita_id, solicitante=padre)
    print(f"Padre: {padre.id}, Cita: {cita.id}")

    if not hasattr(cita, 'retroalimentacion'):
        raise Http404("No hay retroalimentación para esta cita")

    retroalimentacion = cita.retroalimentacion
    print(f"Retroalimentación encontrada: {retroalimentacion.id}")

    if retroalimentacion.completada:
        messages.warning(request, "Ya has completado esta retroalimentación")
        return redirect('padres:mis_citas')

    retroalimentacion_aplicada = cita.retroalimentacion
    preguntas = retroalimentacion_aplicada.retroalimentacion.preguntas.all()
    print(f"\n=== PREGUNTAS ENCONTRADAS ({preguntas.count()}) ===")
    for i, p in enumerate(preguntas, 1):
        print(f"{i}. ID: {p.id}, Tipo: {p.tipo}, Texto: {p.texto[:50]}...")

    if request.method == 'POST':
        print("\n=== DATOS POST RECIBIDOS ===")
        print("POST data:", request.POST)

        formset = PreguntaFormSetCopia(request.POST, preguntas=preguntas, prefix='respuestas')
        print(f"\n=== FORMSET POST CREADO ===")
        print(f"Total forms: {len(formset.forms)}")
        print(f"Management form: {formset.management_form}")

        for i, form in enumerate(formset.forms):
            print(f"\nForm {i + 1} - Prefijo: {form.prefix}")
            print("Bound:", form.is_bound)

            if form.instance:
                form.instance.padre = padre
                form.instance.retroalimentacion_aplicada = retroalimentacion
            print("Valid:", form.is_valid())
            print("Errors:", form.errors)
            print("Cleaned data:", getattr(form, 'cleaned_data', None))

        if formset.is_valid():
            print("\n=== FORMSET VÁLIDO ===")
            for form, pregunta in zip(formset.forms, preguntas):
                print(f"\nProcesando pregunta {pregunta.id}")
                if RespuestaRetroalimentacion.objects.filter(
                        retroalimentacion_aplicada=retroalimentacion,
                        padre=padre,
                        pregunta=pregunta
                ).exists():
                    print("Respuesta ya existe, omitiendo")
                    continue

                respuesta = RespuestaRetroalimentacion(
                    retroalimentacion_aplicada=retroalimentacion,
                    padre=padre,
                    pregunta=pregunta,
                    valor_numero=form.cleaned_data.get('valor_numero'),
                    respuesta_si_no=form.cleaned_data.get('respuesta_si_no'),
                    explicacion=form.cleaned_data.get('explicacion'),
                    respuesta_texto=form.cleaned_data.get('respuesta_texto'),
                )
                respuesta.save()
                print(f"Respuesta guardada para pregunta {pregunta.id}")

            retroalimentacion.marcar_como_completada()
            messages.success(request, "¡Gracias por tu retroalimentación!")
            return redirect('padres:mis_citas')
        else:
            print("\n=== ERRORES EN FORMSET ===")
            print("Formset errors:", formset.errors)
            print("Non form errors:", formset.non_form_errors())
    else:
        print("\n=== MÉTODO GET ===")
        initial_data = [{'pregunta_id': pregunta.id} for pregunta in preguntas]
        print("Initial data:", initial_data)

        formset = PreguntaFormSetCopia(
            initial=initial_data,
            preguntas=preguntas,
            prefix='respuestas'  # Mismo prefijo que en POST
        )
        print(f"\n=== FORMSET GET CREADO ===")
        print(f"Total forms: {len(formset.forms)}")
        print(f"Management form: {formset.management_form}")

        for i, form in enumerate(formset.forms):
            print(f"\nForm {i + 1} - Prefijo: {form.prefix}")
            print("Bound:", form.is_bound)
            print("Fields:", list(form.fields.keys()))
            print("Initial:", form.initial)

    context = {
        'cita': cita,
        'retroalimentacion': retroalimentacion,
        'formset': formset,
        'preguntas': preguntas,
        'titulo': f"Retroalimentación: {cita.titulo}"
    }

    print("\n=== CONTEXTO ENVIADO A TEMPLATE ===")
    print("Keys:", context.keys())
    return render(request, 'formularios/retroalimentacion/responder.html', context)
'''


@requiere_servicio_escolar
def tablero_profesores_destacados(request):
    from django.db.models import Avg, Count, Max, Min, Q
    from django.utils import timezone
    from datetime import timedelta

    # Filtros para el período (últimos 6 meses)
    fecha_limite = timezone.now() - timedelta(days=180)

    # Obtenemos profesores con métricas completas
    profesores = Profesor.objects.annotate(
        num_retroalimentaciones=Count(
            'retroalimentaciones_recibidas',
            filter=Q(
                retroalimentaciones_recibidas__completada=True,
                retroalimentaciones_recibidas__fecha_respuesta__gte=fecha_limite
            )
        ),
        promedio_calificacion=Avg(
            'retroalimentaciones_recibidas__respuestas__valor_numero',
            filter=Q(
                retroalimentaciones_recibidas__completada=True,
                retroalimentaciones_recibidas__respuestas__pregunta__tipo='escala_5',
                retroalimentaciones_recibidas__fecha_respuesta__gte=fecha_limite
            )
        ),
        max_calificacion=Max(
            'retroalimentaciones_recibidas__respuestas__valor_numero',
            filter=Q(
                retroalimentaciones_recibidas__completada=True,
                retroalimentaciones_recibidas__respuestas__pregunta__tipo='escala_5'
            )
        ),
        min_calificacion=Min(
            'retroalimentaciones_recibidas__respuestas__valor_numero',
            filter=Q(
                retroalimentaciones_recibidas__completada=True,
                retroalimentaciones_recibidas__respuestas__pregunta__tipo='escala_5'
            )
        ),
        num_padres_distintos=Count(
            'retroalimentaciones_recibidas__cita__solicitante',
            filter=Q(retroalimentaciones_recibidas__completada=True),
            distinct=True
        )
    ).filter(
        num_retroalimentaciones__gte=5  # Solo profesores con mínimo 5 evaluaciones
    ).exclude(
        promedio_calificacion__isnull=True  # Excluir profesores sin calificaciones válidas
    ).order_by('-promedio_calificacion')[:10]  # Top 10 mejor calificados

    # Obtener comentarios para cada profesor
    profesores_con_comentarios = []
    for profesor in profesores:
        comentarios = RespuestaRetroalimentacion.objects.filter(
            retroalimentacion_aplicada__profesor=profesor,
            retroalimentacion_aplicada__completada=True,
            pregunta__tipo__in=['texto', 'si_no_explicacion'],
            respuesta_texto__isnull=False
        ).exclude(respuesta_texto='').values_list('respuesta_texto', flat=True)[:5]

        profesores_con_comentarios.append({
            'profesor': profesor,
            'promedio_calificacion': profesor.promedio_calificacion,
            'num_retroalimentaciones': profesor.num_retroalimentaciones,
            'max_calificacion': profesor.max_calificacion,
            'min_calificacion': profesor.min_calificacion,
            'num_padres_distintos': profesor.num_padres_distintos,
            'comentarios': list(comentarios),
        })

    # Calcular estadísticas generales
    if profesores:
        promedio_general = sum(p.promedio_calificacion for p in profesores) / len(profesores)
    else:
        promedio_general = 0

    context = {
        'profesores': profesores_con_comentarios,
        'titulo': 'Profesores Destacados',
        'subtitulo': 'Reconocimiento por excelente retroalimentación',
        'promedio_general': promedio_general,
        'total_evaluaciones': sum(p['num_retroalimentaciones'] for p in profesores_con_comentarios),
        'periodo': 'Últimos 6 meses',
        'fecha_limite': fecha_limite.date()
    }

    return render(
        request,
        'formularios/tableros/tablero_profesores_destacados.html',
        context
    )


class PanelMetricasView(TemplateView):
    template_name = 'formularios/tableros/panel_metricas.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('credenciales'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('servicios_escolares:login')

        try:
            self.servicio_escolar = ServicioEscolar.objects.get(
                id=request.session['credenciales']['id'],
                estado_cuenta='Activo'
            )
        except ServicioEscolar.DoesNotExist:
            messages.error(request, 'Usuario no encontrado o cuenta inactiva')
            return redirect('servicios_escolares:logout')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['metricas'] = obtener_metricas_satisfaccion(self.servicio_escolar)
        context['titulo_pagina'] = "Panel de Métricas de Satisfacción"
        context['periodo_actual'] = "Últimos 30 días"

        return context


'''
@requiere_servicio_escolar
def tablero_profesores_destacados(request):
    from django.shortcuts import render
    from django.db.models import Avg, Count
    from profesores.models import Profesor
    # Obtenemos profesores con al menos 5 retroalimentaciones completadas
    profesores = Profesor.objects.annotate(
        num_retroalimentaciones=Count(
            'retroalimentaciones_recibidas',
            filter=Q(retroalimentaciones_recibidas__completada=True)
        ),
        promedio_calificacion=Avg(
            'retroalimentaciones_recibidas__respuestas__valor_numero',
            filter=Q(
                retroalimentaciones_recibidas__completada=True,
                retroalimentaciones_recibidas__respuestas__pregunta__tipo='escala_5'
            )
        )
    ).filter(
        num_retroalimentaciones__gte=5  # Solo profesores con mínimo 5 evaluaciones
    ).order_by('-promedio_calificacion')[:10]  # Top 10 mejor calificados

    context = {
        'profesores': profesores,
        'titulo': 'Profesores Destacados',
        'subtitulo': 'Reconocimiento por excelente retroalimentación'
    }
    return render(request,
                  'formularios/tableros/tablero_profesores_destacados.html', context)
'''


@requiere_servicio_o_profesor
def retroalimentaciones_profesores(request):
    # Obtener todos los profesores con retroalimentaciones
    profesores = Profesor.objects.filter(
        retroalimentaciones_recibidas__completada=True
    ).distinct().order_by('nombre_completo')

    # Paginación de profesores (10 por página)
    paginator = Paginator(profesores, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'titulo': 'Retroalimentaciones de Profesores',
        'subtitulo': 'Evaluaciones recibidas por cada profesor',
        'tipo': 'profesor'
    }
    return render(request, 'formularios/retroalimentacion/lista_retroalimentaciones.html', context)


@requiere_servicio_o_profesor
def detalle_retroalimentaciones_profesor(request, profesor_id):
    profesor = Profesor.objects.get(id=profesor_id)

    # Obtener todas las retroalimentaciones completadas para este profesor
    retroalimentaciones = RetroalimentacionAplicada.objects.filter(
        profesor=profesor,
        completada=True
    ).select_related('cita__solicitante').prefetch_related('respuestas').order_by('-fecha_respuesta')

    # Paginación de retroalimentaciones (5 por página)
    paginator = Paginator(retroalimentaciones, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Calcular estadísticas
    promedio = retroalimentaciones.aggregate(
        avg=Avg('respuestas__valor_numero', filter=Q(respuestas__pregunta__tipo='escala_5'))
    )['avg'] or 0

    context = {
        'profesor': profesor,
        'page_obj': page_obj,
        'promedio': promedio,
        'total_evaluaciones': retroalimentaciones.count(),
        'titulo': f'Retroalimentaciones de {profesor.nombre_completo}',
        'subtitulo': 'Detalle de todas las evaluaciones recibidas',
        'tipo': 'profesor'
    }
    return render(request, 'formularios/retroalimentacion/detalle_retroalimentaciones.html', context)


@requiere_servicio_escolar
def retroalimentaciones_servicio_escolar(request):
    # Obtener todas las retroalimentaciones completadas para servicio escolar
    retroalimentaciones = RetroalimentacionAplicada.objects.filter(
        profesor__isnull=True,
        completada=True
    ).select_related('cita__solicitante').order_by('-fecha_respuesta')

    # Paginación (15 por página)
    paginator = Paginator(retroalimentaciones, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Calcular estadísticas
    promedio = retroalimentaciones.aggregate(
        avg=Avg('respuestas__valor_numero', filter=Q(respuestas__pregunta__tipo='escala_5'))
    )['avg'] or 0

    context = {
        'page_obj': page_obj,
        'promedio': promedio,
        'total_evaluaciones': retroalimentaciones.count(),
        'titulo': 'Retroalimentaciones de Servicio Escolar',
        'subtitulo': 'Evaluaciones recibidas por el servicio escolar',
        'tipo': 'servicio'
    }
    return render(request, 'formularios/retroalimentacion/lista_retroalimentaciones.html', context)
