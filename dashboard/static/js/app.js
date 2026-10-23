document.addEventListener('DOMContentLoaded', () => {
    const boton = document.getElementById('btn-inferir');
    if (boton) boton.addEventListener('click', ejecutarInferencia);
    cargarDashboard();
});

async function cargarDashboard() {
    try {
        const resp = await fetch('/api/dashboard');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const datos = await resp.json();
        const estadisticas = datos.estadisticas || {};

        document.getElementById('total-registros').textContent = estadisticas.total_registros ?? 0;
        document.getElementById('total-anomalias').textContent = estadisticas.total_detecciones ?? 0;
        document.getElementById('total-motores').textContent = (datos.motores || []).length;
        document.getElementById('umbral').textContent =
            Number.isFinite(estadisticas.umbral) ? estadisticas.umbral.toFixed(6) : '-';

        const tbody = document.querySelector('#tabla-anomalias tbody');
        tbody.replaceChildren();
        const historial = datos.historial || [];
        actualizarApoyoOperador(datos.apoyo_operador || null);
        historial.forEach((deteccion) => {
            const tr = document.createElement('tr');
            const valores = [
                deteccion.fecha || '-',
                deteccion.hora || '-',
                deteccion.motor_id || '-',
            ];
            valores.forEach((valor) => {
                const td = document.createElement('td');
                td.textContent = String(valor);
                tr.appendChild(td);
            });

            const tdSeveridad = document.createElement('td');
            const etiqueta = document.createElement('span');
            etiqueta.className = `severidad ${String(deteccion.severidad || '').replace(/[^a-zA-Z_-]/g, '')}`;
            etiqueta.textContent = deteccion.severidad || '-';
            tdSeveridad.appendChild(etiqueta);
            tr.appendChild(tdSeveridad);

            const tdError = document.createElement('td');
            const error = Number(deteccion.error_reconstruccion);
            tdError.textContent = Number.isFinite(error) ? error.toFixed(4) : '-';
            tr.appendChild(tdError);

            const tdInterpretacion = document.createElement('td');
            tdInterpretacion.textContent = deteccion.tipo_interpretacion || '-';
            tr.appendChild(tdInterpretacion);
            tbody.appendChild(tr);
        });

        const contenedorMotores = document.getElementById('lista-motores');
        contenedorMotores.replaceChildren();
        (datos.motores || []).forEach((motor) => {
            const tarjeta = document.createElement('div');
            tarjeta.className = 'motor-card';
            const titulo = document.createElement('h3');
            titulo.textContent = String(motor);
            const detalle = document.createElement('p');
            detalle.textContent = 'Motor registrado en la base de datos.';
            tarjeta.append(titulo, detalle);
            contenedorMotores.appendChild(tarjeta);
        });
        dibujarGrafico(historial);
    } catch (error) {
        console.error('Error cargando dashboard:', error);
        const estado = document.getElementById('estado-inferencia');
        if (estado) estado.textContent = 'No se pudo cargar el dashboard. Revisa la base de datos y el servidor.';
    }
}

