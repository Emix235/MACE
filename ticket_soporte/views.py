from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import View, ListView
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.contrib import messages

from notificaciones.models import Notification
from profesores.models import Profesor
from servicios_escolares.models import ServicioEscolar
from .models import TicketSoporte
from padres.models import Padre
from .forms import TicketSoporteForm
import json


def crear_notificacion_ticket(ticket, creador, user_type):
    servicio_escolar_ct = ContentType.objects.get_for_model(ServicioEscolar)
    destinatarios = ServicioEscolar.objects.filter(estado_cuenta='Activo')

    # Mapear qué tipo de event_type usar
    event_type_mapping = {
        'padre': 'servicio_ticket_padre',
        'profesor': 'servicio_ticket_profesor',
        # 'servicio': 'servicio_ticket',
    }

    event_type = event_type_mapping.get(user_type, 'servicio_ticket')  # Default de seguridad

    for destinatario in destinatarios:
        Notification.objects.create(
            recipient_ct=servicio_escolar_ct,
            recipient_id=destinatario.id,
            event_type=event_type,
            title=f'Nuevo ticket de {ticket.get_tipo_usuario_display()}',
            message=f"Asunto: {ticket.asunto}",
            rol_destinatario='servicio',
            target_ct=ContentType.objects.get_for_model(TicketSoporte),
            target_id=ticket.id
        )

    # Crear notificación opcional para el creador del ticket
    if user_type != 'servicio':
        creator_ct = ContentType.objects.get_for_model(creador.__class__)

        # Definir los mensajes según el tipo de usuario
        if user_type == 'profesor':
            event_type = 'profesor_ticket'
            title = 'Nuevo ticket de soporte'
        elif user_type == 'padre':
            event_type = 'padre_ticket'
            title = 'Nuevo ticket de soporte'
        else:
            event_type = 'custom'
            title = 'Ticket creado'

        Notification.objects.create(
            recipient_ct=creator_ct,
            recipient_id=creador.id,
            event_type=event_type,
            title=title,
            message=f"Tu ticket #{ticket.id} ha sido registrado",
            rol_destinatario=user_type,
            target_ct=ContentType.objects.get_for_model(TicketSoporte),
            target_id=ticket.id
        )


class CrearTicketSoporteView(View):
    def post(self, request):
        user_type = None
        user_obj = None

        if 'credenciales_padre' in request.session:
            user_type = 'padre'
            try:
                user_obj = Padre.objects.get(id=request.session['credenciales_padre']['id'])
            except (Padre.DoesNotExist, KeyError):
                return JsonResponse({'success': False, 'message': 'Sesión inválida'}, status=401)

        elif 'credenciales_profesor' in request.session:
            user_type = 'profesor'
            try:
                user_obj = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
            except (Profesor.DoesNotExist, KeyError):
                return JsonResponse({'success': False, 'message': 'Sesión inválida'}, status=401)

        elif 'credenciales' in request.session:
            user_type = 'servicio'
            try:
                user_obj = ServicioEscolar.objects.get(
                    id=request.session['credenciales']['id'],
                    estado_cuenta='Activo'
                )
            except (ServicioEscolar.DoesNotExist, KeyError):
                return JsonResponse({'success': False, 'message': 'Sesión inválida'}, status=401)

        if not user_type:
            return JsonResponse({'success': False, 'message': 'Debes iniciar sesión'}, status=403)

        # Procesar formulario
        form_data = {
            'asunto': request.POST.get('asunto'),
            'descripcion': request.POST.get('descripcion')
        }
        form = TicketSoporteForm(form_data)

        if form.is_valid():
            ticket = form.save(commit=False)
            # Asegúrate de que estás recibiendo el current_url
            print("URL recibida en el backend:", request.POST.get('current_url'))

            # Usa el current_url si está disponible, si no, usa HTTP_REFERER
            ticket.url_pagina = request.POST.get('current_url') or \
                                request.META.get('HTTP_REFERER', '/')
            print('URL que se guardará:', ticket.url_pagina)
            ticket.tipo_usuario = user_type
            ticket.usuario_ct = ContentType.objects.get_for_model(user_obj.__class__)
            ticket.usuario_id = user_obj.id
            ticket.user_agent = request.META.get('HTTP_USER_AGENT', '')
            ticket.save()

            # Crear notificación para el servicio escolar
            crear_notificacion_ticket(ticket, user_obj, user_type)

            return JsonResponse({'success': True, 'message': 'Ticket creado exitosamente'})
        else:
            errors = {field: error[0] for field, error in form.errors.items()}
            return JsonResponse({
                'success': False,
                'message': 'Error en el formulario',
                'errors': errors
            }, status=400)


# Para Servicios Escolares, veran todos
class TodosTicketsView(ListView):
    model = TicketSoporte
    template_name = 'soporte/tickets.html'
    context_object_name = 'tickets'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        # Verificación de autenticación
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

    def get_queryset(self):
        queryset = TicketSoporte.objects.all().order_by('-creado_en')

        # Filtros adicionales
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)

        tipo_usuario = self.request.GET.get('tipo_usuario')
        if tipo_usuario:
            queryset = queryset.filter(tipo_usuario=tipo_usuario)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'estados': TicketSoporte.ESTADOS_TICKET,
            'tipos_usuario': TicketSoporte.TIPO_USUARIO_CHOICES,
            'servicio_escolar': self.servicio_escolar
        })
        return context


# Para el profesor
def panel_tickets_profesor(request):
    # Autenticación
    if not request.session.get('credenciales_profesor'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('profesores:login_profesor')

    try:
        profesor = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
    except Profesor.DoesNotExist:
        messages.error(request, 'Profesor no encontrado')
        return redirect('profesores:logout_profesor')

    # Obtener los tickets creados por el profesor
    profesor_ct = ContentType.objects.get_for_model(Profesor)
    tickets = TicketSoporte.objects.filter(
        usuario_ct=profesor_ct,
        usuario_id=profesor.id
    ).order_by('-creado_en')

    # Filtros
    estado_filtro = request.GET.get('estado')
    if estado_filtro and estado_filtro in dict(TicketSoporte.ESTADOS_TICKET).keys():
        tickets = tickets.filter(estado=estado_filtro)

    # Paginación
    paginator = Paginator(tickets, 10)  # 10 tickets por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Obtener todas las notificaciones del profesor
    notificaciones = profesor.get_notificaciones()
    # Filtrar las no leídas manualmente porque son dicts
    notificaciones_no_leidas = [n for n in notificaciones if not n['is_read']]

    # Tomar las 5 más recientes (ya depende del orden en get_notificaciones)
    notificaciones_recientes = notificaciones[:5]

    # Contar no leídas
    contador_no_leidas = len(notificaciones_no_leidas)

    context = {
        'profesor': profesor,
        'tickets': page_obj,
        'estados_ticket': TicketSoporte.ESTADOS_TICKET,
        'estado_filtro_actual': estado_filtro,
        'notificaciones_no_leidas': profesor.notificaciones_no_leidas(),
        'notificaciones_recientes': notificaciones_recientes,
        'contador_no_leidas': contador_no_leidas,
    }

    return render(request, 'soporte/tickets_profesor.html', context)
