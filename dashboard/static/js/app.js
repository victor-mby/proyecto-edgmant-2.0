document.addEventListener('DOMContentLoaded', () => {
    const diagnostico = document.getElementById('diagnostico-texto');
    const estadoTitulo = document.getElementById('estado-titulo');
    const prioridad = document.getElementById('estado-prioridad');
    const conexion = document.getElementById('conexion-estado');
    const hora = document.getElementById('hora-analisis');
    const conversacion = document.getElementById('conversacion');
    const formulario = document.getElementById('form-pregunta');
    const entrada = document.getElementById('pregunta-operador');
    let ultimoDiagnostico = '';
    let apoyoActual = null;
    let actualizando = false;

    const preguntas = {
        '¿Cuál es la posible causa?': 'causa',
        '¿Qué debo revisar primero?': 'revisar',
        '¿Cómo confirmo que se solucionó?': 'recuperacion'
    };

    function escribirTexto(elemento, texto, velocidad = 13) {
        return new Promise((resolve) => {
            elemento.textContent = '';
            let indice = 0;
            const cursor = document.createElement('span');
            cursor.className = 'cursor-escritura';
            cursor.setAttribute('aria-hidden', 'true');
            elemento.appendChild(cursor);
            const intervalo = window.setInterval(() => {
                if (indice >= texto.length) {
                    window.clearInterval(intervalo);
                    cursor.remove();
                    resolve();
                    return;
                }
                cursor.insertAdjacentText('beforebegin', texto.slice(indice, indice + 2));
                indice += 2;
            }, velocidad);
        });
    }

    function textoDiagnostico(apoyo) {
        if (!apoyo) return {
            titulo: 'Estado no disponible',
            prioridad: 'SIN DATOS',
            texto: 'No pude consultar el estado actual. Comprueba que el dashboard y el receptor de telemetría estén funcionando.'
        };
        const estado = String(apoyo.estado || 'VIGILANCIA').toUpperCase();
        if (estado === 'VALIDAR_MODELO') {
            return {
                titulo: 'Diagnóstico pendiente de validación',
                prioridad: 'VALIDAR MODELO',
                texto: (apoyo.resumen || 'Los resultados del modelo necesitan validación.')
                    + '\n\n' + (apoyo.advertencia || 'No se puede confirmar una avería con la clasificación actual.')
                    + '\n\nPrimero hay que validar la calidad de la evaluación. No atribuiré una falla física mientras los resultados no sean confiables.'
            };
        }
        if (estado === 'VIGILANCIA') {
            return {
                titulo: 'Estación en vigilancia',
                prioridad: 'VIGILANCIA',
                texto: 'No hay una detección vigente disponible para establecer una causa específica. Continúo pendiente de nuevos datos operativos. Si observas una condición anormal, verifica la alarma correspondiente y el procedimiento de la estación.'
            };
        }
        const deteccion = apoyo.deteccion || {};
        const acciones = Array.isArray(apoyo.acciones) ? apoyo.acciones : [];
        const causa = deteccion.tipo_interpretacion || apoyo.titulo || 'Comportamiento fuera del patrón esperado';
        const pasos = acciones.slice(0, 2).map((a, i) => (i + 1) + '. ' + a).join('\n');
        return {
            titulo: causa,
            prioridad: String(deteccion.severidad_modelo || 'REVISAR').toUpperCase(),
            texto: 'He detectado un comportamiento que requiere revisión en ' + (deteccion.motor_id || 'un motor de la estación') + '.\n\nPosible causa: ' + causa + '.\n\nQué revisar primero:\n' + (pasos || 'Contrasta el estado actual con las señales operativas y el procedimiento técnico de la estación.') + '\n\nEsta es una causa posible, no una avería confirmada. Verifica las condiciones antes de intervenir.'
        };
    }

    async function cargarEstado(forzar = false) {
        if (actualizando) return;
        actualizando = true;
        try {
            const respuesta = await fetch('/api/dashboard', { cache: 'no-store' });
            if (!respuesta.ok) throw new Error('HTTP ' + respuesta.status);
            const datos = await respuesta.json();
            if (datos.ok === false) throw new Error(datos.error || 'No se pudo consultar el estado');
            apoyoActual = datos.apoyo_operador || null;
            conexion.innerHTML = '<span class="punto"></span> Conectado';
            conexion.classList.add('conectado');
            const diagnosticoActual = textoDiagnostico(apoyoActual);
            const clave = JSON.stringify(diagnosticoActual);
            if (forzar || clave !== ultimoDiagnostico) {
                ultimoDiagnostico = clave;
                estadoTitulo.textContent = '';
                await escribirTexto(estadoTitulo, diagnosticoActual.titulo, 20);
                prioridad.textContent = diagnosticoActual.prioridad;
                prioridad.className = 'prioridad ' + clasePrioridad(diagnosticoActual.prioridad);
                hora.textContent = new Date().toLocaleTimeString('es-PE', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
                await escribirTexto(diagnostico, diagnosticoActual.texto, 9);
                actualizarPreguntas(diagnosticoActual.prioridad);
            }
        } catch (error) {
            conexion.innerHTML = '<span class="punto"></span> Sin conexión';
            conexion.classList.remove('conectado');
            if (!ultimoDiagnostico) {
                estadoTitulo.textContent = 'No se pudo consultar el estado';
                diagnostico.textContent = 'Comprueba que el dashboard y el receptor estén activos. No puedo emitir un diagnóstico sin consultar los datos actuales.';
            }
            console.error('Error consultando estado de EdgeMant:', error);
        } finally {
            actualizando = false;
        }
    }

    function clasePrioridad(texto) {
        const valor = String(texto).toUpperCase();
        if (valor.includes('CRITICO') || valor.includes('CRÍTICO') || valor.includes('PRIORITARIA')) return 'prioridad-critica';
        if (valor.includes('VALIDAR') || valor.includes('ATENCION') || valor.includes('ATENCIÓN') || valor.includes('REVISAR')) return 'prioridad-atencion';
        return 'prioridad-normal';
    }

    function actualizarPreguntas(prioridadActual) {
        const contenedor = document.getElementById('preguntas-rapidas');
        const textos = prioridadActual === 'VALIDAR MODELO'
            ? ['¿Por qué no se puede confirmar la falla?', '¿Qué se debe validar primero?', '¿Cómo verifico el resultado?']
            : ['¿Cuál es la posible causa?', '¿Qué debo revisar primero?', '¿Cómo confirmo que se solucionó?'];
        contenedor.replaceChildren();
        textos.forEach((texto) => {
            const boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'pregunta-btn';
            boton.textContent = texto;
            boton.addEventListener('click', () => responderPregunta(texto));
            contenedor.appendChild(boton);
        });
    }

    function agregarMensaje(clase, autor, texto, animar = false) {
        const mensaje = document.createElement('div');
        mensaje.className = 'mensaje ' + clase;
        const avatar = document.createElement('div');
        avatar.className = 'avatar-edgemant';
        avatar.textContent = clase === 'mensaje-edgemant' ? 'E' : 'O';
        const cuerpo = document.createElement('div');
        cuerpo.className = 'mensaje-cuerpo';
        const cabecera = document.createElement('div');
        cabecera.className = 'mensaje-autor';
        cabecera.textContent = autor;
        const parrafo = document.createElement('p');
        cuerpo.append(cabecera, parrafo);
        mensaje.append(avatar, cuerpo);
        conversacion.appendChild(mensaje);
        if (animar) escribirTexto(parrafo, texto, 10);
        else parrafo.textContent = texto;
        mensaje.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }

    function responderPregunta(pregunta) {
        const texto = String(pregunta || '').trim();
        if (!texto) return;
        agregarMensaje('mensaje-operador', 'Operador', texto);
        const apoyo = apoyoActual || {};
        const acciones = Array.isArray(apoyo.acciones) ? apoyo.acciones : [];
        const clave = preguntas[texto] || (texto.toLowerCase().includes('causa') ? 'causa'
            : texto.toLowerCase().includes('revis') || texto.toLowerCase().includes('validar') ? 'revisar'
            : texto.toLowerCase().includes('solucion') || texto.toLowerCase().includes('recuper') ? 'recuperacion' : 'general');
        let respuesta;
        if (apoyo.estado === 'VALIDAR_MODELO') {
            respuesta = clave === 'revisar'
                ? 'Lo primero es validar que las variables, unidades, escalador y versión del modelo coincidan. La tasa actual de alertas no permite atribuir una avería física con confianza.'
                : 'No puedo confirmar una causa física todavía: la evaluación del modelo requiere validación. ' + (apoyo.advertencia || 'Contrasta las lecturas con las señales operativas y los procedimientos de la estación.');
        } else if (clave === 'causa') {
            respuesta = apoyo.deteccion?.tipo_interpretacion
                ? 'La posible causa indicada por la interpretación actual es: ' + apoyo.deteccion.tipo_interpretacion + '. Es una hipótesis que debe contrastarse con las señales de la estación.'
                : 'Aún no hay evidencia suficiente para proponer una causa específica. Necesito una detección válida o una condición operativa confirmada.';
        } else if (clave === 'revisar') {
            respuesta = acciones.slice(0, 2).join(' ') || 'Comprueba el estado de la estación, la alarma operativa relacionada y el procedimiento de seguridad antes de intervenir.';
        } else if (clave === 'recuperacion') {
            respuesta = 'Compara las nuevas lecturas con el rango operativo normal, confirma que la alarma haya desaparecido y verifica que la condición se mantenga estable durante varias capturas. Sigue el procedimiento de la estación.';
        } else {
            respuesta = 'Puedo orientar sobre la posible causa, las primeras comprobaciones y cómo verificar la recuperación. Para un diagnóstico más específico se necesita integrar un modelo de lenguaje con acceso a la telemetría y los manuales técnicos.';
        }
        agregarMensaje('mensaje-edgemant', 'EdgeMant', respuesta, true);
    }

    document.querySelectorAll('.pregunta-btn').forEach((boton) => {
        boton.addEventListener('click', () => responderPregunta(boton.textContent));
    });
    formulario.addEventListener('submit', (evento) => {
        evento.preventDefault();
        const pregunta = entrada.value.trim();
        if (!pregunta) return;
        entrada.value = '';
        responderPregunta(pregunta);
    });

    cargarEstado(true);
    window.setInterval(() => cargarEstado(false), 5000);
});
