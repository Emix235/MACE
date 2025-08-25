# padres/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from servicios_escolares.models import ServicioEscolar
from notificaciones.models import Notification


@receiver(post_save, sender='padres.Padre')  # Usamos string para evitar imports circulares
def notificar_registro_padre(sender, instance, created, **kwargs):
    """
    Notifica a todos los servicios escolares cuando un padre se registra
    """
    if created:
        # Obtener todos los servicios escolares
        servicios_escolares = ServicioEscolar.objects.all()

        # Obtener content types
        servicio_escolar_ct = ContentType.objects.get_for_model(ServicioEscolar)
        padre_ct = ContentType.objects.get_for_model(instance)

        # Crear notificaciones para cada servicio escolar
        for servicio_escolar in servicios_escolares:
            Notification.objects.create(
                recipient_ct=servicio_escolar_ct,
                recipient_id=servicio_escolar.id,
                event_type='registro_padre',
                title='Nuevo registro de padre',
                message=f'El padre {instance.nombre_completo} se ha registrado en el sistema',
                target_ct=padre_ct,
                target_id=instance.id,
                variable_1=instance.nombre_completo,  # Nombre del padre
                variable_2=instance.correo_electronico  # Email del padre
            )