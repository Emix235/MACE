// ========== BLOQUEAR NAVEGACIÓN FUERA DEL IFRAME ==========
// ========== BLOQUEAR NAVEGACIÓN FUERA DEL IFRAME ==========
class BloqueadorNavegacion {
  constructor(iframe) {
    this.iframe = iframe;
    this.estaActivado = false;
    this.urlOriginal = null;
  }

  activar() {
    if (this.estaActivado) return;
    
    this.estaActivado = true;
    this.urlOriginal = window.location.href;
    
    // 1. Bloquear clicks en enlaces externos
    document.querySelectorAll('a:not(.tutorial-control):not(.btn-cancelar-tutorial):not(.btn-scroll)').forEach(enlace => {
      if (!enlace.hasAttribute('data-tutorial-safe')) {
        enlace.addEventListener('click', this.bloquearClick.bind(this));
        enlace.style.cursor = 'not-allowed';
        enlace.style.opacity = '0.5';
      }
    });
    
    // 2. Bloquear navegación con teclado
    document.addEventListener('keydown', this.bloquearTeclado.bind(this));
    
    // 3. Bloquear cambios de URL
    window.addEventListener('beforeunload', this.bloquearCambioURL.bind(this));
    
    // 4. Crear overlay semi-transparente sobre los controles
    this.crearOverlay();
    
    // 5. Enfocar el iframe
    this.iframe.focus();
    
    console.log('🔒 Navegación bloqueada fuera del iframe');
  }
  
  desactivar() {
    if (!this.estaActivado) return;
    
    this.estaActivado = false;
    
    // Restaurar enlaces
    document.querySelectorAll('a:not(.tutorial-control):not(.btn-cancelar-tutorial):not(.btn-scroll)').forEach(enlace => {
      enlace.removeEventListener('click', this.bloquearClick.bind(this));
      enlace.style.cursor = '';
      enlace.style.opacity = '';
    });
    
    // Remover event listeners
    document.removeEventListener('keydown', this.bloquearTeclado.bind(this));
    window.removeEventListener('beforeunload', this.bloquearCambioURL.bind(this));
    
    // Remover overlay
    const overlay = document.getElementById('tutorialOverlay');
    if (overlay) overlay.remove();
    
    console.log('🔓 Navegación desbloqueada');
  }
  
  bloquearClick(e) {
    e.preventDefault();
    e.stopPropagation();
    this.mostrarAdvertencia('⚠️ Completa el tutorial o presiona "Cancelar Tutorial"');
    return false;
  }
  
