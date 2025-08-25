import traceback
from audioop import reverse
from datetime import datetime
from turtle import pd

from django.views.generic import UpdateView

from .models import NivelEducativo
from .forms import NivelEducativoForm, EditarNivelEducativoForm, PeriodosConfigForm, EstudianteForm
from django.shortcuts import render, redirect
from .forms import CicloEscolarForm
from servicios_escolares.models import ServicioEscolar
from django.core.exceptions import ValidationError
import datetime
from estudiantes.models import Estudiante
from .forms import AsignarEstudiantesForm, ConfiguracionGradosForm, ConfiguracionFlexibleForm
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.db.models import Count
from .models import CicloEscolar, Grado, Grupo
from .forms import AsignarEstudiantesForm, ImportarEstudiantesForm
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect
from django.db.utils import IntegrityError
import pandas as pd


def verificar_autenticacion(request):
    """ Verifica si el usuario está autenticado y tiene una cuenta activa. """
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return False, redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except (ServicioEscolar.DoesNotExist, KeyError):
        messages.error(request, 'Usuario no autorizado o cuenta inactiva')
        return False, redirect('servicios_escolares:logout')

    return True, usuario


def crear_ciclo_paso1(request):
    # Verificación de autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')

    if request.method == 'POST':
        form = CicloEscolarForm(request.POST)
        if form.is_valid():
            try:
                ciclo = form.save(commit=False)

                # Si no es personalizado, calcular fecha_fin
                if ciclo.tipo_duracion != 'PERS':
                    fecha_inicio = form.cleaned_data['fecha_inicio']
                    meses_duracion = {
                        'TRAD': 10,  # Tradicional: 10 meses
                        'CUAT': 12,  # Cuatrimestral: 12 meses
                        'TRIM': 12,  # Trimestral: 12 meses
                        'SEM': 12  # Semestral: 12 meses
                    }.get(ciclo.tipo_duracion, 12)

                    # Calcular fecha_fin sin dateutil.relativedelta
                    year = fecha_inicio.year
                    month = fecha_inicio.month + meses_duracion
                    day = fecha_inicio.day

                    # Ajustar año si pasamos de diciembre
                    while month > 12:
                        month -= 12
                        year += 1

                    # Asegurarnos que el día no exceda los días del mes
                    last_day_of_month = (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day
                    day = min(day, last_day_of_month)

                    ciclo.fecha_fin = datetime.date(year, month, day)

                ciclo.save()
                request.session['ciclo_actual_id'] = ciclo.id

                messages.success(request, 'Ciclo escolar creado correctamente')
                """return redirect('servicios_escolares:gestion_ciclos')"""
                # Al final, en lugar de redirigir a gestion_ciclos, redirigir al paso 2:
                return redirect('servicios_escolares:paso2_grados', ciclo_id=ciclo.id)

            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
            except Exception as e:
                messages.error(request, f"Error al crear el ciclo: {str(e)}")
    else:
        form = CicloEscolarForm()

    context = {
        'form': form,
        'usuario': usuario,
    }
    return render(request, 'servicios_escolares/administracion/paso1_ciclo.html', context)


def configurar_grados(request, ciclo_id):
    # Verificación de autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')

    try:
        ciclo = get_object_or_404(CicloEscolar, pk=ciclo_id)
        niveles = NivelEducativo.objects.all().order_by('orden')

        if request.method == 'POST':
            try:
                # Procesar configuración por niveles
                for nivel in niveles:
                    # Eliminar configuración previa
                    Grado.objects.filter(ciclo=ciclo, nivel=nivel).delete()

                    # Obtener cantidad de grados
                    num_grados = int(request.POST.get(f'nivel_{nivel.id}_grados', 0))

                    if num_grados > 0:
                        for grado_num in range(1, num_grados + 1):
                            # Crear nombre del grado usando el nombre completo del nivel
                            nombre_grado = f"{grado_num}° {nivel.nombre}"

                            # Crear el grado
                            grado = Grado.objects.create(
                                ciclo=ciclo,
                                nivel=nivel,
                                numero=grado_num,
                                nombre=nombre_grado
                            )

                            # Obtener grupos para este grado
                            grupos_key = f'nivel_{nivel.id}_grado_{grado_num}_grupos'
                            num_grupos = int(request.POST.get(grupos_key, 1))

                            # Crear los grupos
                            for i in range(num_grupos):
                                letra = chr(65 + i)  # A, B, C...
                                Grupo.objects.create(
                                    grado=grado,
                                    ciclo=ciclo,
                                    letra=letra,
                                    turno='M',
                                    capacidad=30
                                )

                messages.success(request, 'Configuración guardada exitosamente')
                return redirect('servicios_escolares:paso3_estudiante', ciclo_id=ciclo.id)

            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
                raise

        # Preparar datos para el template (GET)
        configuracion = []
        for nivel in niveles:
            grados = Grado.objects.filter(ciclo=ciclo, nivel=nivel).order_by('numero')
            nivel_data = {
                'nivel': nivel,
                'grados': [],
                'num_grados': grados.count() or 0
            }

            for grado in grados:
                nivel_data['grados'].append({
                    'numero': grado.numero,
                    'num_grupos': Grupo.objects.filter(grado=grado).count()
                })

            configuracion.append(nivel_data)

        context = {
            'ciclo': ciclo,
            'configuracion': configuracion,
            'niveles': niveles,
            'usuario': usuario,
        }
        return render(request, 'servicios_escolares/administracion/paso2_grados.html', context)

    except Exception as e:
        messages.error(request, f'Error inesperado: {str(e)}')
        return redirect('servicios_escolares:gestion_ciclos')


def asignar_estudiantes(request, ciclo_id):
    # Verificación de autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        print("DEBUG: No hay credenciales en la sesión - Redirigiendo a login")  # Debug
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
        print(f"DEBUG: Usuario autenticado - ID: {usuario.id}")  # Debug
    except ServicioEscolar.DoesNotExist as e:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        print(f"DEBUG: Error de autenticación - {str(e)}")  # Debug
        return redirect('servicios_escolares:logout')

    try:
        ciclo = get_object_or_404(CicloEscolar, pk=ciclo_id)
        print(f"DEBUG: Ciclo obtenido - ID: {ciclo.id}, Nombre: {ciclo.nombre}")  # Debug

        # Obtener todos los grupos del ciclo con sus grados y niveles
        grupos = Grupo.objects.filter(ciclo=ciclo).select_related(
            'grado__nivel', 'grado'
        ).order_by('grado__nivel__orden', 'grado__numero', 'letra')

        print(f"DEBUG: Número de grupos encontrados: {grupos.count()}")  # Debug

        if request.method == 'POST':
            print("DEBUG: Método POST recibido")  # Debug
            print(f"DEBUG: Datos POST: {request.POST}")  # Debug

            try:
                # Procesar cada grupo
                for grupo in grupos:
                    cantidad_key = f'cantidad_{grupo.id}'
                    cantidad_estudiantes = int(request.POST.get(cantidad_key, 0))
                    print(f"DEBUG: Procesando grupo {grupo.id} - Cantidad estudiantes: {cantidad_estudiantes}")  # Debug

                    # Eliminar estudiantes existentes si se está actualizando
                    if 'actualizar' in request.POST:
                        deleted, _ = grupo.estudiantes.all().delete()
                        print(f"DEBUG: Estudiantes eliminados del grupo {grupo.id}: {deleted}")  # Debug

                    # Generar matrículas según el formato del ciclo
                    año_inicio = ciclo.nombre.split('-')[0][2:]  # Últimos 2 dígitos del año inicial
                    print(f"DEBUG: Año inicio para matrículas: {año_inicio}")  # Debug

                    for i in range(1, cantidad_estudiantes + 1):
                        matricula = f"{año_inicio}{grupo.grado.numero}{grupo.letra}-{i:03d}"
                        print(f"DEBUG: Generando matrícula: {matricula}")  # Debug

                        # Crear estudiante solo con matrícula y referencias
                        estudiante = Estudiante.objects.create(
                            matricula=matricula,
                            grupo_actual=grupo,
                            ciclo_inscripcion=ciclo,
                        )
                        print(
                            f"DEBUG: Estudiante creado - ID: {estudiante.id}, Matrícula: {estudiante.matricula}")  # Debug

                messages.success(request, 'Estudiantes registrados exitosamente')
                print("DEBUG: Proceso completado exitosamente")  # Debug
                return redirect('servicios_escolares:gestion_ciclos')

            except Exception as e:
                error_msg = f'Error al registrar estudiantes: {str(e)}'
                messages.error(request, error_msg)
                print(f"DEBUG ERROR: {error_msg}")  # Debug
                print(f"DEBUG ERROR Tipo: {type(e)}")  # Debug
                print(f"DEBUG ERROR Traceback: {traceback.format_exc()}")  # Debug

        # Preparar datos para el template (GET)
        print("DEBUG: Preparando datos para template (GET)")  # Debug
        grupos_data = []
        for grupo in grupos:
            grupo_info = {
                'id': grupo.id,
                'nombre_completo': f"{grupo.grado.numero}° {grupo.grado.nivel.nombre} Grupo {grupo.letra}",
                # Usando nombre en lugar de nombre_corto
                'nombre_corto': f"{grupo.grado.numero}{grupo.letra}",
                'cantidad_actual': grupo.estudiantes.count(),
                'capacidad': grupo.capacidad,
                'ejemplo_matricula': f"{ciclo.nombre.split('-')[0][2:]}{grupo.grado.numero}{grupo.letra}-001"
            }
            grupos_data.append(grupo_info)
            print(f"DEBUG: Grupo preparado - ID: {grupo.id}, Nombre: {grupo_info['nombre_completo']}")  # Debug

        context = {
            'ciclo': ciclo,
            'grupos': grupos_data,
            'usuario': usuario,
        }
        return render(request, 'servicios_escolares/administracion/paso3_estudiantes.html', context)

    except Exception as e:
        error_msg = f'Error inesperado: {str(e)}'
        messages.error(request, error_msg)
        print(f"DEBUG ERROR GLOBAL: {error_msg}")  # Debug
        print(f"DEBUG ERROR Traceback: {traceback.format_exc()}")  # Debug
        return redirect('servicios_escolares:gestion_ciclos')


def editar_nivel_view(request, pk):
    # Verificar autenticación mediante sesión
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        # Verificar usuario activo en la base de datos
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')
    except KeyError:
        messages.error(request, 'Error en los datos de sesión')
        return redirect('servicios_escolares:logout')

    # Obtener el nivel educativo
    nivel = get_object_or_404(NivelEducativo, pk=pk)

    if request.method == 'POST':
        form = EditarNivelEducativoForm(request.POST, instance=nivel)
        if form.is_valid():
            nivel_editado = form.save()
            messages.success(request, f'Nivel educativo "{nivel_editado.nombre}" actualizado correctamente')
            return redirect('servicios_escolares:panel-principal')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario')
    else:
        form = EditarNivelEducativoForm(instance=nivel)

    context = {
        'form': form,
        'nivel': nivel,
        'usuario': usuario,
        'titulo': f'Editar {nivel.nombre}',
        'ultimo_acceso': request.session.get('ultimo_acceso', 'Nunca'),
        'rol': request.session.get('credenciales', {}).get('rol', 'Servicio Escolar')
    }

    return render(request, 'servicios_escolares/administracion/editar_nivel.html', context)


def editar_ciclo(request, pk):
    # Verificación de autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')

    ciclo = get_object_or_404(CicloEscolar, pk=pk)

    if request.method == 'POST':
        form = CicloEscolarForm(request.POST, instance=ciclo)
        if form.is_valid():
            try:
                ciclo_editado = form.save(commit=False)

                # Recalcular fecha_fin si no es personalizado
                if ciclo_editado.tipo_duracion != 'PERS':
                    fecha_inicio = form.cleaned_data['fecha_inicio']
                    meses_duracion = {
                        'TRAD': 10,  # Tradicional: 10 meses
                        'CUAT': 12,  # Cuatrimestral: 12 meses
                        'TRIM': 12,  # Trimestral: 12 meses
                        'SEM': 12  # Semestral: 12 meses
                    }.get(ciclo_editado.tipo_duracion, 12)

                    # Calcular nueva fecha_fin
                    year = fecha_inicio.year
                    month = fecha_inicio.month + meses_duracion
                    day = fecha_inicio.day

                    # Ajustar año si pasamos de diciembre
                    while month > 12:
                        month -= 12
                        year += 1

                    # Asegurar que el día no exceda los días del mes
                    if month == 12:
                        next_month = 1
                        next_year = year + 1
                    else:
                        next_month = month + 1
                        next_year = year

                    last_day_of_month = (datetime.date(next_year, next_month, 1) - datetime.timedelta(days=1)).day
                    day = min(day, last_day_of_month)

                    ciclo_editado.fecha_fin = datetime.date(year, month, day)

                ciclo_editado.save()
                messages.success(request, 'Ciclo escolar actualizado correctamente')
                return redirect('servicios_escolares:panel-principal')

            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
            except Exception as e:
                messages.error(request, f"Error al actualizar el ciclo: {str(e)}")
    else:
        form = CicloEscolarForm(instance=ciclo)

    context = {
        'form': form,
        'ciclo': ciclo,
        'usuario': usuario,
    }
    return render(request, 'servicios_escolares/administracion/editar_ciclo.html', context)


def panel_grupos(request):
    # Verificación de autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')

    # Obtener el ciclo actual
    ciclo_actual = CicloEscolar.obtener_actual()
    if not ciclo_actual:
        messages.error(request, 'No hay un ciclo escolar activo')
        return redirect('servicios_escolares:dashboard')

    # Obtener parámetros
    grado_id = request.GET.get('grado_id')
    grupo_id = request.GET.get('grupo_id')

    # Obtener todos los grados del ciclo actual
    grados = Grado.objects.filter(
        ciclo=ciclo_actual
    ).annotate(
        num_grupos=Count('grupos')
    ).order_by('nivel__orden', 'numero')

    grado_seleccionado = None
    grupos = None
    grupo_seleccionado = None
    estudiantes = None

    if grado_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id, ciclo=ciclo_actual)

        # Obtener grupos con conteo de estudiantes
        grupos = Grupo.objects.filter(
            grado=grado_seleccionado,
            ciclo=ciclo_actual
        ).annotate(
            num_estudiantes=Count('estudiantes')
        ).order_by('letra')

        if grupo_id:
            grupo_seleccionado = get_object_or_404(Grupo, pk=grupo_id, grado=grado_seleccionado)

            # Obtener estudiantes del grupo con información básica
            estudiantes = Estudiante.objects.filter(
                grupo_actual=grupo_seleccionado
            ).select_related('grupo_actual').order_by('apellido_paterno', 'apellido_materno', 'nombre')

    context = {
        'ciclo_actual': ciclo_actual,
        'grados': grados,
        'grado_seleccionado': grado_seleccionado,
        'grupos': grupos,
        'grupo_seleccionado': grupo_seleccionado,
        'estudiantes': estudiantes,
        'usuario': usuario,
    }
    return render(request, 'servicios_escolares/administracion/panel_grupos.html', context)