function actualizarApoyoOperador(apoyo) {
    const estado = document.getElementById('apoyo-estado');
    const contenedor = document.getElementById('apoyo-contenido');
    if (!estado || !contenedor) return;

    contenedor.replaceChildren();
    if (!apoyo) {
        estado.className = 'apoyo-operador__estado';
        estado.textContent = 'SIN DATOS';
        const mensaje = document.createElement('p');
        mensaje.className = 'apoyo-operador__vacio';
        mensaje.textContent = 'No se pudo obtener el plan de apoyo. Recarga el dashboard para volver a consultar los resultados.';
        contenedor.appendChild(mensaje);
        return;
    }

    const modo = String(apoyo.estado || 'VIGILANCIA').toUpperCase();
    estado.className = 'apoyo-operador__estado';
    if (modo === 'VALIDAR_MODELO') {
        estado.classList.add('apoyo-operador__estado--validar');
        estado.textContent = 'VALIDAR MODELO';
    } else if (modo === 'REVISION_TECNICA') {
        const severidad = String(apoyo.deteccion?.severidad_modelo || '').toUpperCase();
        estado.classList.add(severidad === 'CRITICO'
            ? 'apoyo-operador__estado--critico'
            : 'apoyo-operador__estado--atencion');
        estado.textContent = severidad === 'CRITICO' ? 'REVISIÓN PRIORITARIA' : 'REVISAR';
    } else {
        estado.textContent = 'VIGILANCIA';
    }

    const titulo = document.createElement('h3');
    titulo.className = 'apoyo-operador__titulo';
    titulo.textContent = apoyo.titulo || 'Apoyo operativo';

    const resumen = document.createElement('p');
    resumen.className = 'apoyo-operador__resumen';
    resumen.textContent = apoyo.resumen || '';

    contenedor.append(titulo, resumen);

    if (apoyo.advertencia) {
        const advertencia = document.createElement('div');
        advertencia.className = modo === 'VALIDAR_MODELO'
            ? 'apoyo-operador__alerta apoyo-operador__alerta--modelo'
            : 'apoyo-operador__alerta';
        const subtitulo = document.createElement('strong');
        subtitulo.textContent = modo === 'VALIDAR_MODELO'
            ? 'Control de calidad del modelo'
            : 'Precaución';
        const texto = document.createElement('p');
        texto.textContent = apoyo.advertencia;
        advertencia.append(subtitulo, texto);
        contenedor.appendChild(advertencia);
    }

    const deteccion = apoyo.deteccion;
    if (deteccion) {
        const metadatos = document.createElement('p');
        metadatos.className = 'apoyo-operador__metadatos';
        const datosMeta = [
            'Motor: ' + (deteccion.motor_id || 'No identificado'),
            'Fecha: ' + (deteccion.fecha || 'No disponible'),
            'Hora: ' + (deteccion.hora || 'No disponible'),
            'Severidad del modelo: ' + (deteccion.severidad_modelo || 'No clasificada'),
        ];
        if (Number.isFinite(deteccion.error_reconstruccion)) {
            datosMeta.push('Error: ' + deteccion.error_reconstruccion.toFixed(4));
        }
        if (Number.isFinite(deteccion.umbral)) {
            datosMeta.push('Umbral: ' + deteccion.umbral.toFixed(6));
        }
        metadatos.textContent = datosMeta.join(' · ');
        contenedor.appendChild(metadatos);
    }

    const accionesTitulo = document.createElement('strong');
    accionesTitulo.className = 'apoyo-operador__seccion-titulo';
    accionesTitulo.textContent = modo === 'VALIDAR_MODELO'
        ? 'Comprobaciones previas a interpretar la alerta'
        : 'Pasos sugeridos para el operador';

    const listaAcciones = document.createElement('ol');
    listaAcciones.className = 'apoyo-operador__acciones';
    (Array.isArray(apoyo.acciones) ? apoyo.acciones : []).forEach((accion) => {
        const item = document.createElement('li');
        item.textContent = String(accion);
        listaAcciones.appendChild(item);
    });
    contenedor.append(accionesTitulo, listaAcciones);

    const variables = Array.isArray(apoyo.variables) ? apoyo.variables : [];
    if (variables.length) {
        const variablesTitulo = document.createElement('strong');
        variablesTitulo.className = 'apoyo-operador__seccion-titulo';
        variablesTitulo.textContent = 'Variables señaladas por la interpretación';
        const etiquetas = document.createElement('div');
        etiquetas.className = 'apoyo-operador__variables';
        const nombres = {
            nivel: 'Nivel', nivel_porcentaje: 'Nivel (%)',
            voltaje: 'Tensión de red', voltaje_terminal: 'Tensión terminal',
            amperaje: 'Amperaje', corriente_total: 'Corriente total',
            caudal: 'Caudal', potencia: 'Potencia', carga: 'Carga',
            altura: 'Altura', factor_potencia: 'Factor de potencia',
            caudal_total: 'Caudal total', potencia_total: 'Potencia total',
            nivel_destino: 'Nivel destino', demanda: 'Demanda',
            posicion_valvula: 'Posición de válvula',
            velocidad_rotacion: 'Velocidad de rotación',
            horas_operacion: 'Horas de operación'
        };
        variables.forEach((variable) => {
            const etiquetaVariable = document.createElement('span');
            etiquetaVariable.className = 'apoyo-operador__variable';
            etiquetaVariable.textContent = nombres[variable] || String(variable);
            etiquetas.appendChild(etiquetaVariable);
        });
        contenedor.append(variablesTitulo, etiquetas);
    }

    if (Number.isFinite(apoyo.porcentaje_anomalias)) {
        const tasa = document.createElement('p');
        tasa.className = 'apoyo-operador__metadatos';
        tasa.textContent = 'Registros clasificados como posibles anomalías: '
            + apoyo.porcentaje_anomalias.toFixed(2) + '% del total almacenado.';
        contenedor.appendChild(tasa);
    }
}

