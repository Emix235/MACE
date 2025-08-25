from django import template

register = template.Library()


@register.filter
def zip_lists(a, b):
    return zip(a, b)


@register.filter
def index(sequence, i):
    return sequence[i]


@register.filter
def multiply(value, arg):
    try:
        if value is None or arg is None:
            return 0
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter(name='subtract')
def subtract(value, arg):
    """Resta arg de value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def first_escala_5(respuestas):
    """Obtiene la primera respuesta de tipo escala_5"""
    for respuesta in respuestas:
        if respuesta.pregunta.tipo == 'escala_5' and respuesta.valor_numero is not None:
            return respuesta.valor_numero
    return 0


@register.filter
def first_texto(respuestas):
    """Obtiene la primera respuesta de tipo texto"""
    for respuesta in respuestas:
        if respuesta.pregunta.tipo == 'texto' and respuesta.respuesta_texto:
            return respuesta.respuesta_texto
    return ""


@register.filter
def avg_calificacion(retroalimentaciones):
    """Calcula el promedio de calificaciones"""
    total = 0
    count = 0
    for retro in retroalimentaciones:
        for respuesta in retro.respuestas.all():
            if respuesta.pregunta.tipo == 'escala_5' and respuesta.valor_numero is not None:
                total += respuesta.valor_numero
                count += 1
    return total / count if count > 0 else 0


@register.filter
def es_si_no(tipo):
    return tipo in ['si_no', 'si_no_explicacion']
