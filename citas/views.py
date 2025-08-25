from citas.models import Cita, ModificacionCita
from notificaciones.models import Notification
from padres.models import Padre
from profesores.models import Profesor
from servicios_escolares.models import ServicioEscolar
from citas.forms import CancelarCitaForm, ReprogramarCitaForm
import sys
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Cita
from .forms import CancelarCitaForm

# Configuración global para manejar Unicode en prints
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def get_user_and_role(request):
    """
    Obtiene el usuario actual y su rol basado en la sesión.
    Devuelve (user, role) o redirige si no está autenticado.
    """
    user = None
    role = None

    if request.session.get('credenciales_padre'):
        user = get_object_or_404(Padre, id=request.session['credenciales_padre']['id'])
        role = 'padre'
    elif request.session.get('credenciales_profesor'):
        user = get_object_or_404(Profesor, id=request.session['credenciales_profesor']['id'])
        role = 'profesor'
    elif request.session.get('credenciales'):
        user = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])
        role = 'servicio'
    else:
        messages.warning(request, 'Debes iniciar sesión primero')
        return None, None, redirect('inicio')

    return user, role, None


def redirigir_segun_rol(role):
    """Función auxiliar para redirigir según el rol del usuario"""
    if role == 'padre':
        return redirect('padres:dashboard_padre')
    elif role == 'profesor':
        return redirect('profesores:dashboard_profesor')
    else:
        return redirect('servicios_escolares:dashboard')


# Las funciones get_user_and_role y redirigir_segun_rol se mantienen igual que las que ya tienes
def determinar_template_segun_rol(role):
    """
    Devuelve la ruta de la plantilla adecuada según el rol
    """
    templates = {
        'padre': 'padres/citas/cancelar_cita.html',
        'profesor': 'profesores/citas/cancelar_cita.html',
        'servicio': 'servicios_escolares/citas/cancelar_cita.html'
    }
    return templates.get(role, 'servicios_escolares/citas/cancelar_cita.html')


def cancelar_cita_view(request, cita_id):
    """
    Vista para cancelar una cita, compatible con múltiples roles de usuario
    """
    # Obtener usuario y rol
    user, role, redireccion = get_user_and_role(request)
    if redireccion:
        return redireccion

    # Obtener la cita
    cita = get_object_or_404(Cita, id=cita_id)

    # Verificar si ya está cancelada
    if cita.estado == 'cancelada':
        messages.info(request, 'La cita ya fue cancelada anteriormente.')
        return redirigir_segun_rol(role)

    # Procesar formulario si es POST
    if request.method == 'POST':
        form = CancelarCitaForm(request.POST)
        if form.is_valid():
            motivo = form.cleaned_data['motivo_cancelacion']

            # Actualizar cita
            cita.estado = 'cancelada'
            cita.motivo_cancelacion = motivo
            cita.save()

            messages.success(request, 'La cita ha sido cancelada exitosamente.')
            return redirigir_segun_rol(role)
        else:
            messages.error(request, 'Por favor llena el motivo de cancelación correctamente.')
    else:
        form = CancelarCitaForm()

    # Preparar contexto según el rol
    context = {
        'form': form,
        'cita': cita,
        'usuario': user,
        'rol': role,
        'titulo': 'Cancelar cita'
    }

    # Determinar la plantilla según el rol
    template_path = determinar_template_segun_rol(role)
    return render(request, template_path, context)


def reprogramar_cita_view(request, cita_id):
    # Verificación de usuario
    user = None
    role = None
    if request.session.get('credenciales_padre'):
        user = get_object_or_404(Padre, id=request.session['credenciales_padre']['id'])
        role = 'padre'
    elif request.session.get('credenciales_profesor'):
        user = get_object_or_404(Profesor, id=request.session['credenciales_profesor']['id'])
        role = 'profesor'
    elif request.session.get('credenciales'):
        user = get_object_or_404(ServicioEscolar, id=request.session['credenciales']['id'])
        role = 'servicio'
    else:
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('inicio')

    cita = get_object_or_404(Cita, id=cita_id)

    if request.method == 'POST':
        form = ReprogramarCitaForm(request.POST, instance=cita)
        if form.is_valid():
            # Guardar cambios y registrar la modificación
            cita_modificada = form.save(commit=False)
            motivo = form.cleaned_data['motivo_reprogramacion']

            # Crear registro de modificación
            ModificacionCita.objects.create(
                cita=cita,
                usuario=user,
                campo_modificado='Reprogramación',
                valor_anterior=f"Fecha: {cita.fecha_hora_inicio}, Duración: {cita.duracion}",
                valor_nuevo=f"Fecha: {cita_modificada.fecha_hora_inicio}, Duración: {cita_modificada.duracion}",
                motivo=motivo
            )

            # Actualizar motivo de la cita incluyendo el historial
            cita_modificada.motivo = f"{cita.motivo}\n\n--- REPROGRAMACIÓN ---\nMotivo: {motivo}\nNueva fecha: {cita_modificada.fecha_hora_inicio}"
            cita_modificada.save()

            # Notificar a los involucrados
            destinatarios = [cita.profesor, cita.solicitante]
            if cita.servicio_escolar:
                destinatarios.append(cita.servicio_escolar)

            for destinatario in set(d for d in destinatarios if d is not None and d != user):
                Notification.crear_notificacion_cita(
                    event_type='cita_reprogramada',
                    sender=user,
                    recipient=destinatario,
                    message=f"La cita '{cita.titulo}' ha sido reprogramada para el {cita_modificada.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M')}. Motivo: {motivo}",
                    target=cita_modificada
                )

            messages.success(request, 'Cita reprogramada exitosamente')

            if role == 'padre':
                return redirect('padres:mis_citas')
            elif role == 'profesor':
                return redirect('profesores:panel_citas')
            else:
                return redirect('servicios_escolares:panel_citas')
    else:
        form = ReprogramarCitaForm(instance=cita)

    context = {
        'form': form,
        'cita': cita,
        'role': role,
        'titulo': 'Reprogramar Cita'
    }

    template_map = {
        'padre': 'padres/citas/reprogramar_cita.html',
        'profesor': 'profesores/citas/reprogramar_cita.html',
        'servicio': 'servicios_escolares/citas/reprogramar_cita.html'
    }

    return render(request, template_map[role], context)



