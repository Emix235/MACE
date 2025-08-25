from django import template
from urllib.parse import urlparse

register = template.Library()


@register.filter
def urlparse(value):
    return urlparse(value)