  bloquearTeclado(e) {
    const teclasPermitidas = ['ArrowLeft', 'ArrowRight', 'Escape'];
    
    if (e.ctrlKey && (e.key === 'w' || e.key === 'r' || e.key === 'F5')) {
      e.preventDefault();
      this.mostrarAdvertencia('⚠️ No puedes recargar durante el tutorial');
      return false;
    }
    
    if (!teclasPermitidas.includes(e.key) && !e.ctrlKey && !e.altKey) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight' && e.key !== 'Escape') {
        e.preventDefault();
      }
    }
  }
  
  bloquearCambioURL(e) {
    if (this.estaActivado) {
      e.preventDefault();
      e.returnValue = '¿Estás seguro? El tutorial no está completo.';
      return false;
    }
  }
  
  crearOverlay() {
    const existingOverlay = document.getElementById('tutorialOverlay');
    if (existingOverlay) existingOverlay.remove();
    
    const overlay = document.createElement('div');
    overlay.id = 'tutorialOverlay';
    
    // Crear el contenido primero
    const contentDiv = document.createElement('div');
    contentDiv.className = 'tutorial-overlay-content';
    contentDiv.innerHTML = `
      <i class="fas fa-lock"></i>
      <p><strong>Tutorial Activo</strong></p>
      <p>Completa el tutorial o presiona <kbd>ESC</kbd> o "Cancelar Tutorial" para salir</p>
    `;
    
    // Agregar el contenido al overlay ANTES de aplicar estilos que dependen de firstChild
    overlay.appendChild(contentDiv);
    
    // Aplicar estilos al overlay
    Object.assign(overlay.style, {
      position: 'fixed',
      top: '0',
      left: '0',
      width: '100%',
      height: '100%',
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
      zIndex: '9999',
      pointerEvents: 'none',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'all 0.3s ease'
    });
    
    // Aplicar estilos al contenido
    Object.assign(contentDiv.style, {
      backgroundColor: 'rgba(0, 0, 0, 0.9)',
      color: 'white',
      padding: '20px',
      borderRadius: '10px',
      textAlign: 'center',
      border: '2px solid #e94560',
      boxShadow: '0 0 20px rgba(233, 69, 96, 0.5)',
      maxWidth: '300px'
    });
    
    document.body.appendChild(overlay);
    
    setTimeout(() => {
      overlay.style.opacity = '0';
      setTimeout(() => {
        if (overlay.parentNode) overlay.remove();
      }, 300);
    }, 2000);
  }
  
  mostrarAdvertencia(mensaje) {
    const toast = document.createElement('div');
    toast.textContent = mensaje;
    Object.assign(toast.style, {
      position: 'fixed',
      bottom: '20px',
      right: '20px',
      backgroundColor: '#e94560',
      color: 'white',
      padding: '10px 20px',
      borderRadius: '5px',
      zIndex: '10000',
      animation: 'fadeInOut 2s ease'
    });
    
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
  }
}

// Agregar animación CSS
const style = document.createElement('style');
style.textContent = `
  @keyframes fadeInOut {
    0% { opacity: 0; transform: translateY(20px); }
    15% { opacity: 1; transform: translateY(0); }
    85% { opacity: 1; transform: translateY(0); }
    100% { opacity: 0; transform: translateY(-20px); }
  }
  
  .tutorial-active {
    overflow: hidden !important;
  }
  
  iframe {
    transition: all 0.3s ease;
  }
  
  .tutorial-focus iframe {
    box-shadow: 0 0 0 3px #e94560, 0 0 0 6px rgba(233, 69, 96, 0.3);
  }
  
  /* Estilos para el botón de cancelar */
  .btn-cancelar-tutorial {
    background: linear-gradient(135deg, #dc3545, #c82333) !important;
    color: white !important;
    border: none !important;
    transition: all 0.3s ease !important;
    font-weight: bold !important;
  }
  
  .btn-cancelar-tutorial:hover {
    background: linear-gradient(135deg, #c82333, #bd2130) !important;
    transform: scale(1.05) !important;
    box-shadow: 0 4px 12px rgba(220, 53, 69, 0.4) !important;
  }
  
  /* Deshabilitar scroll durante tutorial */
  .tutorial-active body {
    overflow: hidden !important;
    position: fixed !important;
    width: 100% !important;
  }
  
  /* Asegurar que el iframe sea visible */
  .tutorial-focus {
    scroll-behavior: smooth !important;
  }
  
  .tutorial-focus .card:has(iframe) {
    z-index: 1000 !important;
    position: relative !important;
  }
  
  /* Scroll suave para la lista de pasos */
  #listaPasos {
    max-height: 120px;
    overflow-y: auto;
    scroll-behavior: smooth;
  }
  
  #listaPasos::-webkit-scrollbar {
    width: 6px;
  }
  
  #listaPasos::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 10px;
  }
  
  #listaPasos::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 10px;
  }
  
  #listaPasos::-webkit-scrollbar-thumb:hover {
    background: #555;
  }
  
  /* Botones de navegación */
  .btn-scroll {
    transition: all 0.3s ease;
  }
  
  .btn-scroll:hover {
    transform: scale(1.05);
  }
`;
document.head.appendChild(style);

// Prevenir múltiples cargas del script
if (window.demoCompletaLoaded) {
  console.warn("Script demo_completa.js ya cargado, abortando.");
  throw new Error("demo_completa.js ya cargado");
}
window.demoCompletaLoaded = true;

