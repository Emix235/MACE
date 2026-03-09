# preguntas/templatetags/faq_extras.py
from django import template
from ..utils import get_user_role_and_base, get_user_role_display

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Filtro para acceder a diccionarios en templates"""
    return dictionary.get(key, key)


@register.filter
def get_role_display(role):
    """Filtro para mostrar nombre del rol"""
    role_display = {
        'padre': 'Padre/Madre de Familia',
        'profesor': 'Profesor',
        'servicio': 'Servicio Escolar',
        'general': 'General',
    }
    return role_display.get(role, role.capitalize())


@register.simple_tag(takes_context=True)
def get_user_role(context):
    request = context['request']
    user, role, base_template, _ = get_user_role_and_base(request)
    return role


@register.simple_tag(takes_context=True)
def get_user_role_display_tag(context):
    request = context['request']
    user, role, base_template, _ = get_user_role_and_base(request)
    return get_user_role_display(role) if role else "Usuario"
