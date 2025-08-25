from audioop import reverse
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.shortcuts import redirect
from django.views import generic
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, TemplateView

from padres.models import Padre
from profesores.models import Profesor
from servicios_escolares.models import ServicioEscolar
from .models import Notification, NotificationTemplate


class PanelNotificacionesView(generic.TemplateView):
    template_name = 'servicios_escolares/notificaciones/panel_tipos_notificaciones.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('credenciales'):
            messages.warning(request, 'Debes iniciar sesión primero')
            return redirect('servicios_escolares:login')

        try:
            self.servicio_escolar = ServicioEscolar.objects.get(
                id=request.session['credenciales']['id']
            )
        except (ServicioEscolar.DoesNotExist, KeyError):
            messages.error(request, 'Error de autenticación')
            return redirect('servicios_escolares:logout')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        servicio_ct = ContentType.objects.get_for_model(ServicioEscolar)

        # Tipos de notificación específicos para servicio escolar
        tipos_a_mostrar = [
            'registro_padre',
            'servicio_nuevo_profesor',
        ]

        tipos_notificaciones = []

        for event_key in tipos_a_mostrar:
            event_data = Notification.EVENT_TYPES.get(event_key)
            if not event_data:
                continue

            try:
                # Filtrar notificaciones para este servicio escolar
                notificaciones = Notification.objects.filter(
                    event_type=event_key,
                    recipient_ct=servicio_ct,
                    recipient_id=self.servicio_escolar.id
                )

                # Obtener URL base sin argumentos
                url_base = event_data[0].split(':')[0]  # Ej: 'servicios_escolares'
                try:
                    # Intentar obtener la URL sin argumentos primero
                    url_destino = reverse(f"{url_base}:dashboard")
                except:
                    try:
                        # Si falla, usar la URL del evento sin argumentos
                        url_destino = reverse(event_data[0].split(':')[0] + ":dashboard")
                    except:
                        # Último recurso: dashboard general
                        url_destino = reverse('servicios_escolares:dashboard')

                tipo = {
                    'codigo': event_key,
                    'nombre': event_data[1],
                    'url_destino': url_destino,
                    'total': notificaciones.count(),
                    'no_leidas': notificaciones.filter(is_read=False).count(),
                    'ultima_semana': notificaciones.filter(
                        created_at__gte=timezone.now() - timezone.timedelta(days=7)
                    ).count(),
                    'destinos_comunes': notificaciones
                                        .exclude(target_ct__isnull=True)
                                        .values('target_ct__model')
                                        .annotate(total=Count('target_ct'))
                                        .order_by('-total')[:3]
                }
                tipos_notificaciones.append(tipo)
            except Exception as e:
                print(f"Error procesando {event_key}: {str(e)}")
                continue

        context.update({
            'servicio_escolar': self.servicio_escolar,
            'tipos': sorted(tipos_notificaciones, key=lambda x: x['no_leidas'], reverse=True),
            'total_general': Notification.objects.filter(
                recipient_ct=servicio_ct,
                recipient_id=self.servicio_escolar.id
            ).count()
        })

        return context

    def _generate_notification_url(self, url_name, event_key):
        """Genera URLs de notificación de manera segura con manejo de excepciones"""
        try:
            # URLs que necesitan argumentos específicos
            if event_key == 'custom':
                return reverse(url_name, args=[self.servicio_escolar.id])

            # URLs para notificaciones con targets
            if hasattr(self, 'target') and self.target:
                try:
                    return reverse(url_name, args=[self.target.id])
                except:
                    pass

            # Versión sin argumentos por defecto
            return reverse(url_name)

        except Exception as e:
            print(f"Error generando URL para {url_name}: {str(e)}")
            return reverse('servicios_escolares:dashboard')


class CrearPlantillaView(CreateView):
    model = NotificationTemplate
    fields = ['nombre', 'descripcion', 'destinatarios', 'plantilla_mensaje']
    template_name = 'servicios_escolares/notificaciones/crear_plantilla.html'

    def form_valid(self, form):
        # Asignar el creador según tipo de usuario
        user = self.request.user
        form.instance.creador_type = ContentType.objects.get_for_model(user)
        form.instance.creador_id = user.id

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['variables_disponibles'] = {
            'usuario': "Nombre del destinatario",
            'fecha': "Fecha actual",
            'detalle': "Información específica del evento"
        }
        return context


