from django import template

register = template.Library()


@register.filter
def multiply(value, arg):
    """Multiplica el valor por el argumento"""
    return float(value) * float(arg)


@register.filter
def divide(value, arg):
    """Divide el valor por el argumento"""
    if float(arg) == 0:
        return 0
    return float(value) / float(arg)
