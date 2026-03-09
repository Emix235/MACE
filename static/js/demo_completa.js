// Prevenir múltiples cargas del script
if (window.demoCompletaLoaded) {
    console.warn('Script demo_completa.js ya cargado, abortando.');
    throw new Error('demo_completa.js ya cargado');
}
window.demoCompletaLoaded = true;

// Clase base para tutoriales
class TutorialInteractivo {
    constructor(config) {
        console.log('Inicializando TutorialInteractivo...');

        // Configuración desde Django
        this.config = config || {};
        this.tutorialActual = null;

        this.iframe = document.getElementById('demoIframe');
        this.popup = document.getElementById('demoPopup');
        this.estaInicializado = false;

        this.init();
    }

    // Catálogo de tutoriales disponibles
    getTutoriales() {
        return {
            'agendar_cita': {
                nombre: "Cómo Agendar una Cita",
                descripcion: "Aprende a agendar citas para estudiantes paso a paso",
                pasos: [
                    {
                        titulo: "Inicio",
                        texto: "Bienvenido al tutorial. Desde el dashboard, haz clic en 'Nueva Cita' o el botón correspondiente.",
                        url: this.config.urls?.dashboard || "/",
                        selector: "[href*='panel_citas'], a[href*='nueva-cita'], .btn-nueva-cita, .btn-primary",
                        accion: null
                    },
                    {
                        titulo: "Seleccionar Grado",
                        texto: "Selecciona un grado académico de la lista haciendo clic en él.",
                        url: this.config.urls?.panel_citas || "/servicios_escolares/citas/",
                        selector: ".grado-card:first-child, .card.grado:first-child, [data-grado-id]:first-child, .list-group-item:first-child",
                        accion: null
                    },
                    {
                        titulo: "Seleccionar Grupo",
                        texto: "Elige un grupo dentro del grado seleccionado. Y abajo has click en Ver citas",
                        url: `${this.config.urls?.panel_citas || '/servicios_escolares/citas/'}?grado_id=4`,
                        selector: "a[href*='grupo_id']:first-child, .grupo-item:first-child, [data-grupo-id]:first-child",
                        accion: null
                    },
                    {
                        titulo: "Seleccionar Estudiante",
                        texto: "Haz clic en 'Agendar cita' junto al estudiante para agendar nueva cita.",
                        url: `${this.config.urls?.panel_citas || '/servicios_escolares/citas/'}?grado_id=4&grupo_id=1#detalle-grupo`,
                        selector: "a.btn-success:first-child, .btn-nueva:first-child, [href*='agendar']:first-child, button:has(span:contains('Nueva'))",
                        accion: null
                    },
                    {
                        titulo: "Completar Fecha",
                        texto: "Selecciona la fecha y hora para la cita. Es importante el campo para agendar cita.",
                        url: (this.config.urls?.agendar_cita || '/servicios_escolares/agendar-cita/0').replace('/0', '/16'),
                        selector: "#id_fecha_hora_inicio, input[type='datetime-local'], .datetime-input, input[name='fecha']",
                        accion: null
                    },
                    {
                        titulo: "Escribir Motivo",
                        texto: "Describe el motivo de la reunión. Es importante el campo para agendar cita.",
                        url: (this.config.urls?.agendar_cita || '/servicios_escolares/agendar-cita/0').replace('/0', '/16'),
                        selector: "#id_motivo, textarea[name='motivo'], .motivo-textarea, textarea",
                        accion: null
                    },
                    {
                        titulo: "Definir Duración",
                        texto: "Selecciona la duración de la cita (30-60 min recomendado).",
                        url: (this.config.urls?.agendar_cita || '/servicios_escolares/agendar-cita/0').replace('/0', '/16'),
                        selector: "#id_duracion, select[name='duracion'], .duracion-select, select",
                        accion: null
                    },
                    {
                        titulo: "Confirmar Cita",
                        texto: "Haz clic en 'Agendar Cita' para finalizar.",
                        url: (this.config.urls?.agendar_cita || '/servicios_escolares/agendar-cita/0').replace('/0', '/16'),
                        selector: "button[type='submit'], .btn-agendar, input[type='submit'], button:has(span:contains('Agendar'))",
                        accion: null
                    }
                ]
            },
            'gestionar_calendario': {
                nombre: "Gestión de Calendario",
                descripcion: "Aprende a gestionar y visualizar el calendario de citas",
                pasos: [
                    {
                        titulo: "Acceder al Calendario",
                        texto: "Desde el dashboard, haz clic en 'Calendario' o 'Ver todas las citas'.",
                        url: this.config.urls?.dashboard || "/",
                        selector: "[href*='calendario'], [href*='citas'], .btn-calendario",
                        accion: null
                    },
                    {
                        titulo: "Navegar entre Fechas",
                        texto: "Usa los botones de anterior/siguiente para navegar entre meses o semanas.",
                        url: this.config.urls?.calendario || "/calendario/",
                        selector: ".fc-prev-button, .fc-next-button, .btn-prev, .btn-next",
                        accion: null
                    },
                    {
                        titulo: "Ver Detalles de Cita",
                        texto: "Haz clic en cualquier cita del calendario para ver sus detalles.",
                        url: this.config.urls?.calendario || "/calendario/",
                        selector: ".fc-event, .evento-cita, [data-cita-id]",
                        accion: null
                    },
                    {
                        titulo: "Filtrar Citas",
                        texto: "Usa los filtros para ver citas por estado, grado o fecha.",
                        url: this.config.urls?.calendario || "/calendario/",
                        selector: "#filtro-estado, .filtro-select, select[name='filtro']",
                        accion: null
                    }
                ]
            },
            'generar_reportes': {
                nombre: "Generar Reportes",
                descripcion: "Aprende a generar reportes estadísticos del sistema",
                pasos: [
                    {
                        titulo: "Acceder a Reportes",
                        texto: "Desde el menú principal, selecciona 'Reportes' o 'Estadísticas'.",
                        url: this.config.urls?.dashboard || "/",
                        selector: "[href*='reportes'], [href*='estadisticas'], .btn-reportes",
                        accion: null
                    },
                    {
                        titulo: "Seleccionar Tipo de Reporte",
                        texto: "Elige el tipo de reporte que deseas generar (citas por mes, por grado, etc).",
                        url: this.config.urls?.reportes || "/reportes/",
                        selector: ".tipo-reporte, .report-card, [data-reporte-tipo]",
                        accion: null
                    },
                    {
                        titulo: "Configurar Parámetros",
                        texto: "Selecciona el rango de fechas y otros filtros para el reporte.",
                        url: this.config.urls?.reportes || "/reportes/",
                        selector: "#fecha_inicio, #fecha_fin, .fecha-input",
                        accion: null
                    },
                    {
                        titulo: "Generar Reporte",
                        texto: "Haz clic en 'Generar' para crear el reporte con los parámetros seleccionados.",
                        url: this.config.urls?.reportes || "/reportes/",
                        selector: "button[type='submit'], .btn-generar, .btn-descargar",
                        accion: null
                    }
                ]
            },
            'gestionar_usuarios': {
                nombre: "Gestión de Usuarios",
                descripcion: "Aprende a gestionar usuarios y permisos en el sistema",
                pasos: [
                    {
                        titulo: "Acceder a Usuarios",
                        texto: "Desde el panel de administración, selecciona 'Usuarios' o 'Gestión de usuarios'.",
                        url: this.config.urls?.dashboard || "/",
                        selector: "[href*='usuarios'], [href*='gestion-usuarios'], .btn-usuarios",
                        accion: null
                    },
                    {
                        titulo: "Ver Lista de Usuarios",
                        texto: "Revisa la lista completa de usuarios registrados en el sistema.",
                        url: this.config.urls?.usuarios || "/usuarios/",
                        selector: ".user-list, .table-usuarios, tbody tr:first-child",
                        accion: null
                    },
                    {
                        titulo: "Agregar Nuevo Usuario",
                        texto: "Haz clic en 'Agregar Usuario' o 'Nuevo' para crear un nuevo usuario.",
                        url: this.config.urls?.usuarios || "/usuarios/",
                        selector: ".btn-agregar-usuario, [href*='nuevo'], .btn-success",
                        accion: null
                    },
                    {
                        titulo: "Editar Usuario",
                        texto: "Selecciona un usuario de la lista y haz clic en 'Editar' para modificar sus datos.",
                        url: this.config.urls?.usuarios || "/usuarios/",
                        selector: ".btn-editar, [href*='editar'], .btn-warning",
                        accion: null
                    }
                ]
            }
        };
    }