def importar_estudiantes(request, grupo_id):
    grupo = get_object_or_404(Grupo, pk=grupo_id)

    def get_redirect_url():
        return f"{reverse('servicios_escolares:panel-grupos')}?grado_id={grupo.grado.id}&grupo_id={grupo.id}"

    if request.method == 'POST':
        form = ImportarEstudiantesForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                archivo = request.FILES['archivo']

                # Leer archivo
                try:
                    if archivo.name.endswith('.xlsx'):
                        df = pd.read_excel(archivo, engine='openpyxl')
                    elif archivo.name.endswith('.csv'):
                        df = pd.read_csv(archivo)
                except Exception as e:
                    messages.error(request, f'Error al leer archivo: {str(e)}')
                    return redirect(get_redirect_url())

                # Verificar columnas requeridas
                required_columns = ['Nombre', 'Apellido Paterno']
                missing_cols = [col for col in required_columns if col not in df.columns]
                if missing_cols:
                    messages.error(request, f'Faltan columnas requeridas: {", ".join(missing_cols)}')
                    return redirect(get_redirect_url())

                # Obtener estudiantes existentes ordenados por matrícula
                estudiantes_existentes = grupo.estudiantes.all().order_by('matricula')
                if estudiantes_existentes.count() != len(df):
                    messages.error(request,
                                   f'El archivo contiene {len(df)} registros pero hay {estudiantes_existentes.count()} estudiantes en el grupo')
                    return redirect(get_redirect_url())

                # Procesar actualizaciones
                actualizados = 0
                errores = 0

                for index, (_, fila) in enumerate(df.iterrows()):
                    try:
                        estudiante = estudiantes_existentes[index]

                        # Actualizar datos
                        estudiante.nombre = str(fila['Nombre']).strip()
                        estudiante.apellido_paterno = str(fila['Apellido Paterno']).strip()
                        estudiante.apellido_materno = str(fila.get('Apellido Materno', '')).strip()

                        if 'CURP' in fila and pd.notna(fila['CURP']):
                            estudiante.curp = str(fila['CURP']).strip()

                        if 'Fecha de Nacimiento' in fila and pd.notna(fila['Fecha de Nacimiento']):
                            estudiante.fecha_nacimiento = fila['Fecha de Nacimiento']

                        estudiante.save()
                        actualizados += 1

                    except Exception as e:
                        messages.warning(request, f'Error actualizando estudiante {index + 1}: {str(e)}')
                        errores += 1

                # Resultado final
                if actualizados > 0:
                    messages.success(request, f'¡Actualización exitosa! {actualizados} estudiantes actualizados')
                if errores > 0:
                    messages.warning(request, f'{errores} registros no pudieron ser procesados')

                return redirect(get_redirect_url())

            except Exception as e:
                messages.error(request, f'Error inesperado: {str(e)}')
                return redirect(get_redirect_url())

    return redirect(get_redirect_url())


