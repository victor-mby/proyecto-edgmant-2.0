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
