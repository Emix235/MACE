from itertools import groupby
from operator import attrgetter
from django import template

register = template.Library()


@register.filter(name='subtract')
def subtract(value, arg):
    """Resta arg de value"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value


@register.filter(name='filter_profesores_por_grupo')
def filter_profesores_por_grupo(profesores, grupo_id):
    return [p for p in profesores if any(clase.grupo.id == grupo_id for clase in p.clases.all())]


@register.filter(name='unique_by_field')
def unique_by_field(queryset, field_name):
    """Filtra elementos únicos por un campo específico"""
    seen = set()
    unique_items = []
    for item in queryset:
        field_value = getattr(item, field_name)
        if field_value not in seen:
            seen.add(field_value)
            unique_items.append(item)
    return unique_items


@register.filter
def group_by_field(queryset, field_name):
    """Agrupa elementos por un campo específico"""
    return groupby(sorted(queryset, key=attrgetter(field_name)), key=attrgetter(field_name))


@register.filter
def zip_lists(a, b):
    return zip(a, b)


@register.filter
def index(sequence, i):
    return sequence[i]


@register.filter
def zip(a, b):
    return zip(a, b)