class PanelServiciosEscolaresView(generic.ListView):
    template_name = 'servicios_escolares/notificaciones/panel_notificaciones.html'
    context_object_name = 'notificaciones'
    paginate_by = 15

    def dispatch(self, request, *args, **kwargs):
        # 1. Verificación de autenticación
        if not request.session.get('credenciales'):
            print("[DEBUG] No hay sesión activa - Redirigiendo a login")
            messages.error(request, 'Debes iniciar sesión primero')
            return redirect('servicios_escolares:login')

        # 2. Obtener el servicio escolar actual
        try:
            self.servicio_escolar = ServicioEscolar.objects.get(
                id=request.session['credenciales']['id'],
                estado_cuenta='Activo'
            )
            print(f"[DEBUG] Servicio escolar autenticado: {self.servicio_escolar}")

        except ServicioEscolar.DoesNotExist:
            print("[DEBUG] Error: ServicioEscolar no existe o cuenta no activa")
            messages.error(request, 'Error de autenticación')
            return redirect('servicios_escolares:logout')

        except KeyError:
            print("[DEBUG] Error: KeyError al acceder a credenciales")
            messages.error(request, 'Error de autenticación')
            return redirect('servicios_escolares:logout')

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        content_type = ContentType.objects.get_for_model(ServicioEscolar)

        queryset = Notification.objects.filter(
            recipient_ct=content_type,
            recipient_id=self.servicio_escolar.id
        ).order_by('-created_at')

        # Aplicar filtros
        estado = self.request.GET.get('estado')
        tipo = self.request.GET.get('tipo')

        if estado == 'leidas':
            queryset = queryset.filter(is_read=True)
        elif estado == 'no_leidas':
            queryset = queryset.filter(is_read=False)

        if tipo and tipo in dict(Notification.EVENT_CHOICES):
            queryset = queryset.filter(event_type=tipo)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            'servicio': self.servicio_escolar,
            'total_notificaciones': self.get_queryset().count(),
            'no_leidas_count': self.get_queryset().filter(is_read=False).count(),
            'tipos_notificaciones': Notification.EVENT_CHOICES,
            'filtro_actual': {
                'estado': self.request.GET.get('estado', 'todas'),
                'tipo': self.request.GET.get('tipo', 'todas')
            }
        })
        return context


@csrf_exempt
@require_POST
def marcar_notificacion_leida(request, notification_id):
    if not (request.session.get('credenciales') or
            request.session.get('credenciales_padre') or
            request.session.get('credenciales_profesor')):
        return JsonResponse({'status': 'error', 'message': 'No autenticado'}, status=401)

    try:
        # Obtener el usuario según su tipo
        user_obj = None

        if 'credenciales_padre' in request.session:
            user_obj = Padre.objects.get(id=request.session['credenciales_padre']['id'])
        elif 'credenciales_profesor' in request.session:
            user_obj = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        elif 'credenciales' in request.session:
            user_obj = ServicioEscolar.objects.get(id=request.session['credenciales']['id'])

        # Marcar una notificación específica recibida como leída
        notificacion = Notification.objects.get(
            id=notification_id,
            recipient_id=user_obj.id,
            is_read=False
        )
        notificacion.mark_as_read()

        # Actualizar valores en la sesión
        if 'notificaciones_no_leidas' in request.session:
            request.session['notificaciones_no_leidas'] = max(0, request.session['notificaciones_no_leidas'] - 1)

        if 'notificaciones_recientes' in request.session:
            request.session['notificaciones_recientes'] = [
                n for n in request.session['notificaciones_recientes']
                if n['id'] != notification_id
            ]

        request.session.modified = True

        return JsonResponse({
            'status': 'success',
            'nuevo_contador': request.session.get('notificaciones_no_leidas', 0),
            'notification_id': notification_id
        })

    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notificación no encontrada o ya leída'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


'''
@csrf_exempt
@require_POST
def marcar_notificacion_leida(request, notification_id):
    # Verificación básica
    if not request.session.get('credenciales_padre') and not request.session.get(
            'credenciales_profesor') and not request.session.get('credenciales'):
        return JsonResponse({'status': 'error', 'message': 'No autenticado'}, status=401)

    try:
        # Identificar usuario
        if 'credenciales_padre' in request.session:
            user = Padre.objects.get(id=request.session['credenciales_padre']['id'])
        elif 'credenciales_profesor' in request.session:
            user = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        else:
            user = ServicioEscolar.objects.get(id=request.session['credenciales']['id'])

        content_type = ContentType.objects.get_for_model(user)

        # Marcar una notificación específica
        Notification.objects.filter(
            id=notification_id,
            recipient_ct=content_type,
            recipient_id=user.id
        ).update(is_read=True)

        # Obtener nuevo contador
        nuevo_contador = Notification.objects.filter(
            recipient_ct=content_type,
            recipient_id=user.id,
            is_read=False
        ).count()

        return JsonResponse({
            'status': 'success',
            'nuevo_contador': nuevo_contador
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
'''