function dibujarGrafico(historial) {
    const canvas = document.getElementById('grafico-error');
    if (!canvas) return;
    const contexto = canvas.getContext('2d');
    if (!contexto) return;

    const ancho = Math.max(canvas.clientWidth, 320);
    const alto = 220;
    const escalaDpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(ancho * escalaDpr);
    canvas.height = Math.floor(alto * escalaDpr);
    canvas.style.height = `${alto}px`;
    contexto.setTransform(escalaDpr, 0, 0, escalaDpr, 0, 0);
    contexto.clearRect(0, 0, ancho, alto);

    const puntos = historial
        .map((fila) => ({
            error: Number(fila.error_reconstruccion),
            umbral: Number(fila.umbral),
        }))
        .filter((fila) => Number.isFinite(fila.error) && Number.isFinite(fila.umbral));
    if (!puntos.length) {
        contexto.fillText('Aún no hay detecciones para graficar.', 12, 24);
        return;
    }

    const margen = { izquierda: 42, derecha: 12, arriba: 12, abajo: 28 };
    const anchoUtil = ancho - margen.izquierda - margen.derecha;
    const altoUtil = alto - margen.arriba - margen.abajo;
    const maximo = Math.max(...puntos.flatMap((p) => [p.error, p.umbral]), 0.000001) * 1.1;
    const x = (i) => margen.izquierda + (puntos.length === 1 ? anchoUtil / 2 : i * anchoUtil / (puntos.length - 1));
    const y = (valor) => margen.arriba + altoUtil - (valor / maximo) * altoUtil;

    contexto.beginPath();
    contexto.moveTo(margen.izquierda, margen.arriba);
    contexto.lineTo(margen.izquierda, margen.arriba + altoUtil);
    contexto.lineTo(ancho - margen.derecha, margen.arriba + altoUtil);
    contexto.stroke();

    contexto.beginPath();
    puntos.forEach((p, i) => {
        if (i === 0) contexto.moveTo(x(i), y(p.error));
        else contexto.lineTo(x(i), y(p.error));
    });
    contexto.stroke();

    contexto.setLineDash([5, 4]);
    const umbralMedio = puntos.reduce((suma, p) => suma + p.umbral, 0) / puntos.length;
    contexto.beginPath();
    contexto.moveTo(margen.izquierda, y(umbralMedio));
    contexto.lineTo(ancho - margen.derecha, y(umbralMedio));
    contexto.stroke();
    contexto.setLineDash([]);

    contexto.fillText('Error de reconstrucción', margen.izquierda, alto - 8);
    contexto.fillText('Umbral medio', ancho - 112, alto - 8);
}

async function ejecutarInferencia() {
    const estado = document.getElementById('estado-inferencia');
    const boton = document.getElementById('btn-inferir');
    estado.textContent = 'Ejecutando inferencia...';
    if (boton) boton.disabled = true;

    try {
        const resp = await fetch('/api/inferir', { method: 'POST' });
        const datos = await resp.json();
        if (!resp.ok || datos.ok === false) {
            throw new Error(datos.error || `HTTP ${resp.status}`);
        }
        estado.textContent = `Inferencia completada. Nuevas detecciones guardadas: ${datos.detecciones_guardadas}`;
        await cargarDashboard();
    } catch (error) {
        estado.textContent = `Error en la inferencia: ${error.message}`;
        console.error('Error ejecutando inferencia:', error);
    } finally {
        if (boton) boton.disabled = false;
    }
}
