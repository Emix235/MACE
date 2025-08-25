from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta

# Importaciones de modelos (AJUSTA SEGÚN TU ESTRUCTURA REAL)
from servicios_escolares.models import ServicioEscolar
from formularios.models import (
    EncuestaAplicada,
    Respuesta,
    Pregunta,
    RetroalimentacionAplicada,
    RespuestaRetroalimentacion
)
from citas.models import Cita
from profesores.models import Profesor
from padres.models import Padre


def obtener_metricas_satisfaccion(servicio_escolar, dias_atras=30):
    """
    Obtiene métricas de satisfacción para el panel de control

    Parámetros:
        servicio_escolar (ServicioEscolar): Instancia del modelo ServicioEscolar
        dias_atras (int): Número de días hacia atrás para analizar (default: 30)

    Retorna:
        dict: Diccionario con todas las métricas organizadas
    """
    # 1. Definir fecha límite para el análisis
    fecha_limite = timezone.now() - timedelta(days=dias_atras)

    # 2. Obtener comentarios recientes (últimas respuestas de texto)
    comentarios_recientes = Respuesta.objects.filter(
        Q(pregunta__tipo='texto') & ~Q(valor_texto=''),
        encuesta_aplicada__encuesta__creada_por=servicio_escolar,
        fecha_respuesta__gte=fecha_limite
    ).order_by('-fecha_respuesta')[:10].select_related(
        'pregunta', 'profesor', 'padre'
    )

    # 3. Calcular calificaciones promedio
    # Para encuestas generales
    calificaciones_encuestas = Respuesta.objects.filter(
        pregunta__tipo='escala_5',
        encuesta_aplicada__encuesta__creada_por=servicio_escolar,
        fecha_respuesta__gte=fecha_limite
    ).aggregate(
        promedio_general=Avg('valor_numero'),
        total_respuestas=Count('id')
    )

    # Para retroalimentación de citas
    calificaciones_retro = RespuestaRetroalimentacion.objects.filter(
        pregunta__tipo='escala_5',
        retroalimentacion_aplicada__retroalimentacion__creada_por=servicio_escolar,
        fecha_respuesta__gte=fecha_limite
    ).aggregate(
        promedio_retro=Avg('valor_numero'),
        total_retro=Count('id')
    )

    # 4. Calcular tendencias de satisfacción (por semana)
    datos_tendencia = []
    for i in range(dias_atras, -1, -7):  # Agrupar por semanas
        fecha_inicio = timezone.now() - timedelta(days=i)
        fecha_fin = fecha_inicio + timedelta(days=7)

        promedio_semana = Respuesta.objects.filter(
            pregunta__tipo='escala_5',
            encuesta_aplicada__encuesta__creada_por=servicio_escolar,
            fecha_respuesta__range=(fecha_inicio, fecha_fin)
        ).aggregate(promedio=Avg('valor_numero'))['promedio'] or 0

        datos_tendencia.append({
            'fecha': fecha_inicio.date(),
            'promedio': round(promedio_semana, 2)
        })

    # 5. Distribución de calificaciones (1-5)
    distribucion = Respuesta.objects.filter(
        pregunta__tipo='escala_5',
        encuesta_aplicada__encuesta__creada_por=servicio_escolar,
        fecha_respuesta__gte=fecha_limite
    ).values('valor_numero').annotate(
        cantidad=Count('valor_numero')
    ).order_by('valor_numero')

    dist_formateada = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for item in distribucion:
        dist_formateada[item['valor_numero']] = item['cantidad']

    # 6. Porcentaje de recomendación (preguntas Sí/No)
    recomendaciones = Respuesta.objects.filter(
        pregunta__tipo='si_no',
        pregunta__texto__icontains='recomendar',
        encuesta_aplicada__encuesta__creada_por=servicio_escolar,
        fecha_respuesta__gte=fecha_limite
    ).aggregate(
        total=Count('id'),
        positivos=Count('id', filter=Q(valor_numero=1))
    )

    try:
        porcentaje_recomendacion = (recomendaciones['positivos'] / recomendaciones['total']) * 100
    except (ZeroDivisionError, TypeError):
        porcentaje_recomendacion = 0

    # 7. Análisis de comentarios por categoría
    categorias_comentarios = {
        'sistema': 0,
        'profesor': 0,
        'tiempo': 0,
        'servicio': 0
    }

    palabras_clave = {
        'sistema': ['sistema', 'plataforma', 'app', 'aplicación', 'tecnología'],
        'profesor': ['profesor', 'maestro', 'docente', 'enseñanza'],
        'tiempo': ['tiempo', 'espera', 'rápido', 'lento', 'esperar'],
        'servicio': ['servicio', 'atención', 'trato', 'amable', 'cordial']
    }

    comentarios_texto = Respuesta.objects.filter(
        pregunta__tipo='texto',
        encuesta_aplicada__encuesta__creada_por=servicio_escolar,
        fecha_respuesta__gte=fecha_limite
    ).exclude(valor_texto='')

    for comentario in comentarios_texto:
        texto = comentario.valor_texto.lower()
        for categoria, palabras in palabras_clave.items():
            if any(palabra in texto for palabra in palabras):
                categorias_comentarios[categoria] += 1

    # 8. Calcular métricas adicionales
    tasa_respuesta = calcular_tasa_respuesta(servicio_escolar, dias_atras)
    satisfaccion_profesores = obtener_satisfaccion_profesores(servicio_escolar, dias_atras)

    # 9. Retornar todas las métricas organizadas
    return {
        'comentarios_recientes': [
            {
                'texto': c.valor_texto,
                'fecha': c.fecha_respuesta,
                'usuario': c.nombre_respondiente,
                'tipo_usuario': c.tipo_respondiente,
                'pregunta': c.pregunta.texto[:50] + '...' if len(c.pregunta.texto) > 50 else c.pregunta.texto
            }
            for c in comentarios_recientes
        ],
        'calificaciones': {
            'promedio_general': round(calificaciones_encuestas['promedio_general'] or 0, 2),
            'promedio_retroalimentacion': round(calificaciones_retro['promedio_retro'] or 0, 2),
            'total_respuestas': calificaciones_encuestas['total_respuestas'] + calificaciones_retro['total_retro'],
            'distribucion': dist_formateada,
            'porcentaje_recomendacion': round(porcentaje_recomendacion, 1)
        },
        'tendencias': {
            'datos': datos_tendencia,
            'mejora': calcular_tendencia(datos_tendencia),
            'periodo': f"Últimos {dias_atras} días"
        },
        'analisis_comentarios': {
            'categorias': categorias_comentarios,
            'total_comentarios': sum(categorias_comentarios.values())
        },
        'estadisticas_avanzadas': {
            'tasa_respuesta': tasa_respuesta,
            'satisfaccion_profesores': satisfaccion_profesores
        }
    }