class TutorialInteractivo {
  constructor(config) {
    console.log("Inicializando TutorialInteractivo...");

    this.config = config || {};
    this.tutorialActual = null;
    this.bloqueador = null;
    this.pasoActual = 0;
    this.tutorialIniciado = false;
    this.tutorialCargado = false;
    this.iniciandoTutorial = false; // NUEVA: evita múltiples ejecuciones

    this.iframe = document.getElementById("demoIframe");
    this.popup = document.getElementById("demoPopup");
    this.estaInicializado = false;

    this.init();
  }

  getTutoriales() {
    const role = window.USER_ROLE || "default";
    return getTutorialesByRole(role);
  }

  getTutorialesList() {
    const role = window.USER_ROLE || "default";
    return getTutorialesList(role);
  }

  scrollToIframe() {
    const iframeContainer = document.getElementById('iframeContainer');
    if (iframeContainer) {
        iframeContainer.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center',
            inline: 'center'
        });
    }
  }

  scrollToInstrucciones() {
    const instruccionesCard = document.querySelector('#listaPasos').closest('.card');
    if (instruccionesCard) {
      instruccionesCard.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'start',
        inline: 'center'
      });
    }
  }

  init() {
    if (this.estaInicializado) {
        console.log("Tutorial ya está inicializado");
        return;
    }

    console.log("Configurando event listeners...");

    // PRIMERO: Cargar tutorial desde URL (sincrónico)
    this.autoCargarTutorialDesdeURL();

    const iniciarBtn = document.getElementById("iniciarDemo");
    const reiniciarBtn = document.getElementById("reiniciarDemo");
    const cancelarBtn = document.getElementById("cancelarTutorial");

    if (iniciarBtn) {
        if (this.iniciarHandler) {
            iniciarBtn.removeEventListener('click', this.iniciarHandler);
        }
        
        this.iniciarHandler = (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log("Botón Iniciar clickeado");
            
            // Evitar múltiples ejecuciones mientras ya se está iniciando
            if (this.iniciandoTutorial) {
                console.log("Ya se está iniciando el tutorial, ignorando...");
                return;
            }
            
            if (this.tutorialActual && !this.tutorialIniciado) {
                this.iniciarTutorial();
            } else if (!this.tutorialActual) {
                this.cargarSelectorTutoriales();
                this.mostrarMensaje("Selecciona un tutorial de la lista", "info");
            } else if (this.tutorialIniciado) {
                this.mostrarMensaje("El tutorial ya está en curso", "info");
            }
        };
        
        iniciarBtn.addEventListener('click', this.iniciarHandler);
    }

    if (reiniciarBtn) {
        if (this.reiniciarHandler) {
            reiniciarBtn.removeEventListener('click', this.reiniciarHandler);
        }
        
        this.reiniciarHandler = () => {
            console.log("Reiniciando tutorial...");
            if (this.tutorialActual) {
                this.reiniciarTutorial();
            }
        };
        
        reiniciarBtn.addEventListener('click', this.reiniciarHandler);
    }

    if (cancelarBtn) {
        if (this.cancelarHandler) {
            cancelarBtn.removeEventListener('click', this.cancelarHandler);
        }
        
        this.cancelarHandler = () => {
            console.log("Cancelando tutorial...");
            this.terminarTutorial();
            this.mostrarMensaje("Tutorial cancelado", "info");
        };
        
        cancelarBtn.addEventListener('click', this.cancelarHandler);
    }

    document.addEventListener("keydown", (e) => {
        if (!this.tutorialIniciado) return;
        if (e.key === "Escape") {
            this.terminarTutorial();
            this.mostrarMensaje("Tutorial cancelado", "info");
        }
        if (e.key === "ArrowRight") this.siguientePaso();
        if (e.key === "ArrowLeft") this.anteriorPaso();
    });

    // Si no hay tutorial cargado desde URL, mostrar selector
    if (!this.tutorialActual) {
        this.cargarSelectorTutoriales();
    }
    
    this.estaInicializado = true;
    console.log("Tutorial inicializado correctamente");
  }

  mostrarMensaje(mensaje, tipo = "success") {
    const toast = document.createElement('div');
    toast.className = `tutorial-mensaje tutorial-mensaje-${tipo}`;
    toast.innerHTML = `
      <div class="mensaje-contenido">
        <i class="fas ${tipo === 'success' ? 'fa-check-circle' : tipo === 'info' ? 'fa-info-circle' : 'fa-exclamation-circle'}"></i>
        <span>${mensaje}</span>
      </div>
    `;
    
    Object.assign(toast.style, {
      position: 'fixed',
      top: '20px',
      left: '50%',
      transform: 'translateX(-50%)',
      backgroundColor: tipo === 'success' ? '#28a745' : tipo === 'info' ? '#17a2b8' : '#dc3545',
      color: 'white',
      padding: '12px 24px',
      borderRadius: '8px',
      zIndex: '10002',
      animation: 'slideDown 0.3s ease',
      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
      fontWeight: 'bold'
    });
    
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  cargarSelectorTutoriales() {
    const lista = document.getElementById("listaPasos");
    if (!lista) return;

    lista.innerHTML = "";

    const tutorialesList = this.getTutorialesList();

    const header = document.createElement("div");
    header.className = "list-group-header p-3 bg-light";
    header.innerHTML = `
      <h6 class="mb-2"><i class="fas fa-graduation-cap"></i> Tutoriales Disponibles</h6>
      <small class="text-muted">Selecciona un tutorial para comenzar</small>
    `;
    lista.appendChild(header);

    tutorialesList.forEach(({ id, nombre, descripcion, pasosCount }) => {
      const item = document.createElement("a");
      item.href = "#";
      item.className = "list-group-item list-group-item-action tutorial-item";
      item.dataset.tutorialId = id;
      item.innerHTML = `
        <div class="d-flex w-100 justify-content-between">
          <h6 class="mb-1">${nombre}</h6>
          <small class="text-muted">${pasosCount} pasos</small>
        </div>
        <small class="text-muted">${descripcion}</small>
      `;

      item.addEventListener("click", (e) => {
        e.preventDefault();
        console.log("Seleccionando tutorial:", id);
        this.seleccionarTutorial(id);
      });

      lista.appendChild(item);
    });
  }

  seleccionarTutorial(tutorialId) {
    const role = window.USER_ROLE || "default";
    const tutorial = getTutorialById(role, tutorialId);

    if (!tutorial) {
      console.error("Tutorial no encontrado:", tutorialId);
      return;
    }

    this.tutorialActual = {
      id: tutorialId,
      nombre: tutorial.nombre,
      pasos: tutorial.pasos,
    };
    
    this.tutorialIniciado = false;

    console.log("Tutorial seleccionado:", this.tutorialActual.nombre);

    document.getElementById("paginaActual").textContent = tutorial.nombre;
    document.getElementById("tutorialNombre").textContent = tutorial.nombre;
    this.cargarListaPasos();
    this.cargarOtrosTutoriales();
  }

  cargarListaPasos() {
    if (!this.tutorialActual) return;

    const lista = document.getElementById("listaPasos");
    if (!lista) return;

    lista.innerHTML = "";
    
    this.tutorialActual.pasos.forEach((paso, index) => {
        const item = document.createElement("a");
        item.href = "#";
        item.className = "list-group-item list-group-item-action paso-item";
        item.dataset.pasoIndex = index;
        item.innerHTML = `
            <div class="d-flex w-100 justify-content-between">
                <h6 class="mb-1">${index + 1}. ${paso.titulo}</h6>
                <small class="text-muted">${index + 1}/${this.tutorialActual.pasos.length}</small>
            </div>
            <small class="text-muted">${paso.texto.substring(0, 60)}...</small>
        `;

        item.addEventListener("click", (e) => {
            e.preventDefault();
            console.log("Navegando al paso", index);
            if (this.tutorialIniciado) {
                this.irAPaso(index);
            } else {
                this.mostrarMensaje("Debes iniciar el tutorial primero", "info");
            }
        });

        lista.appendChild(item);
    });

    const backBtn = document.createElement("div");
    backBtn.className = "p-3 text-center";
    backBtn.innerHTML = `
        <button class="btn btn-outline-secondary w-100 volver-tutoriales-btn">
            <i class="fas fa-arrow-left"></i> Volver a Tutoriales
        </button>
    `;
    lista.appendChild(backBtn);

    document
        .querySelector(".volver-tutoriales-btn")
        ?.addEventListener("click", () => {
            this.cargarSelectorTutoriales();
            this.tutorialActual = null;
            this.tutorialIniciado = false;
            document.getElementById("paginaActual").textContent = "Seleccionar Tutorial";
        });
  }

  // MÉTODO CORREGIDO: iniciarTutorial sin doble ejecución
  iniciarTutorial() {
    
    // Scroll al iframe
    this.scrollToIframe();
    
    // Verificar si ya está iniciado o en proceso de inicio
    if (this.tutorialIniciado) {
      this.mostrarMensaje("El tutorial ya está en curso", "info");
      return;
    }
    
    if (this.iniciandoTutorial) {
      console.log("El tutorial ya se está iniciando, espera...");
      return;
    }
    
    if (!this.tutorialActual) {
      console.error("No hay tutorial seleccionado");
      this.mostrarMensaje("Primero selecciona un tutorial", "info");
      return;
    }

    console.log("Iniciando tutorial:", this.tutorialActual.nombre);
    
    // Marcar que estamos iniciando
    this.iniciandoTutorial = true;
    
    // Deshabilitar el botón de inicio temporalmente
    const iniciarBtn = document.getElementById("iniciarDemo");
    if (iniciarBtn) {
      iniciarBtn.disabled = true;
      iniciarBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Iniciando...';
    }
    

    // Dar tiempo para que termine el scroll
    setTimeout(() => {
        // Crear bloqueador si no existe
        if (!this.bloqueador) {
            this.bloqueador = new BloqueadorNavegacion(this.iframe);
        }
        this.bloqueador.activar();
        
        document.body.classList.add('tutorial-active');
        document.body.classList.add('tutorial-focus');
        
        this.tutorialIniciado = true;
        this.pasoActual = 0;
        
        this.mostrarBotonesNavegacion();
        
        // Pequeño delay adicional para asegurar que todo esté listo
        setTimeout(() => {
            this.irAPaso(0);
            // Re-habilitar el botón de inicio después de iniciar
            if (iniciarBtn) {
              iniciarBtn.disabled = false;
              iniciarBtn.innerHTML = '<i class="fas fa-play"></i> Iniciar Tutorial';
            }
            // Marcar que terminamos de iniciar
            this.iniciandoTutorial = false;
        }, 300);
    }, 500);
  }

  mostrarBotonesNavegacion() {
    const navFooter = document.getElementById('navFooter');
    if (navFooter) {
        navFooter.style.display = 'block';
    }
    
    const scrollToIframeBtn = document.getElementById('scrollToIframeBtn');
    const scrollToInstruccionesBtn = document.getElementById('scrollToInstruccionesBtn');
    
    if (scrollToIframeBtn) {
        const newBtn = scrollToIframeBtn.cloneNode(true);
        scrollToIframeBtn.parentNode.replaceChild(newBtn, scrollToIframeBtn);
        newBtn.addEventListener('click', () => this.scrollToIframe());
    }
    
    if (scrollToInstruccionesBtn) {
        const newBtn = scrollToInstruccionesBtn.cloneNode(true);
        scrollToInstruccionesBtn.parentNode.replaceChild(newBtn, scrollToInstruccionesBtn);
        newBtn.addEventListener('click', () => this.scrollToInstrucciones());
    }
  }

  reiniciarTutorial() {
    console.log("Reiniciando tutorial...");
    if (this.tutorialIniciado) {
      this.terminarTutorial();
      setTimeout(() => {
        this.iniciarTutorial();
      }, 300);
    } else if (this.tutorialActual) {
      this.iniciarTutorial();
    }
  }

  terminarTutorial() {
    console.log("Terminando tutorial...");

    if (this.bloqueador) {
      this.bloqueador.desactivar();
    }

    document.body.classList.remove('tutorial-active');
    document.body.classList.remove('tutorial-focus');
    
    document.body.style.overflow = '';
    document.body.style.position = '';
    document.body.style.width = '';

    if (this.popup) {
      this.popup.style.display = "none";
    }
    
    const navFooter = document.getElementById('navFooter');
    if (navFooter) {
        navFooter.style.display = 'none';
    }

    this.tutorialIniciado = false;
    this.iniciandoTutorial = false; // Resetear flag de inicio
    this.limpiarResaltado();
    this.actualizarListaPasos();
  }

  irAPaso(index) {
    if (!this.tutorialIniciado) {
      this.mostrarMensaje("Debes iniciar el tutorial primero", "info");
      return;
    }

    this.limpiarResaltado();

    if (
      !this.tutorialActual ||
      index < 0 ||
      index >= this.tutorialActual.pasos.length
    ) {
      console.error("Índice de paso inválido:", index);
      return;
    }

    console.log("Yendo al paso", index, "de", this.tutorialActual.pasos.length);
    this.pasoActual = index;
    const paso = this.tutorialActual.pasos[index];

    const paginaActual = document.getElementById("paginaActual");
    if (paginaActual) {
      paginaActual.textContent = `${this.tutorialActual.nombre} - ${paso.titulo}`;
    }

    this.actualizarListaPasos();

    if (this.iframe && paso.url) {
      console.log("Cargando URL en iframe:", paso.url);
      this.iframe.src = paso.url;

      this.iframe.onload = () => {
        setTimeout(() => {
          if (paso.accion) {
            this.ejecutarAccion(paso.accion);
          }

          setTimeout(() => {
            if (paso.selector) {
              this.esperarElementoVisible(paso.selector, (el) => {
                this.mostrarIntroPaso(paso.selector, paso.texto);
              });
            }
          }, 500);
        }, 800);
      };

      this.iframe.onerror = () => {
        console.error("Error cargando URL en iframe:", paso.url);
        alert(`Error cargando la página: ${paso.url}\nVerifica que la URL sea correcta.`);
      };
    } else {
      console.error("Iframe o URL no disponible");
    }
  }

  siguientePaso() {
    console.log("Siguiente paso...");
    if (
      this.tutorialActual &&
      this.pasoActual < this.tutorialActual.pasos.length - 1
    ) {
      this.pasoActual++;
      this.irAPaso(this.pasoActual);
    } else {
      this.completarDemo();
    }
  }

  anteriorPaso() {
    console.log("Anterior paso...");
    if (this.tutorialActual && this.pasoActual > 0) {
      this.pasoActual--;
      this.irAPaso(this.pasoActual);
    }
  }

  actualizarListaPasos() {
    if (!this.tutorialActual) return;

    const items = document.querySelectorAll("#listaPasos .paso-item");
    items.forEach((item, index) => {
      item.classList.remove("paso-activo", "paso-completado");

      if (index < this.pasoActual) {
        item.classList.add("paso-completado");
      } else if (index === this.pasoActual && this.tutorialIniciado) {
        item.classList.add("paso-activo");
      }
    });
  }

  completarDemo() {
    console.log("¡Tutorial completado!");
    this.mostrarMensaje(`🎉 ¡Tutorial "${this.tutorialActual.nombre}" completado!`, "success");

    if (
      confirm(
        "🎉 ¡Felicidades! Has completado el tutorial.\n\n¿Deseas hacer otro tutorial?"
      )
    ) {
      this.terminarTutorial();
      this.cargarSelectorTutoriales();
      this.tutorialActual = null;
      this.tutorialIniciado = false;
      document.getElementById("paginaActual").textContent = "Seleccionar Tutorial";
    } else {
      this.terminarTutorial();
    }
  }

  mostrarSelectorTutoriales() {
    this.cargarSelectorTutoriales();
    document.getElementById("paginaActual").textContent = "Seleccionar Tutorial";
  }

  mostrarIntroPaso(selector, texto) {
    const iframeDoc = this.iframe.contentDocument || this.iframe.contentWindow.document;
    const iframeWindow = this.iframe.contentWindow;

    if (!iframeWindow.introJs) {
      console.error("❌ Intro.js NO está cargado en el iframe");
      return;
    }

    const elemento = iframeDoc.querySelector(selector);

    if (!elemento) {
      console.warn("Elemento no encontrado:", selector);
      return;
    }

    this.bloquearNavegacionIframe();

    const intro = iframeWindow.introJs();

    intro.setOptions({
      steps: [
        {
          element: elemento,
          intro: texto,
          position: "auto",
        },
      ],
      showBullets: false,
      showProgress: true,
      nextLabel: "Siguiente",
      prevLabel: "Atrás",
      doneLabel: "Entendido",
      skipLabel: "✕",
      exitOnEsc: false,
      exitOnOverlayClick: false,
      tooltipPosition: "auto",
    });

    intro.onexit(() => {
      if (this.tutorialIniciado) {
        this.terminarTutorial();
      }
    });

    intro.oncomplete(() => this.siguientePaso());

    intro.start();
  }

  bloquearNavegacionIframe() {
    try {
      const iframeDoc = this.iframe.contentDocument || this.iframe.contentWindow.document;
      const iframeWindow = this.iframe.contentWindow;
      
      const enlaces = iframeDoc.querySelectorAll('a:not(.introjs-button)');
      enlaces.forEach(enlace => {
        if (!enlace.hasAttribute('data-tutorial-safe')) {
          enlace.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.bloqueador?.mostrarAdvertencia('Completa el paso actual primero');
            return false;
          });
        }
      });
      
      iframeWindow.addEventListener('keydown', (e) => {
        const teclasPermitidas = ['ArrowLeft', 'ArrowRight', 'Enter'];
        if (!teclasPermitidas.includes(e.key)) {
          e.preventDefault();
        }
      });
      
    } catch (error) {
      console.error('Error bloqueando navegación en iframe:', error);
    }
  }

  limpiarResaltado() {
    const arrow = document.getElementById("demoArrow");
    const spotlight = document.getElementById("demoSpotlight");

    if (arrow) arrow.style.display = "none";
    if (spotlight) spotlight.style.display = "none";

    try {
      const iframeDoc = this.iframe.contentDocument || this.iframe.contentWindow.document;
      iframeDoc.querySelectorAll(".demo-highlighted").forEach((el) => {
        el.classList.remove("demo-highlighted");
      });
    } catch (e) {}
  }

  ejecutarAccion(accion) {
    try {
      const iframeDoc = this.iframe.contentDocument || this.iframe.contentWindow.document;
      if (!iframeDoc) return;

      if (accion === "abrir_dropdown_citas") {
        this.esperarElemento("#citasDropdown", (dropdown) => {
          dropdown.click();
          console.log("Click en dropdown");

          this.esperarElemento(".dropdown-menu", () => {
            this.esperarElemento("#btn-nueva-cita", (link) => {
              console.log("LINK ENCONTRADO:", link);
              this.mostrarIntroPaso("#btn-nueva-cita", "Haz clic en Nueva Cita");
            });
          });
        });
      }
    } catch (error) {
      console.error("Error ejecutando acción:", error);
    }
  }

  esperarElementoVisible(selector, callback, intentos = 10) {
    const iframeDoc = this.iframe.contentDocument || this.iframe.contentWindow.document;
    const el = iframeDoc.querySelector(selector);

    if (el) {
      callback(el);
    } else if (intentos > 0) {
      setTimeout(() => {
        this.esperarElementoVisible(selector, callback, intentos - 1);
      }, 300);
    } else {
      console.warn("Elemento no visible:", selector);
    }
  }

  esperarElemento(selector, callback, intentos = 15) {
    const iframeDoc = this.iframe.contentDocument || this.iframe.contentWindow.document;
    const el = iframeDoc.querySelector(selector);

    if (el) {
      callback(el);
    } else if (intentos > 0) {
      setTimeout(() => {
        this.esperarElemento(selector, callback, intentos - 1);
      }, 300);
    } else {
      console.warn("Elemento nunca apareció:", selector);
    }
  }

  autoCargarTutorialDesdeURL() {
    const urlParams = new URLSearchParams(window.location.search);
    const tutorialId = urlParams.get('tutorial');
    
    if (tutorialId) {
      console.log("Auto-cargando tutorial desde URL:", tutorialId);
        this.tutorialCargado = true;
        this.seleccionarTutorial(tutorialId);
    }
  }

  cargarOtrosTutoriales() {
    const container = document.getElementById('otrosTutoriales');
    if (!container) return;
    
    const tutorialesList = this.getTutorialesList();
    const tutorialIdActual = this.tutorialActual ? this.tutorialActual.id : null;
    
    const otrosTutoriales = tutorialesList.filter(t => t.id !== tutorialIdActual);
    
    if (otrosTutoriales.length === 0) {
      container.innerHTML = '<div class="col-12 text-center py-3 text-muted">No hay más tutoriales disponibles</div>';
      return;
    }
    
    container.innerHTML = '';
    
    const colores = [
      { bg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' },
      { bg: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' },
      { bg: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' },
      { bg: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)' },
      { bg: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)' },
      { bg: 'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)' },
      { bg: 'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)' },
      { bg: 'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)' },
    ];
    
    otrosTutoriales.forEach((tutorial, index) => {
      const color = colores[index % colores.length];
      
      const col = document.createElement('div');
      col.className = 'col-md-4 col-sm-6 mb-3';
      col.innerHTML = `
        <div class="card h-100 tutorial-sugerencia" data-tutorial-id="${tutorial.id}" style="cursor: pointer; transition: transform 0.2s;">
          <div class="card-body" style="background: ${color.bg}; color: white; border-radius: 8px;">
            <div class="d-flex justify-content-between align-items-start">
              <h6 class="card-title mb-2" style="color: white; font-weight: bold;">${tutorial.nombre}</h6>
              <span class="badge bg-light text-dark">${tutorial.pasosCount} pasos</span>
            </div>
            <p class="card-text small" style="color: rgba(255,255,255,0.9);">${tutorial.descripcion}</p>
            <div class="mt-2">
              <small><i class="fas fa-play-circle"></i> Click para iniciar</small>
            </div>
          </div>
        </div>
      `;
      
      col.querySelector('.tutorial-sugerencia').addEventListener('click', () => {
        const newUrl = `${window.location.pathname}?tutorial=${tutorial.id}`;
        window.history.pushState({}, '', newUrl);
        this.seleccionarTutorial(tutorial.id);
      });
      
      container.appendChild(col);
    });
  }
}

// Inicializar cuando cargue la página
document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM cargado, inicializando tutoriales...");

  if (window.tutorialInteractivoInstance) {
    console.warn("Ya existe una instancia de tutorial interactivo");
    return;
  }

  try {
    window.tutorialInteractivoInstance = new TutorialInteractivo(window.DEMO_CONFIG || {});
    console.log("Instancia de tutorial creada:", window.tutorialInteractivoInstance);
    
    const urlParams = new URLSearchParams(window.location.search);
    const tutorialId = urlParams.get('tutorial');
    if (tutorialId && !window.tutorialInteractivoInstance.tutorialActual) {
      console.log("FORZANDO carga de tutorial desde URL:", tutorialId);
      window.tutorialInteractivoInstance.seleccionarTutorial(tutorialId);
    }
    
  } catch (error) {
    console.error("Error creando instancia de tutorial:", error);
  }
});