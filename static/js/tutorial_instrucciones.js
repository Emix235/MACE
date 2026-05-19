// ========== CONFIGURACIÓN DE TUTORIALES POR ROL ==========
// Este archivo contiene todas las definiciones de tutoriales y pasos

const TUTORIALES_CONFIG = {
  // =========================
  // SERVICIOS ESCOLARES
  // =========================
  servicios_escolares: {
    agendar_cita: {
      nombre: "Cómo Agendar una Cita",
      descripcion: "Aprende a agendar citas para estudiantes paso a paso",
      pasos: [
        {
          titulo: "Inicio",
          texto: "Bienvenido al tutorial. Desde el dashboard, haz clic en 'Nueva Cita' o el botón correspondiente.",
          url: "/servicios_escolares/dashboard/",
          selector: null,
          accion: "abrir_dropdown_citas",
        },
        {
          titulo: "Seleccionar Grado",
          texto: "Selecciona un grado académico de la lista haciendo clic en él.",
          url: "/servicios_escolares/citas/",
          selector: ".grado-card:first-child, .card.grado:first-child, [data-grado-id]:first-child, .list-group-item:first-child",
          accion: null,
        },
        {
          titulo: "Seleccionar Grupo",
          texto: "Elige un grupo dentro del grado seleccionado. Luego haz clic en 'Ver citas'.",
          url: "/servicios_escolares/citas/?grado_id=4",
          selector: "a[href*='grupo_id']:first-child, .grupo-item:first-child, [data-grupo-id]:first-child",
          accion: null,
        },
        {
          titulo: "Seleccionar Estudiante",
          texto: "Haz clic en 'Agendar cita' junto al estudiante para agendar nueva cita.",
          url: "/servicios_escolares/citas/?grado_id=4&grupo_id=1#detalle-grupo",
          selector: "a.btn-success:first-child, .btn-nueva:first-child, [href*='agendar']:first-child",
          accion: null,
        },
        {
          titulo: "Completar Fecha",
          texto: "Selecciona la fecha y hora para la cita. Este campo es obligatorio.",
          url: "/servicios_escolares/agendar-cita/16",
          selector: "#id_fecha_hora_inicio, input[type='datetime-local'], .datetime-input, input[name='fecha']",
          accion: null,
        },
        {
          titulo: "Escribir Motivo",
          texto: "Describe el motivo de la reunión de manera clara y concisa.",
          url: "/servicios_escolares/agendar-cita/16",
          selector: "#id_motivo, textarea[name='motivo'], .motivo-textarea, textarea",
          accion: null,
        },
        {
          titulo: "Definir Duración",
          texto: "Selecciona la duración de la cita (30-60 minutos es lo recomendado).",
          url: "/servicios_escolares/agendar-cita/16",
          selector: "#id_duracion, select[name='duracion'], .duracion-select, select",
          accion: null,
        },
        {
          titulo: "Confirmar Cita",
          texto: "Haz clic en 'Agendar Cita' para finalizar el proceso.",
          url: "/servicios_escolares/agendar-cita/16",
          selector: "button[type='submit'], .btn-agendar, input[type='submit']",
          accion: null,
        },
      ],
    },
    gestionar_calendario: {
      nombre: "Gestión de Calendario",
      descripcion: "Aprende a gestionar y visualizar el calendario de citas",
      pasos: [
        {
          titulo: "Acceder al Calendario",
          texto: "Desde el dashboard, haz clic en 'Calendario' o 'Ver todas las citas'.",
          url: "/servicios_escolares/dashboard/",
          selector: "[href*='calendario'], [href*='citas'], .btn-calendario",
          accion: null,
        },
        {
          titulo: "Navegar entre Fechas",
          texto: "Usa los botones de anterior/siguiente para navegar entre meses o semanas.",
          url: "/calendario/",
          selector: ".fc-prev-button, .fc-next-button, .btn-prev, .btn-next",
          accion: null,
        },
        {
          titulo: "Ver Detalles de Cita",
          texto: "Haz clic en cualquier cita del calendario para ver sus detalles.",
          url: "/calendario/",
          selector: ".fc-event, .evento-cita, [data-cita-id]",
          accion: null,
        },
        {
          titulo: "Filtrar Citas",
          texto: "Usa los filtros para ver citas por estado, grado o fecha específica.",
          url: "/calendario/",
          selector: "#filtro-estado, .filtro-select, select[name='filtro']",
          accion: null,
        },
      ],
    },
    generar_reportes: {
      nombre: "Generar Reportes",
      descripcion: "Aprende a generar reportes estadísticos del sistema",
      pasos: [
        {
          titulo: "Acceder a Reportes",
          texto: "Desde el menú principal, selecciona 'Reportes' o 'Estadísticas'.",
          url: "/servicios_escolares/dashboard/",
          selector: "[href*='reportes'], [href*='estadisticas'], .btn-reportes",
          accion: null,
        },
        {
          titulo: "Seleccionar Tipo de Reporte",
          texto: "Elige el tipo de reporte que deseas generar (citas por mes, por grado, etc).",
          url: "/reportes/",
          selector: ".tipo-reporte, .report-card, [data-reporte-tipo]",
          accion: null,
        },
        {
          titulo: "Configurar Parámetros",
          texto: "Selecciona el rango de fechas y otros filtros para el reporte.",
          url: "/reportes/",
          selector: "#fecha_inicio, #fecha_fin, .fecha-input",
          accion: null,
        },
        {
          titulo: "Generar Reporte",
          texto: "Haz clic en 'Generar' para crear el reporte con los parámetros seleccionados.",
          url: "/reportes/",
          selector: "button[type='submit'], .btn-generar, .btn-descargar",
          accion: null,
        },
      ],
    },
    gestionar_usuarios: {
      nombre: "Gestión de Usuarios",
      descripcion: "Aprende a gestionar usuarios y permisos en el sistema",
      pasos: [
        {
          titulo: "Acceder a Usuarios",
          texto: "Desde el panel de administración, selecciona 'Usuarios' o 'Gestión de usuarios'.",
          url: "/servicios_escolares/dashboard/",
          selector: "[href*='usuarios'], [href*='gestion-usuarios'], .btn-usuarios",
          accion: null,
        },
        {
          titulo: "Ver Lista de Usuarios",
          texto: "Revisa la lista completa de usuarios registrados en el sistema.",
          url: "/usuarios/",
          selector: ".user-list, .table-usuarios, tbody tr:first-child",
          accion: null,
        },
        {
          titulo: "Agregar Nuevo Usuario",
          texto: "Haz clic en 'Agregar Usuario' o 'Nuevo' para crear un nuevo usuario.",
          url: "/usuarios/",
          selector: ".btn-agregar-usuario, [href*='nuevo'], .btn-success",
          accion: null,
        },
        {
          titulo: "Editar Usuario",
          texto: "Selecciona un usuario de la lista y haz clic en 'Editar' para modificar sus datos.",
          url: "/usuarios/",
          selector: ".btn-editar, [href*='editar'], .btn-warning",
          accion: null,
        },
      ],
    },
  },

  // =========================
  // PADRE DE FAMILIA
  // =========================
  padre: {
    ver_citas: {
      nombre: "Ver Citas de mi Hijo",
      descripcion: "Consulta las citas programadas para tus hijos",
      pasos: [
        {
          titulo: "Ir a Citas",
          texto: "Accede al apartado de citas desde el menú principal.",
          url: "/padre/dashboard/",
          selector: "[href*='citas'], .nav-link-citas, .menu-citas",
          accion: null,
        },
        {
          titulo: "Seleccionar Hijo",
          texto: "Selecciona el hijo del cual deseas ver las citas.",
          url: "/padre/citas/",
          selector: ".hijo-card:first-child, .estudiante-item:first-child, [data-hijo-id]:first-child",
          accion: null,
        },
        {
          titulo: "Ver Detalles",
          texto: "Haz clic en cualquier cita para ver más detalles.",
          url: "/padre/citas/estudiante/",
          selector: ".cita-item:first-child, .cita-card:first-child, [data-cita-id]:first-child",
          accion: null,
        },
      ],
    },
    solicitar_reunion: {
      nombre: "Solicitar Reunión",
      descripcion: "Aprende a solicitar una reunión con los profesores",
      pasos: [
        {
          titulo: "Solicitar Reunión",
          texto: "Desde la sección de citas, busca el botón 'Solicitar Reunión'.",
          url: "/padre/dashboard/",
          selector: ".btn-solicitar-reunion, [href*='solicitar'], .btn-primary",
          accion: null,
        },
        {
          titulo: "Seleccionar Motivo",
          texto: "Elige el motivo de la reunión de la lista de opciones.",
          url: "/padre/solicitar-reunion/",
          selector: "#id_motivo, select[name='motivo'], .motivo-select",
          accion: null,
        },
        {
          titulo: "Elegir Fecha",
          texto: "Selecciona una fecha y hora disponible para la reunión.",
          url: "/padre/solicitar-reunion/",
          selector: "#id_fecha, input[type='date'], .fecha-input",
          accion: null,
        },
      ],
    },
  },

  // =========================
  // PROFESOR
  // =========================
  profesor: {
    gestionar_citas: {
      nombre: "Gestionar Mis Citas",
      descripcion: "Administra las citas programadas con padres y estudiantes",
      pasos: [
        {
          titulo: "Abrir Calendario",
          texto: "Accede al calendario desde el menú principal del profesor.",
          url: "/profesor/dashboard/",
          selector: "[href*='calendario'], .nav-link-calendario, .menu-calendario",
          accion: null,
        },
        {
          titulo: "Ver Citas del Día",
          texto: "Observa las citas programadas para el día actual.",
          url: "/profesor/calendario/",
          selector: ".citas-hoy, .citas-del-dia, .list-group-item:first-child",
          accion: null,
        },
        {
          titulo: "Ver Detalles de Cita",
          texto: "Haz clic en una cita para ver información completa.",
          url: "/profesor/calendario/",
          selector: ".fc-event, .evento-cita, [data-cita-id]",
          accion: null,
        },
        {
          titulo: "Confirmar Asistencia",
          texto: "Marca las citas como completadas después de la reunión.",
          url: "/profesor/cita/",
          selector: ".btn-confirmar, .btn-completar, button[value='completada']",
          accion: null,
        },
      ],
    },
    registrar_notas: {
      nombre: "Registrar Notas",
      descripcion: "Registrar observaciones después de cada reunión",
      pasos: [
        {
          titulo: "Acceder a Cita",
          texto: "Selecciona una cita completada para agregar notas.",
          url: "/profesor/calendario/",
          selector: ".cita-completada:first-child, [data-estado='completada']:first-child",
          accion: null,
        },
        {
          titulo: "Agregar Notas",
          texto: "En la sección de notas, escribe tus observaciones.",
          url: "/profesor/cita/",
          selector: "#id_notas, textarea[name='notas'], .notas-input",
          accion: null,
        },
        {
          titulo: "Guardar Cambios",
          texto: "Haz clic en 'Guardar' para registrar las notas.",
          url: "/profesor/cita/",
          selector: "button[type='submit'], .btn-guardar, .btn-primary",
          accion: null,
        },
      ],
    },
  },
};

