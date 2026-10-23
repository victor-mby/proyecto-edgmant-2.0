/**
 * Transporte de telemetría capturada hacia EdgeMant.
 * Este módulo solo envía muestras; no calcula ni clasifica anomalías.
 */
const ENDPOINT_PREDETERMINADO = 'http://127.0.0.1:8765/api/telemetria';
const TAMANO_LOTE = 100;
const MAX_REGISTROS_EN_COLA = 20000;

export function conectarIngesta(sim, opciones = {}) {
  const endpoint = opciones.endpoint || ENDPOINT_PREDETERMINADO;
  const fetchFn = opciones.fetch || (typeof fetch === 'function' ? fetch.bind(globalThis) : null);

  if (!fetchFn || !sim || !sim.bus || typeof sim.bus.on !== 'function') {
    console.warn('[EdgeMant] No se pudo iniciar el transporte de telemetría.');
    return () => {};
  }

  const pendientes = [];
  let temporizador = null;
  let enviando = false;
  let detenido = false;

  function programar(ms, reemplazar = false) {
    if (detenido) return;
    if (temporizador !== null && !reemplazar) return;
    if (temporizador !== null) clearTimeout(temporizador);
    temporizador = setTimeout(() => {
      temporizador = null;
      void enviarPendientes();
    }, ms);
  }

  function alCapturar(registros) {
    if (detenido || !Array.isArray(registros) || registros.length === 0) return;

    pendientes.push(...registros);
    if (pendientes.length > MAX_REGISTROS_EN_COLA) {
      const perdidos = pendientes.length - MAX_REGISTROS_EN_COLA;
      pendientes.splice(0, perdidos);
      console.error(
        '[EdgeMant] La cola local alcanzó su límite; se descartaron ' +
        perdidos + ' muestras antiguas porque el receptor no está disponible.',
      );
    }

    if (pendientes.length >= TAMANO_LOTE) programar(50, true);
    else programar(1200);
  }

  async function enviarPendientes() {
    if (detenido || enviando || pendientes.length === 0) return;
    enviando = true;
    let fallo = false;

    try {
      while (!detenido && pendientes.length > 0) {
        const lote = pendientes.slice(0, TAMANO_LOTE);
        const respuesta = await fetchFn(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ registros: lote }),
        });

        if (!respuesta.ok) {
          throw new Error('El receptor respondió HTTP ' + respuesta.status);
        }

        pendientes.splice(0, lote.length);
      }
    } catch (error) {
      fallo = true;
      console.warn(
        '[EdgeMant] No se pudo enviar la telemetría; se conservará en cola y se reintentará.',
        error,
      );
    } finally {
      enviando = false;
      if (!detenido && pendientes.length > 0) {
        programar(fallo ? 2000 : 250, true);
      }
    }
  }

  const desuscribir = sim.bus.on('captura', alCapturar);

  return () => {
    detenido = true;
    desuscribir();
    if (temporizador !== null) clearTimeout(temporizador);
    temporizador = null;
  };
}