class EditarEstudianteView(UpdateView):
    model = Estudiante
    fields = [
        'nombre',
        'apellido_paterno',
        'apellido_materno',
        'fecha_nacimiento',
        'curp',
        'grupo_actual',
    ]
    template_name = 'servicios_escolares/administracion/editar_estudiante.html'
    success_url = reverse_lazy('servicios_escolares:panel-grupos')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grupo'] = self.object.grupo_actual
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Estudiante actualizado correctamente')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Error al actualizar el estudiante')
        return super().form_invalid(form)


def panel_grupos_padres(request):
    # Verificación de autenticación
    if not request.session.get('credenciales'):
        messages.warning(request, 'Debes iniciar sesión primero')
        return redirect('servicios_escolares:login')

    try:
        usuario = ServicioEscolar.objects.get(
            id=request.session['credenciales']['id'],
            estado_cuenta='Activo'
        )
    except ServicioEscolar.DoesNotExist:
        messages.error(request, 'Usuario no encontrado o cuenta inactiva')
        return redirect('servicios_escolares:logout')

    # Obtener el ciclo actual
    ciclo_actual = CicloEscolar.obtener_actual()
    if not ciclo_actual:
        messages.error(request, 'No hay un ciclo escolar activo')
        return redirect('servicios_escolares:dashboard')

    # Obtener parámetros
    grado_id = request.GET.get('grado_id')
    grupo_id = request.GET.get('grupo_id')

    # Obtener todos los grados del ciclo actual
    grados = Grado.objects.filter(
        ciclo=ciclo_actual
    ).annotate(
        num_grupos=Count('grupos')
    ).order_by('nivel__orden', 'numero')

    grado_seleccionado = None
    grupos = None
    grupo_seleccionado = None
    estudiantes = None

    if grado_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id, ciclo=ciclo_actual)

        # Obtener grupos con conteo de estudiantes
        grupos = Grupo.objects.filter(
            grado=grado_seleccionado,
            ciclo=ciclo_actual
        ).annotate(
            num_estudiantes=Count('estudiantes')
        ).order_by('letra')

        if grupo_id:
            grupo_seleccionado = get_object_or_404(Grupo, pk=grupo_id, grado=grado_seleccionado)

            # Obtener estudiantes del grupo con información de padre
            estudiantes = Estudiante.objects.filter(
                grupo_actual=grupo_seleccionado
            ).select_related(
                'grupo_actual',
                'padre'  # Optimización para acceder a los datos del padre
            ).order_by('apellido_paterno', 'apellido_materno', 'nombre')

    context = {
        'ciclo_actual': ciclo_actual,
        'grados': grados,
        'grado_seleccionado': grado_seleccionado,
        'grupos': grupos,
        'grupo_seleccionado': grupo_seleccionado,
        'estudiantes': estudiantes,
        'usuario': usuario,
    }
    return render(request, 'servicios_escolares/administracion/panel_grupos_padres.html', context)