// ========== FUNCIONES DE UTILIDAD ==========

/**
 * Obtiene los tutoriales según el rol del usuario
 * @param {string} role - Rol del usuario (servicios_escolares, padre, profesor)
 * @returns {object} Tutoriales disponibles para el rol
 */
function getTutorialesByRole(role) {
  const roleMap = {
    servicios_escolares: "servicios_escolares",
    servicio: "servicios_escolares",
    padre: "padre",
    profesor: "profesor",
    professor: "profesor",
    default: "servicios_escolares",
  };

  const normalizedRole = roleMap[role] || roleMap.default;
  return TUTORIALES_CONFIG[normalizedRole] || TUTORIALES_CONFIG.servicios_escolares;
}

/**
 * Obtiene un tutorial específico por ID y rol
 * @param {string} role - Rol del usuario
 * @param {string} tutorialId - ID del tutorial
 * @returns {object|null} Tutorial encontrado o null
 */
function getTutorialById(role, tutorialId) {
  const tutoriales = getTutorialesByRole(role);
  return tutoriales[tutorialId] || null;
}

/**
 * Obtiene los pasos de un tutorial específico
 * @param {string} role - Rol del usuario
 * @param {string} tutorialId - ID del tutorial
 * @returns {array|null} Lista de pasos o null
 */