def calcular_tendencia(datos):
    """Calcula si la tendencia es positiva, negativa o neutra

    Parámetros:
        datos (list): Lista de diccionarios con {'fecha': date, 'promedio': float}

    Retorna:
        str: 'positiva', 'negativa' o 'neutra'
    """
    if len(datos) < 2:
        return 'neutra'

    primero = datos[0]['promedio']
    ultimo = datos[-1]['promedio']

    if ultimo > primero + 0.3:
        return 'positiva'
    elif ultimo < primero - 0.3:
        return 'negativa'
    return 'neutra'


def calcular_tasa_respuesta(servicio_escolar, dias):
    """Calcula el porcentaje de citas/encuestas con retroalimentación

    Parámetros:
        servicio_escolar (ServicioEscolar): Instancia del servicio
        dias (int): Número de días a analizar

    Retorna:
        dict: {'citas': float, 'encuestas': float, 'promedio': float}
    """
    fecha_limite = timezone.now() - timedelta(days=dias)

    # Citas
    total_citas = Cita.objects.filter(
        servicio_escolar=servicio_escolar,
        fecha_hora_inicio__gte=fecha_limite,
        estado='completada'
    ).count()

    citas_con_retro = RetroalimentacionAplicada.objects.filter(
        cita__servicio_escolar=servicio_escolar,
        cita__fecha_hora_inicio__gte=fecha_limite,
        completada=True
    ).count()

    tasa_citas = (citas_con_retro / total_citas * 100) if total_citas > 0 else 0

    # Encuestas
    total_encuestas = EncuestaAplicada.objects.filter(
        encuesta__creada_por=servicio_escolar,
        fecha_aplicacion__gte=fecha_limite
    ).count()

    respuestas_encuestas = Respuesta.objects.filter(
        encuesta_aplicada__encuesta__creada_por=servicio_escolar,
        fecha_respuesta__gte=fecha_limite
    ).values('encuesta_aplicada').distinct().count()

    tasa_encuestas = (respuestas_encuestas / total_encuestas * 100) if total_encuestas > 0 else 0

    return {
        'citas': round(tasa_citas, 1),
        'encuestas': round(tasa_encuestas, 1),
        'promedio': round((tasa_citas + tasa_encuestas) / 2, 1)
    }


def obtener_satisfaccion_profesores(servicio_escolar, dias):
    """Obtiene métricas de satisfacción por profesor

    Parámetros:
        servicio_escolar (ServicioEscolar): Instancia del servicio
        dias (int): Número de días a analizar

    Retorna:
        list: Lista de diccionarios con datos de profesores
    """
    fecha_limite = timezone.now() - timedelta(days=dias)

    resultados = RespuestaRetroalimentacion.objects.filter(
        pregunta__tipo='escala_5',
        retroalimentacion_aplicada__retroalimentacion__creada_por=servicio_escolar,
        retroalimentacion_aplicada__profesor__isnull=False,
        fecha_respuesta__gte=fecha_limite
    ).values(
        'retroalimentacion_aplicada__profesor',
        'retroalimentacion_aplicada__profesor__nombre_completo'
    ).annotate(
        promedio=Avg('valor_numero'),
        total_respuestas=Count('id')
    ).order_by('-promedio')[:5]

    return [
        {
            'profesor_id': r['retroalimentacion_aplicada__profesor'],
            'nombre': r['retroalimentacion_aplicada__profesor__nombre_completo'],
            'calificacion': round(r['promedio'], 2) if r['promedio'] is not None else 0,
            'respuestas': r['total_respuestas']
        }
        for r in resultados
    ]
