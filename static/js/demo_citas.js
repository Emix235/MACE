// static/js/demo_citas.js - VERSIÓN SIMPLIFICADA Y FUNCIONAL

// Variable para controlar estado
let demoActiva = false;

class DemostracionCitas {
    constructor() {
        this.pasos = [
            {selector: '#iniciarDemo', texto: 'Haz clic aquí para iniciar el tutorial de citas'},
            {selector: '[href*="panel_citas"]', texto: 'Haz clic en "Nueva Cita" para comenzar'},
            {selector: '.grado-card:first-child', texto: 'Selecciona un grado académico'},
            {selector: 'a[href*="grupo_id"]:first-child', texto: 'Elige un grupo de este grado'},
            {selector: 'a.btn-success:first-child', texto: 'Haz clic en "Nueva" junto al estudiante'},
            {selector: '#id_fecha_hora_inicio', texto: 'Selecciona fecha y hora para la cita'},
            {selector: '#id_motivo', texto: 'Describe el motivo de la reunión'},
            {selector: '#id_duracion', texto: 'Define la duración (30-60 minutos recomendado)'},
            {selector: 'button[type="submit"]', texto: 'Confirma haciendo clic en "Agendar Cita"'},
            {selector: '.ayuda-flotante', texto: '¿Tienes dudas? Usa el botón de Ayuda en cualquier momento'}
        ];

        this.pasoActual = 0;
        this.popup = null;
        this.overlay = null;
        this.elementoActual = null;
    }

    iniciar() {
        // Evitar múltiples demos
        if (demoActiva) {
            console.log('Demo ya está activa');
            return;
        }

        demoActiva = true;
        this.crearOverlay();
        this.crearPopup();
        this.mostrarPaso(0);
    }

    crearOverlay() {
        // Eliminar overlay existente
        const overlays = document.querySelectorAll('.demo-overlay');
        overlays.forEach(overlay => overlay.remove());

        this.overlay = document.createElement('div');
        this.overlay.className = 'demo-overlay';
        document.body.appendChild(this.overlay);
    }

    crearPopup() {
        // Eliminar popup existente
        const popups = document.querySelectorAll('.demo-popup');
        popups.forEach(popup => popup.remove());

        this.popup = document.createElement('div');
        this.popup.className = 'demo-popup';
        this.popup.innerHTML = `
            <div class="demo-header">
                <h5><i class="fas fa-graduation-cap"></i> Tutorial: Agendar Cita</h5>
                <small>Paso <span id="demo-contador">1</span> de ${this.pasos.length}</small>
            </div>
            <div class="demo-body">
                <p id="demo-texto"></p>
                <div class="demo-progress">
                    <div class="progress">
                        <div id="demo-barra" class="progress-bar" style="width: 0%"></div>
                    </div>
                </div>
            </div>
            <div class="demo-footer">
                <button id="demo-anterior" class="btn btn-sm btn-outline-secondary">
                    <i class="fas fa-arrow-left"></i> Anterior
                </button>
                <button id="demo-siguiente" class="btn btn-sm btn-primary">
                    Siguiente <i class="fas fa-arrow-right"></i>
                </button>
                <button id="demo-cerrar" class="btn btn-sm btn-link">
                    Saltar
                </button>
            </div>
        `;

        document.body.appendChild(this.popup);

        // Configurar eventos una sola vez
        this.popup.addEventListener('click', (e) => {
            if (e.target.closest('#demo-siguiente')) {
                this.siguientePaso();
            } else if (e.target.closest('#demo-anterior')) {
                this.pasoAnterior();
            } else if (e.target.closest('#demo-cerrar')) {
                this.terminar();
            }
        });

        // Teclado
        this.keyHandler = (e) => {
            if (e.key === 'Escape') this.terminar();
            if (e.key === 'ArrowRight') this.siguientePaso();
            if (e.key === 'ArrowLeft') this.pasoAnterior();
        };
        document.addEventListener('keydown', this.keyHandler);
    }