function getTutorialPasos(role, tutorialId) {
  const tutorial = getTutorialById(role, tutorialId);
  return tutorial ? tutorial.pasos : null;
}

/**
 * Obtiene la lista de tutoriales con sus metadatos
 * @param {string} role - Rol del usuario
 * @returns {array} Lista de tutoriales (id, nombre, descripcion, pasosCount)
 */
function getTutorialesList(role) {
  const tutoriales = getTutorialesByRole(role);
  return Object.entries(tutoriales).map(([id, tutorial]) => ({
    id: id,
    nombre: tutorial.nombre,
    descripcion: tutorial.descripcion,
    pasosCount: tutorial.pasos.length,
  }));
}

/**
 * Obtiene la URL base para un rol específico
 * @param {string} role - Rol del usuario
 * @returns {string} URL base del dashboard
 */
function getDashboardUrlByRole(role) {
  const urls = {
    servicios_escolares: "/servicios_escolares/dashboard/",
    servicio: "/servicios_escolares/dashboard/",
    padre: "/padre/dashboard/",
    profesor: "/profesor/dashboard/",
  };
  return urls[role] || urls.servicios_escolares;
}

// Exportar para uso en otros módulos (si se usa módulos ES6)
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    TUTORIALES_CONFIG,
    getTutorialesByRole,
    getTutorialById,
    getTutorialPasos,
    getTutorialesList,
    getDashboardUrlByRole,
  };
}