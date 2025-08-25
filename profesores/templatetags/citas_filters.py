from django import template
from django.contrib.contenttypes.models import ContentType

register = template.Library()


@register.filter
def filter_creadas_por_profesor(citas, profesor):
    profesor_ct = ContentType.objects.get_for_model(profesor.__class__)
    try:
        return citas.filter(creador_tipo=profesor_ct, creador_id=profesor.id)
    except AttributeError:
        # citas es una lista, no un QuerySet
        return [c for c in citas if
                getattr(c, 'creador_tipo', None) == profesor_ct and getattr(c, 'creador_id', None) == profesor.id]


@register.filter
def filter_solicitadas_por_padres(citas, profesor):
    from padres.models import Padre
    padre_ct = ContentType.objects.get_for_model(Padre)
    try:
        return citas.filter(profesor=profesor, creador_tipo=padre_ct)
    except AttributeError:
        return [c for c in citas if
                getattr(c, 'profesor', None) == profesor and getattr(c, 'creador_tipo', None) == padre_ct]


@register.filter
def filter_solicitadas_por_padres_y_no_creadas(citas, profesor):
    try:
        return citas.exclude(creador_id=profesor.id).filter(profesor=profesor)
    except AttributeError:
        return [c for c in citas if
                getattr(c, 'profesor', None) == profesor and getattr(c, 'creador_id', None) != profesor.id]