    init() {
        if (this.estaInicializado) {
            console.log('Tutorial ya está inicializado');
            return;
        }

        console.log('Configurando event listeners...');

        // Configurar controles principales
        const iniciarBtn = document.getElementById('iniciarDemo');
        const reiniciarBtn = document.getElementById('reiniciarDemo');

        if (iniciarBtn) {
            iniciarBtn.addEventListener('click', (e) => {
                console.log('Botón Iniciar clickeado');
                e.stopPropagation();

                // Si hay tutorial seleccionado, iniciarlo
                if (this.tutorialActual) {
                    this.iniciar(this.tutorialActual);
                } else {
                    // Si no, preguntar qué tutorial ejecutar
                    this.mostrarSelectorTutoriales();
                }
            });
        }

        if (reiniciarBtn) {
            reiniciarBtn.addEventListener('click', () => {
                console.log('Reiniciando tutorial...');
                if (this.tutorialActual) {
                    this.reiniciar();
                }
            });
        }

        // Popup controls
        document.getElementById('popupAnterior')?.addEventListener('click', () => this.anteriorPaso());
        document.getElementById('popupSiguiente')?.addEventListener('click', () => this.siguientePaso());
        document.getElementById('popupSaltar')?.addEventListener('click', () => this.terminar());
        document.querySelector('.btn-close-popup')?.addEventListener('click', () => this.terminar());

        // Teclado
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.terminar();
            if (e.key === 'ArrowRight') this.siguientePaso();
            if (e.key === 'ArrowLeft') this.anteriorPaso();
        });

        // Cargar selector de tutoriales
        this.cargarSelectorTutoriales();

        this.estaInicializado = true;
        console.log('Tutorial inicializado correctamente');
    }

    cargarSelectorTutoriales() {
        const lista = document.getElementById('listaPasos');
        if (!lista) return;

        // Limpiar lista
        lista.innerHTML = '';

        const tutoriales = this.getTutoriales();

        // Crear encabezado
        const header = document.createElement('div');
        header.className = 'list-group-header p-3 bg-light';
        header.innerHTML = `
            <h6 class="mb-2"><i class="fas fa-graduation-cap"></i> Tutoriales Disponibles</h6>
            <small class="text-muted">Selecciona un tutorial para comenzar</small>
        `;
        lista.appendChild(header);

        // Agregar cada tutorial
        Object.entries(tutoriales).forEach(([id, tutorial]) => {
            const item = document.createElement('a');
            item.href = '#';
            item.className = 'list-group-item list-group-item-action tutorial-item';
            item.dataset.tutorialId = id;
            item.innerHTML = `
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${tutorial.nombre}</h6>
                    <small class="text-muted">${tutorial.pasos.length} pasos</small>
                </div>
                <small class="text-muted">${tutorial.descripcion}</small>
            `;

            item.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('Seleccionando tutorial:', id);
                this.seleccionarTutorial(id);
            });

            lista.appendChild(item);
        });
    }

    seleccionarTutorial(tutorialId) {
        const tutoriales = this.getTutoriales();
        const tutorial = tutoriales[tutorialId];

        if (!tutorial) {
            console.error('Tutorial no encontrado:', tutorialId);
            return;
        }

        this.tutorialActual = {
            id: tutorialId,
            nombre: tutorial.nombre,
            pasos: tutorial.pasos
        };

        console.log('Tutorial seleccionado:', this.tutorialActual.nombre);

        // Actualizar UI
        document.getElementById('paginaActual').textContent = tutorial.nombre;

        // Cargar pasos del tutorial
        this.cargarListaPasos();

        // Mostrar botón para iniciar
        const lista = document.getElementById('listaPasos');
        if (lista) {
            const startBtn = document.createElement('div');
            startBtn.className = 'p-3 text-center';
            startBtn.innerHTML = `
                <button class="btn btn-primary w-100 iniciar-tutorial-btn">
                    <i class="fas fa-play"></i> Iniciar "${tutorial.nombre}"
                </button>
            `;
            lista.appendChild(startBtn);

            // Agregar event listener al botón
            document.querySelector('.iniciar-tutorial-btn')?.addEventListener('click', () => {
                this.iniciar(this.tutorialActual);
            });
        }
    }

    cargarListaPasos() {
        if (!this.tutorialActual) return;

        const lista = document.getElementById('listaPasos');
        if (!lista) return;

        // Limpiar lista
        lista.innerHTML = '';

        // Encabezado del tutorial
        const header = document.createElement('div');
        header.className = 'list-group-header p-3 bg-light';
        header.innerHTML = `
            <h6 class="mb-1"><i class="fas fa-graduation-cap"></i> ${this.tutorialActual.nombre}</h6>
            <small class="text-muted">${this.tutorialActual.pasos.length} pasos</small>
        `;
        lista.appendChild(header);

        // Listar pasos
        this.tutorialActual.pasos.forEach((paso, index) => {
            const item = document.createElement('a');
            item.href = '#';
            item.className = 'list-group-item list-group-item-action paso-item';
            item.dataset.pasoIndex = index;
            item.innerHTML = `
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${index + 1}. ${paso.titulo}</h6>
                    <small class="text-muted">${index + 1}/${this.tutorialActual.pasos.length}</small>
                </div>
                <small class="text-muted">${paso.texto.substring(0, 60)}...</small>
            `;

            item.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('Navegando al paso', index);
                this.irAPaso(index);
            });

            lista.appendChild(item);
        });

        // Botón para volver a selección
        const backBtn = document.createElement('div');
        backBtn.className = 'p-3 text-center';
        backBtn.innerHTML = `
            <button class="btn btn-outline-secondary w-100 volver-tutoriales-btn">
                <i class="fas fa-arrow-left"></i> Volver a Tutoriales
            </button>
        `;
        lista.appendChild(backBtn);

        document.querySelector('.volver-tutoriales-btn')?.addEventListener('click', () => {
            this.cargarSelectorTutoriales();
            this.tutorialActual = null;
            document.getElementById('paginaActual').textContent = 'Seleccionar Tutorial';
        });
    }

    iniciar(tutorial) {
        if (!tutorial) {
            console.error('No hay tutorial seleccionado');
            return;
        }

        console.log('Iniciando tutorial:', tutorial.nombre);
        this.tutorialActual = tutorial;
        this.pasoActual = 0;
        this.mostrarPopup();
        this.irAPaso(0);
    }

    reiniciar() {
        console.log('Reiniciando tutorial...');
        this.terminar();
        setTimeout(() => {
            if (this.tutorialActual) {
                this.pasoActual = 0;
                this.mostrarPopup();
                this.irAPaso(0);
            }
        }, 500);
    }

    irAPaso(index) {
        if (!this.tutorialActual || index < 0 || index >= this.tutorialActual.pasos.length) {
            console.error('Índice de paso inválido:', index);
            return;
        }

        console.log('Yendo al paso', index, 'de', this.tutorialActual.pasos.length);
        this.pasoActual = index;
        const paso = this.tutorialActual.pasos[index];

        // Actualizar indicador de página
        const paginaActual = document.getElementById('paginaActual');
        if (paginaActual) {
            paginaActual.textContent = `${this.tutorialActual.nombre} - ${paso.titulo}`;
        }

        // Actualizar lista de pasos
        this.actualizarListaPasos();

        // Cargar URL en el iframe
        if (this.iframe && paso.url) {
            console.log('Cargando URL en iframe:', paso.url);
            this.iframe.src = paso.url;

            // Esperar a que cargue el iframe
            this.iframe.onload = () => {
                console.log('Iframe cargado, mostrando instrucciones...');
                setTimeout(() => {
                    this.mostrarPopup();
                }, 800);
            };

            // Manejar errores de carga
            this.iframe.onerror = () => {
                console.error('Error cargando URL en iframe:', paso.url);
                alert(`Error cargando la página: ${paso.url}\nVerifica que la URL sea correcta.`);
            };
        } else {
            console.error('Iframe o URL no disponible');
        }
    }

    mostrarPopup() {
        if (!this.tutorialActual) return;

        const paso = this.tutorialActual.pasos[this.pasoActual];
        console.log('Mostrando popup para paso:', this.pasoActual);

        // Actualizar contenido
        const popupTitulo = document.getElementById('popupTitulo');
        const popupTexto = document.getElementById('popupTexto');
        const popupPasoActual = document.getElementById('popupPasoActual');
        const popupTotalPasos = document.getElementById('popupTotalPasos');
        const popupProgreso = document.getElementById('popupProgreso');

        if (popupTitulo) popupTitulo.textContent = paso.titulo;
        if (popupTexto) popupTexto.textContent = paso.texto;
        if (popupPasoActual) popupPasoActual.textContent = this.pasoActual + 1;
        if (popupTotalPasos) popupTotalPasos.textContent = this.tutorialActual.pasos.length;
        if (popupProgreso) {
            popupProgreso.style.width = `${((this.pasoActual + 1) / this.tutorialActual.pasos.length) * 100}%`;
        }

        // Posicionar y mostrar popup
        this.popup.style.display = 'block';
        this.popup.style.zIndex = '10001';
    }

    siguientePaso() {
        console.log('Siguiente paso...');
        if (this.tutorialActual && this.pasoActual < this.tutorialActual.pasos.length - 1) {
            this.pasoActual++;
            this.irAPaso(this.pasoActual);
        } else {
            this.completarDemo();
        }
    }

    anteriorPaso() {
        console.log('Anterior paso...');
        if (this.tutorialActual && this.pasoActual > 0) {
            this.pasoActual--;
            this.irAPaso(this.pasoActual);
        }
    }

    actualizarListaPasos() {
        if (!this.tutorialActual) return;

        const items = document.querySelectorAll('#listaPasos .paso-item');
        items.forEach((item, index) => {
            item.classList.remove('paso-activo', 'paso-completado');

            if (index < this.pasoActual) {
                item.classList.add('paso-completado');
            } else if (index === this.pasoActual) {
                item.classList.add('paso-activo');
            }
        });
    }

    completarDemo() {
        console.log('¡Tutorial completado!');
        // Mostrar mensaje de finalización
        const mensaje = `🎉 ¡Tutorial "${this.tutorialActual.nombre}" completado!\n\n¿Qué deseas hacer ahora?`;

        if (confirm(mensaje + "\n\n• OK: Volver a tutoriales\n• Cancelar: Continuar en la página actual")) {
            this.terminar();
            // Regresar a selección de tutoriales
            this.cargarSelectorTutoriales();
            this.tutorialActual = null;
            document.getElementById('paginaActual').textContent = 'Seleccionar Tutorial';
        } else {
            this.terminar();
        }
    }

    terminar() {
        console.log('Terminando tutorial...');
        // Ocultar popup
        this.popup.style.display = 'none';

        // Resetear lista
        this.actualizarListaPasos();
    }

    mostrarSelectorTutoriales() {
        // Mostrar modal o cambiar vista para seleccionar tutorial
        this.cargarSelectorTutoriales();
        document.getElementById('paginaActual').textContent = 'Seleccionar Tutorial';
    }
}

// Inicializar cuando cargue la página
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM cargado, inicializando tutoriales...');

    // Prevenir múltiples instancias
    if (window.tutorialInteractivoInstance) {
        console.warn('Ya existe una instancia de tutorial interactivo');
        return;
    }

    try {
        window.tutorialInteractivoInstance = new TutorialInteractivo(window.DEMO_CONFIG || {});
        console.log('Instancia de tutorial creada:', window.tutorialInteractivoInstance);
    } catch (error) {
        console.error('Error creando instancia de tutorial:', error);
    }
});