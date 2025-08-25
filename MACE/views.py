from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
import json
from .forms import EstiloUsuarioForm, ConfiguracionEstilosForm


def get_user_model(request):
    """Función auxiliar para obtener el modelo de usuario correcto"""
    if hasattr(request, 'profesor'):  # Si estás usando request.profesor
        return request.profesor
    elif hasattr(request, 'padre'):
        return request.padre
    elif hasattr(request, 'servicioescolar'):
        return request.servicioescolar
    return None