class NotificationTypesView(TemplateView):
    template_name = 'servicios_escolares/notificaciones/panel_tipos_notificaciones.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Estadísticas generales
        context['total_notificaciones'] = Notification.objects.count()
        context['total_leidas'] = Notification.objects.filter(is_read=True).count()
        context['total_no_leidas'] = Notification.objects.filter(is_read=False).count()

        # Notificaciones de la última semana
        last_week = timezone.now() - timedelta(days=7)
        context['total_ultima_semana'] = Notification.objects.filter(
            created_at__gte=last_week
        ).count()

        # Obtener estadísticas por tipo de notificación
        event_types = Notification.EVENT_TYPES
        tipos_data = []

        for event_type, event_data in event_types.items():
            # Consultas para cada tipo
            total = Notification.objects.filter(event_type=event_type).count()
            no_leidas = Notification.objects.filter(
                event_type=event_type,
                is_read=False
            ).count()

            ultima_semana = Notification.objects.filter(
                event_type=event_type,
                created_at__gte=last_week
            ).count()

            tipos_data.append({
                'tipo': (event_type, event_data[1]),  # (codigo, nombre)
                'url': event_data[0],  # url destino
                'rol': event_data[2] if len(event_data) > 2 else 'todos',
                'total': total,
                'no_leidas': no_leidas,
                'ultima_semana': ultima_semana
            })

        # Organizar por categorías
        categorias = {
            'Padres': [],
            'Profesores': [],
            'Servicio Escolar': [],
            'Generales': []
        }

        for tipo in tipos_data:
            if 'padre_' in tipo['tipo'][0]:
                categorias['Padres'].append(tipo)
            elif 'profesor_' in tipo['tipo'][0]:
                categorias['Profesores'].append(tipo)
            elif 'servicio_' in tipo['tipo'][0] or 'registro_' in tipo['tipo'][0]:
                categorias['Servicio Escolar'].append(tipo)
            else:
                categorias['Generales'].append(tipo)

        # Estadísticas por categoría
        stats_categorias = {}
        for categoria, items in categorias.items():
            stats_categorias[categoria] = {
                'total': sum(item['total'] for item in items),
                'no_leidas': sum(item['no_leidas'] for item in items),
                'ultima_semana': sum(item['ultima_semana'] for item in items)
            }

        context['tipos_notificaciones'] = categorias
        context['stats_categorias'] = stats_categorias

        return context


@csrf_exempt
@require_POST
def marcar_todas_leidas(request):
    if not (request.session.get('credenciales') or
            request.session.get('credenciales_padre') or
            request.session.get('credenciales_profesor')):
        return JsonResponse({'status': 'error', 'message': 'No autenticado'}, status=401)

    try:
        # Obtener el usuario según su tipo
        user_obj = None

        if 'credenciales_padre' in request.session:
            user_obj = Padre.objects.get(id=request.session['credenciales_padre']['id'])
        elif 'credenciales_profesor' in request.session:
            user_obj = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        elif 'credenciales' in request.session:
            user_obj = ServicioEscolar.objects.get(id=request.session['credenciales']['id'])

        # Marcar todas las notificaciones recibidas como leídas
        count = Notification.objects.filter(
            recipient_id=user_obj.id,
            is_read=False
        ).update(is_read=True)

        # Actualizar valores en la sesión
        request.session['notificaciones_no_leidas'] = 0
        request.session['notificaciones_recientes'] = []
        request.session.modified = True

        return JsonResponse({
            'status': 'success',
            'marcadas': count,
            'nuevo_contador': 0
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


'''
@csrf_exempt
@require_POST
def marcar_todas_leidas(request):
    # Verificación simple de sesión
    if not any(k in request.session for k in ['credenciales_padre', 'credenciales_profesor', 'credenciales']):
        return JsonResponse({'status': 'error', 'message': 'No autenticado'}, status=401)

    try:
        # Obtener usuario según tipo
        if 'credenciales_padre' in request.session:
            user = Padre.objects.get(id=request.session['credenciales_padre']['id'])
        elif 'credenciales_profesor' in request.session:
            user = Profesor.objects.get(id=request.session['credenciales_profesor']['id'])
        else:
            user = ServicioEscolar.objects.get(id=request.session['credenciales']['id'])

        content_type = ContentType.objects.get_for_model(user)

        # Actualización directa en BD
        count = Notification.objects.filter(
            recipient_ct=content_type,
            recipient_id=user.id,
            is_read=False
        ).update(is_read=True)

        return JsonResponse({
            'status': 'success',
            'marcadas': count,
            'nuevo_contador': 0
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
'''



