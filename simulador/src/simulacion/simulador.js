import { crearBus } from '../nucleo/almacen.js';
import { crearConfiguracion, fusionar, clonar } from './configuracion.js';
import { crearEstacion } from './estacion.js';
import { crearGestorAlarmas } from './almagas.js';
import { crearRegistroEventos } from './eventos.js';
import { crearHistorial, construirCSV, descargarCSV } from './historial.js';
import { selloTemporal, horaSegundos } from '../nucleo/formato.js';

export function crearSimulador(configInicial) {
  const bus = crearBus();
  let cfg = crearConfiguracion(configInicial);
  const eventos = crearRegistroEventos(600);
  const historial = crearHistorial(cfg.simulacion.historialMaximo);
  let estacion = crearEstacion(cfg, eventos);
  let alarmas = crearGestorAlarmas(cfg, registrarAlarma);
  const reloj = {
    corriendo: false,
    velocidad: cfg.simulacion.velocidad,
    acumulado: 0,
    paso: cfg.simulacion.paso,
    ultimoReal: performance.now(),
    tiempoReal: Date.now(),
    muestras: 0,
    pasos: 0,
  };

  function registrarAlarma(evento) {
    const registro = eventos.agregar({
      tiempo: estacion.estado.tiempo,
      tipo: 'ALARMA',
      equipo: evento.equipo,
      severidad: evento.severidad,
      texto: evento.texto,
    });
    bus.emit('alarma', registro);
  }

  function registrarSistema(texto, extra) {
    const registro = eventos.agregar({
      tiempo: estacion.estado.tiempo,
      tipo: 'SISTEMA',
      equipo: 'ESTACIÓN',
      texto,
      ...extra,
    });
    bus.emit('evento', registro);
    return registro;
  }

  function contextoAlarmas(dt) {
    return {
      dt,
      tiempo: estacion.estado.tiempo,
      cfg,
      red: estacion.estado.red,
      tanque: estacion.estado.tanque,
      destino: estacion.estado.destino,
      comunicacion: estacion.estado.comunicacion,
      porMotor: estacion.porMotor(),
      cualquieraEnMarcha: estacion.estado.motores.some((m) => m.velocidad > 0.05),
    };
  }

  function capturar(dt) {
    const estado = estacion.estado;
    const fecha = estacion.fechaSimulacion();
    const registrosCapturados = [];
    for (const motor of estado.motores) {
      const registro = {
        tiempo: estado.tiempo,
        tiempo_simulacion: `${String(Math.floor(estado.tiempo / 3600)).padStart(2, '0')}:${String(
          Math.floor((estado.tiempo % 3600) / 60),
        ).padStart(2, '0')}:${String(Math.floor(estado.tiempo % 60)).padStart(2, '0')}`,
        timestamp: fecha.getTime(),
        fecha: fecha.toLocaleDateString('es-ES'),
        hora: horaSegundos(fecha),
        motor_id: motor.id,
        nivel: estado.tanque.nivel,
        nivel_porcentaje: (estado.tanque.nivel / estado.tanque.altura) * 100,
        voltaje: estado.red.tension,
        voltaje_terminal: motor.tensionTerminal,
        amperaje: motor.corriente,
        corriente_nominal: motor.placa.corrienteNominal,
        caudal: motor.caudal * 1000,
        potencia: motor.potencia,
        potencia_nominal: motor.placa.potenciaKw,
        carga: motor.carga * 100,
        altura: motor.altura,
        factor_potencia: motor.factorPotencia,
        estado_motor: motor.estado,
        estado_valvula: motor.valvula.estado,
        posicion_valvula: motor.valvula.posicion * 100,
        velocidad_rotacion: motor.velocidad * 100,
        horas_operacion: motor.tiempoOperacion / 3600,
        caudal_total: estado.totales.caudal * 1000,
        potencia_total: estado.totales.potencia,
        corriente_total: estado.red.corriente,
        nivel_destino: estado.destino.nivel,
        demanda: estado.destino.demanda,
        nivel_tanque_maximo: estado.tanque.altura,
      };
      historial.agregar(registro);
      registrosCapturados.push(registro);
    }
    reloj.muestras += 1;
    bus.emit('captura', registrosCapturados);
    bus.emit('muestra', { dt, total: historial.total() });
  }

  function avanzarSim(dt) {
    estacion.avanzar(dt);
    const cambios = alarmas.evaluar(contextoAlarmas(dt));
    if (cambios.length > 0) bus.emit('alarmas', cambios);
    if (historial.intervalo(dt, cfg.simulacion.intervaloMuestra)) capturar(dt);
  }

  function avanzarReloj(deltaMs) {
    const ahora = performance.now();
    const delta = Number.isFinite(deltaMs)
      ? Math.min(500, Math.max(0, deltaMs))
      : Math.min(250, ahora - reloj.ultimoReal);
    reloj.ultimoReal = ahora;
    reloj.tiempoReal = Date.now();
    if (!reloj.corriendo) return 0;
    reloj.acumulado += (delta / 1000) * reloj.velocidad;
    const maximo = 40;
    let pasos = 0;
    while (reloj.acumulado >= reloj.paso && pasos < maximo) {
      avanzarSim(reloj.paso);
      reloj.acumulado -= reloj.paso;
      pasos += 1;
    }
    if (pasos >= maximo) reloj.acumulado = 0;
    reloj.pasos += pasos;
    return pasos;
  }

  function iniciar() {
    if (reloj.corriendo) return;
    reloj.corriendo = true;
    reloj.ultimoReal = performance.now();
    registrarSistema('Simulación iniciada. Adquisición de datos activa.');
    bus.emit('reloj', reloj);
  }

  function pausar() {
    if (!reloj.corriendo) return;
    reloj.corriendo = false;
    registrarSistema('Simulación en pausa. Variables congeladas, historial conservado.');
    bus.emit('reloj', reloj);
  }

  function alternar() {
    if (reloj.corriendo) pausar();
    else iniciar();
    return reloj.corriendo;
  }

  function establecerVelocidad(valor) {
    reloj.velocidad = Math.min(60, Math.max(0.5, Number(valor) || 1));
    registrarSistema(`Factor de tiempo de simulación fijado en x${reloj.velocidad}.`);
    bus.emit('reloj', reloj);
    return reloj.velocidad;
  }

  function reiniciar() {
    reloj.corriendo = false;
    reloj.acumulado = 0;
    reloj.muestras = 0;
    reloj.pasos = 0;
    const copia = clonar(cfg);
    cfg = crearConfiguracion(copia);
    reloj.paso = cfg.simulacion.paso;
    reloj.velocidad = cfg.simulacion.velocidad;
    eventos.limpiar();
    historial.limpiar();
    estacion = crearEstacion(cfg, eventos);
    alarmas = crearGestorAlarmas(cfg, registrarAlarma);
    registrarSistema('Simulación reiniciada. Estado de estación restablecido a valores iniciales.');
    bus.emit('reinicio');
    bus.emit('reloj', reloj);
  }

  function aplicarConfig(cambios) {
    cfg = crearConfiguracion(fusionar(clonar(cfg), cambios));
    reloj.paso = cfg.simulacion.paso;
    historial.fijarLimite(cfg.simulacion.historialMaximo);
    estacion.reconfigurar(cfg);
    alarmas = crearGestorAlarmas(cfg, registrarAlarma);
    registrarSistema('Parámetros de configuración actualizados desde el panel de configuración.');
    bus.emit('config', cfg);
    return cfg;
  }

  function agregarMotor(definicion) {
    const existentes = cfg.motores.map((m) => m.id);
    let indice = 1;
    let id = definicion.id && !existentes.includes(definicion.id) ? definicion.id : `M-${String(cfg.motores.length + 1).padStart(2, '0')}`;
    while (existentes.includes(id)) {
      indice += 1;
      id = `M-${String(cfg.motores.length + indice).padStart(2, '0')}`;
    }
    const nuevo = {
      ...definicion,
      id,
      descripcion: definicion.descripcion || `Equipo de impulsión ${cfg.motores.length + 1}`,
      estadoInicial: 'PARADO',
      cargaInicial: 0,
      horasIniciales: 0,
      valvula: definicion.valvula || {},
    };
    return aplicarConfig({ motores: [...cfg.motores, nuevo] });
  }

  function quitarMotor(id) {
    if (cfg.motores.length <= 1) return { ok: false, mensaje: 'Debe existir al menos un equipo en la estación.' };
    const restantes = cfg.motores.filter((m) => m.id !== id);
    if (restantes.length === cfg.motores.length) {
      return { ok: false, mensaje: `Equipo ${id} no encontrado.` };
    }
    const motor = estacion.estado.motores.find((m) => m.id === id);
    if (motor && motor.estado !== 'PARADO') {
      return { ok: false, mensaje: `No se puede retirar ${id}: equipo en estado ${motor.estado}.` };
    }
    aplicarConfig({ motores: restantes });
    return { ok: true, mensaje: `Equipo ${id} retirado de la estación.` };
  }

  function exportar(opciones) {
    const cfgExport = opciones || {};
    let registros = historial.listar(cfgExport.limite);
    if (cfgExport.motor) registros = registros.filter((r) => r.motor_id === cfgExport.motor);
    if (!registros.length) return { ok: false, mensaje: 'No hay registros para exportar.' };
    const csv = construirCSV(registros);
    const nombre = `${cfg.estacion.id}_historial`;
    const archivo = descargarCSV(nombre, csv);
    registrarSistema(`Exportación de historial: ${registros.length} registros (${archivo}).`);
    return { ok: true, mensaje: `${registros.length} registros exportados a ${archivo}`, archivo };
  }

  function exportarEventosCSV() {
    const lista = eventos.listar();
    if (!lista.length) return { ok: false, mensaje: 'No hay eventos para exportar.' };
    const filas = lista
      .map((e) => [e.hora.toLocaleString('es-ES'), e.tipo, e.equipo, e.severidad, e.texto].join(';'))
      .join('\r\n');
    const csv = `Hora;Tipo;Equipo;Severidad;Descripción\r\n${filas}`;
    const archivo = descargarCSV(`${cfg.estacion.id}_eventos`, csv);
    return { ok: true, mensaje: `${lista.length} eventos exportados`, archivo };
  }

  function resumen() {
    const estado = estacion.estado;
    return {
      id: cfg.estacion.id,
      nombre: cfg.estacion.nombre,
      tiempo: estado.tiempo,
      reloj,
      estado,
      cfg,
      alarmas: alarmas.listar(),
      conteoAlarmas: alarmas.contar(),
      totalEventos: eventos.total(),
      totalMuestras: historial.total(),
      capacidadHistorial: historial.capacidad(),
      online: estado.comunicacion.online,
    };
  }

  return {
    bus,
    estado: () => estacion.estado,
    config: () => cfg,
    eventos,
    historial,
    alarmas: () => alarmas,
    reloj,
    avanzarReloj,
    iniciar,
    pausar,
    alternar,
    reiniciar,
    establecerVelocidad,
    aplicarConfig,
    agregarMotor,
    quitarMotor,
    exportar,
    exportarEventosCSV,
    confirmarAlarmas: () => {
      alarmas.acknowledgeTodas();
      registrarSistema('Alarmas confirmadas por el operador.');
      bus.emit('alarmas', []);
    },
    confirmarAlarma: (id) => {
      alarmas.acknowledge(id);
      bus.emit('alarmas', []);
    },
    reiniciarAlarmas: () => {
      alarmas.reiniciar();
      registrarSistema('Registro de alarmas reiniciado.');
      bus.emit('alarmas', []);
    },
    limpiarHistorial: () => {
      historial.limpiar();
      registrarSistema('Historial de telemedicine borrado por el operador.');
      bus.emit('muestra', { total: 0 });
    },
    estartrar: (id) => wrap(estacion.estartrar(id)),
    parar: (id) => wrap(estacion.parar(id)),
    abrirValvula: (id) => wrap(estacion.abrirValvula(id)),
    cerrarValvula: (id) => wrap(estacion.cerrarValvula(id)),
    fallar: (id, codigo, texto) => wrap(estacion.fallar(id, codigo || 'FALLA MANUAL', texto || 'fallo inyectado por el operador')),
    reiniciarFalla: (id) => wrap(estacion.reiniciarFalla(id)),
    conmutarComunicacion: () => {
      const activo = !estacion.estado.comunicacion.online;
      estacion.desactivarComunicacion(activo);
      bus.emit('comunicacion', estacion.estado.comunicacion);
      return {
        ok: true,
        mensaje: activo ? 'Comunicación con el RTU restablecida.' : 'Pérdida de comunicación con el RTU simulada.',
      };
    },
    perturbacion: (tipo) => {
      const mapa = {
        caida: [{ delta: -16, duracion: 9, etiqueta: 'caída de tensión de red' }],
        sobre: [{ delta: 13, duracion: 11, etiqueta: 'sobretensión transitoria' }],
        fluctuacion: [
          { delta: 5, duracion: 4, etiqueta: 'fluctuación de red (+)' },
          { delta: -5, duracion: 4, etiqueta: 'fluctuación de red (-)' },
          { delta: 5, duracion: 4, etiqueta: 'fluctuación de red (+)' },
        ],
      };
      const lista = mapa[tipo] || mapa.caida;
      lista.forEach((p, i) => estacion.perturbacion(p.delta, p.duracion, p.etiqueta, i * p.duracion));
      return { ok: true, mensaje: `Evento de red inyectado: ${lista[0].etiqueta}.` };
    },
    fijarNivel: (valor) => {
      estacion.fijarNivel(valor);
      registrarSistema(`Nivel del reservorio forzado a ${estacion.estado.tanque.nivel.toFixed(2)} m.`);
      return { ok: true, mensaje: `Nivel fijado en ${estacion.estado.tanque.nivel.toFixed(2)} m.` };
    },
    fijarNivelDestino: (valor) => {
      estacion.fijarNivelDestino(valor);
      return { ok: true, mensaje: 'Nivel de destino forzado.' };
    },
    resumen,
    fechaSimulacion: () => estacion.fechaSimulacion(),
    ahora: () => reloj.tiempoReal,
    sello: () => selloTemporal(new Date()),
  };

  function wrap(resultado) {
    if (resultado && resultado.ok) bus.emit('accion', resultado);
    return resultado;
  }
}
