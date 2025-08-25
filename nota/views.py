from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Nota
from .forms import NotaForm
from .utils import get_user_role_and_base

# Mapeo de plantillas específicas (sin incluir la extensión)
TEMPLATE_MAP = {
    'crear_nota': 'notas/crear_nota.html',
    'lista_notas': 'notas/lista_notas.html',
    'detalle_nota': 'notas/detalle_nota.html',
    'confirmar_eliminar': 'notas/confirmar_eliminar.html'
}


def crear_nota(request):
    user, role, base_template, redirect_response, _ = get_user_role_and_base(request)
    if redirect_response:
        return redirect_response

    if request.method == 'POST':
        form = NotaForm(request.POST, request.FILES)
        if form.is_valid():
            nota = form.save(commit=False)

            # Asignar el creador según el tipo de usuario
            if role == 'padre':
                nota.creador_padre = user
            elif role == 'profesor':
                nota.creador_profesor = user
            elif role == 'servicio':
                nota.creador_servicio = user

            nota.save()
            messages.success(request, 'Nota creada exitosamente!')
            return redirect('notas:lista_notas')
    else:
        form = NotaForm()

    context = {
        'form': form,
        'usuario': user,
        'rol': role,
        'titulo': 'Crear nueva nota',
        'base_template': base_template
    }
    return render(request, TEMPLATE_MAP['crear_nota'], context)


def lista_notas(request):
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)
    notas_enviadas = ''
    notas_recibidas = ''
    if redirect_response:
        return redirect_response

    # Obtener notas según el tipo de usuario
    if role == 'padre':
        notas_enviadas = Nota.objects.filter(creador_padre=user)
        notas_recibidas = Nota.objects.filter(destinatario_padre=user)
    elif role == 'profesor':
        notas_enviadas = Nota.objects.filter(creador_profesor=user)
        notas_recibidas = Nota.objects.filter(destinatario_profesor=user)
    elif role == 'servicio':
        notas_enviadas = Nota.objects.filter(creador_servicio=user)
        notas_recibidas = Nota.objects.filter(destinatario_servicio=user)

    context = {
        'notas_enviadas': notas_enviadas.order_by('-fecha_creacion'),
        'notas_recibidas': notas_recibidas.order_by('-fecha_creacion'),
        'usuario': user,
        'rol': role,
        'titulo': 'Mis notas',
        'base_template': base_template
    }
    context.update(extra_context)  # Añade el contexto adicional
    return render(request, TEMPLATE_MAP['lista_notas'], context)


def detalle_nota(request, pk):
    user, role, base_template, redirect_response, extra_context = get_user_role_and_base(request)
    if redirect_response:
        return redirect_response

    nota = get_object_or_404(Nota, pk=pk)

    context = {
        'nota': nota,
        'usuario': user,
        'rol': role,
        'titulo': 'Detalle de nota',
        'base_template': base_template
    }
    return render(request, TEMPLATE_MAP['detalle_nota'], context)


def eliminar_nota(request, pk):
    user, role, base_template, redirect_response = get_user_role_and_base(request)
    if redirect_response:
        return redirect_response

    nota = get_object_or_404(Nota, pk=pk)

    # Verificar que el usuario es el creador
    user_is_author = False
    if role == 'padre' and nota.creador_padre == user:
        user_is_author = True
    elif role == 'profesor' and nota.creador_profesor == user:
        user_is_author = True
    elif role == 'servicio' and nota.creador_servicio == user:
        user_is_author = True

    if not user_is_author:
        messages.error(request, 'No tienes permiso para eliminar esta nota.')
        return redirect('notas:lista_notas')

    if request.method == 'POST':
        nota.delete()
        messages.success(request, 'Nota eliminada exitosamente!')
        return redirect('notas:lista_notas')

    context = {
        'nota': nota,
        'usuario': user,
        'rol': role,
        'titulo': 'Confirmar eliminación',
        'base_template': base_template
    }
    return render(request, TEMPLATE_MAP['confirmar_eliminar'], context)