    mostrarPaso(index) {
        const paso = this.pasos[index];

        // Actualizar texto
        const texto = document.getElementById('demo-texto');
        const contador = document.getElementById('demo-contador');
        const barra = document.getElementById('demo-barra');
        const siguiente = document.getElementById('demo-siguiente');
        const anterior = document.getElementById('demo-anterior');

        if (texto) texto.textContent = paso.texto;
        if (contador) contador.textContent = index + 1;
        if (barra) barra.style.width = `${((index + 1) / this.pasos.length) * 100}%`;

        // Buscar elemento
        this.elementoActual = document.querySelector(paso.selector);

        if (this.elementoActual) {
            // Quitar focus anterior
            if (this.elementoAnterior) {
                this.elementoAnterior.classList.remove('demo-elemento-activo');
            }

            // Aplicar focus
            this.elementoActual.classList.add('demo-elemento-activo');
            this.elementoAnterior = this.elementoActual;

            // Scroll
            this.elementoActual.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });

            // Agujero en overlay
            this.crearAgujeroOverlay(this.elementoActual);

            // Posicionar popup
            this.posicionarPopup(this.elementoActual);

            // Botón siguiente
            if (siguiente) {
                siguiente.innerHTML = index === this.pasos.length - 1
                    ? 'Finalizar <i class="fas fa-check"></i>'
                    : 'Siguiente <i class="fas fa-arrow-right"></i>';
            }
        }

        // Botón anterior
        if (anterior) {
            anterior.disabled = index === 0;
        }
    }

    crearAgujeroOverlay(elemento) {
        if (!this.overlay) return;

        const rect = elemento.getBoundingClientRect();
        this.overlay.style.clipPath = `
            polygon(0% 0%, 0% 100%, 100% 100%, 100% 0%,
                ${rect.right}px ${rect.top}px,
                ${rect.right}px ${rect.bottom}px,
                ${rect.left}px ${rect.bottom}px,
                ${rect.left}px ${rect.top}px)
        `;
    }

    posicionarPopup(elemento) {
        if (!this.popup) return;

        const rect = elemento.getBoundingClientRect();
        const popupHeight = this.popup.offsetHeight;

        // Decidir posición
        let topPosition;
        if (rect.bottom + popupHeight + 20 > window.innerHeight) {
            topPosition = rect.top - popupHeight - 20;
        } else {
            topPosition = rect.bottom + 20;
        }

        // Centrar
        const leftPosition = Math.max(20, rect.left - (350 - rect.width) / 2);

        this.popup.style.top = `${Math.max(20, topPosition)}px`;
        this.popup.style.left = `${Math.min(leftPosition, window.innerWidth - 370)}px`;
    }

    siguientePaso() {
        if (this.pasoActual < this.pasos.length - 1) {
            this.pasoActual++;
            this.mostrarPaso(this.pasoActual);
        } else {
            this.terminar();
        }
    }

    pasoAnterior() {
        if (this.pasoActual > 0) {
            this.pasoActual--;
            this.mostrarPaso(this.pasoActual);
        }
    }

    terminar() {
        // Limpiar
        if (this.popup) this.popup.remove();
        if (this.overlay) this.overlay.remove();

        // Remover listener de teclado
        if (this.keyHandler) {
            document.removeEventListener('keydown', this.keyHandler);
        }

        // Limpiar clases
        document.querySelectorAll('.demo-elemento-activo').forEach(el => {
            el.classList.remove('demo-elemento-activo');
        });

        // Resetear
        demoActiva = false;
        this.pasoActual = 0;

        // Mensaje final
        this.mostrarMensajeFinal();
    }

    mostrarMensajeFinal() {
        const mensaje = document.createElement('div');
        mensaje.className = 'demo-final';
        mensaje.innerHTML = `
            <div class="demo-final-contenido">
                <i class="fas fa-check-circle text-success mb-2"></i>
                <h6>¡Tutorial Completado!</h6>
                <p class="small">Ahora sabes cómo agendar una cita.</p>
            </div>
        `;

        document.body.appendChild(mensaje);

        // Auto-remover
        setTimeout(() => {
            if (mensaje.parentNode) mensaje.remove();
        }, 3000);
    }
}

// INICIALIZACIÓN SIMPLE
document.addEventListener('DOMContentLoaded', function() {
    // Crear instancia
    window.demoCitas = new DemostracionCitas();

    // Configurar botón
    const boton = document.getElementById('iniciarDemo');
    if (boton) {
        boton.addEventListener('click', function(e) {
            e.preventDefault();
            if (window.demoCitas) {
                window.demoCitas.iniciar();
            }
        });
    }
});