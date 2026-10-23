import { crear, vaciar } from './dom.js';
import { crearSimulador } from '../simulacion/simulador.js';
import { conectarIngesta } from '../integracion/cliente_ingesta.js';
import { crearDiagrama } from './diagrama.js';
import { crearPanelTelemetria } from './paneles/telemetria.js';
import { crearPanelEquipos, crearPanelControles } from './paneles/equipos.js';
import { crearPanelAlarmas, crearPanelEventos } from './paneles/registros.js';
import { crearPanelGraficas } from './paneles/graficas.js';
import { crearPanelHistorial } from './paneles/historial.js';
import { crearPanelConfiguracion } from './paneles/configuracion.js';
import { horaSegundos, duracion } from '../nucleo/formato.js';

const TABS = [
  { id: 'telemetria', titulo: 'TELEMETRÍA' },
  { id: 'equipos', titulo: 'EQUIPOS' },
  { id: 'alarmas', titulo: 'ALARMAS' },
  { id: 'eventos', titulo: 'EVENTOS' },
  { id: 'configuracion', titulo: 'CONFIGURACIÓN' },
];

export function arrancar(contenedorRaiz) {
  const sim = crearSimulador();
  const detenerIngesta = conectarIngesta(sim);
  const raiz = vaciar(contenedorRaiz || document.getElementById('app'));
  raiz.classList.add('aplicacion');

  const cabecera = crearCabecera(sim);

  const escenario = crear('section', { class: 'escenario' }, [
    crear('header', { class: 'escenario__barra' }, [
      crear('span', { class: 'escenario__titulo', texto: 'DIAGRAMA DE ESTACIÓN · LÍNEA DE IMPULSIÓN' }),
      crear('span', { class: 'escenario__estado', texto: 'CAUDAL EN MOVIMIENTO SE INDICA CON TRAZOS ANIMADOS' }),
    ]),
    crear('div', { class: 'escenario__lienzo', id: 'diagrama' }),
  ]);

  const lateral = crear('aside', { class: 'lateral' });
  const navTabs = crear('nav', { class: 'lateral__tabs' },
    TABS.map((t) =>
      crear('button', { class: 'tab', type: 'button', datos: { tab: t.id } }, [
        crear('span', { texto: t.titulo }),
      ]),
    ),
  );
  const cuerpoLateral = crear('div', { class: 'lateral__cuerpo' });
  lateral.appendChild(navTabs);
  lateral.appendChild(cuerpoLateral);

  const seccionGraficas = crear('section', { class: 'seccion seccion--graficas' }, [
    crear('header', { class: 'seccion__barra' }, [
      crear('span', { class: 'seccion__titulo', texto: 'TENDENCIAS EN TIEMPO REAL' }),
      crear('span', { class: 'seccion__sub', texto: 'MIN · MÁX · PROMEDIO DE LA VENTANA SELECCIONADA' }),
    ]),
    crear('div', { class: 'seccion__contenido', id: 'graficas' }),
  ]);

  const seccionHistorial = crear('section', { class: 'seccion seccion--historial' }, [
    crear('header', { class: 'seccion__barra' }, [
      crear('span', { class: 'seccion__titulo', texto: 'HISTORIAL DE TELEMEDIDA' }),
      crear('span', { class: 'seccion__sub', texto: 'REGISTROS MUESTREADOS DURANTE LA SESIÓN' }),
    ]),
    crear('div', { class: 'seccion__contenido', id: 'historial' }),
  ]);

  raiz.appendChild(cabecera.nodo);
  raiz.appendChild(
    crear('div', { class: 'aplicacion__filaPrincipal' }, [escenario, lateral]),
  );
  raiz.appendChild(seccionGraficas);
  raiz.appendChild(seccionHistorial);

  const avisos = crear('div', { class: 'avisos' });
  raiz.appendChild(avisos);

  function avisar(resultado) {
    if (!resultado) return resultado;
    const aviso = crear('div', { class: `aviso ${resultado.ok === false ? 'aviso--error' : 'aviso--ok'}` }, [
      crear('span', { class: 'aviso__texto', texto: resultado.mensaje || 'Operación ejecutada.' }),
    ]);
    avisos.appendChild(aviso);
    requestAnimationFrame(() => aviso.classList.add('aviso--visible'));
    setTimeout(() => {
      aviso.classList.remove('aviso--visible');
      setTimeout(() => aviso.remove(), 400);
    }, 3600);
    while (avisos.children.length > 5) avisos.firstChild.remove();
    return resultado;
  }

  const envoltorioControles = crear('div', { class: 'bloque-lateral' });
  const envoltorios = {
    telemetria: crear('div', { class: 'bloque-lateral' }),
    equipos: crear('div', { class: 'bloque-lateral' }),
    alarmas: crear('div', { class: 'bloque-lateral' }),
    eventos: crear('div', { class: 'bloque-lateral' }),
    configuracion: crear('div', { class: 'bloque-lateral' }),
  };

  const panelControles = crearPanelControles(envoltorioControles, sim, avisar);
  const panelTelemetria = crearPanelTelemetria(envoltorios.telemetria, sim);
  const panelEquipos = crearPanelEquipos(envoltorios.equipos, sim, avisar);
  const panelAlarmas = crearPanelAlarmas(envoltorios.alarmas, sim, avisar);
  const panelEventos = crearPanelEventos(envoltorios.eventos, sim, avisar);
  const panelConfiguracion = crearPanelConfiguracion(envoltorios.configuracion, sim, avisar);

  const paneles = {
    telemetria: [panelTelemetria],
    equipos: [panelEquipos],
    alarmas: [panelAlarmas],
    eventos: [panelEventos],
    configuracion: [panelConfiguracion],
  };

  const diagrama = crearDiagrama(escenario.querySelector('#diagrama'), sim);
  const panelGraficas = crearPanelGraficas(seccionGraficas.querySelector('#graficas'), sim);
  const panelHistorial = crearPanelHistorial(seccionHistorial.querySelector('#historial'), sim, avisar);

  let tabActiva = 'telemetria';
  function mostrarTab(id) {
    tabActiva = id;
    vaciar(cuerpoLateral);
    cuerpoLateral.appendChild(envoltorioControles);
    cuerpoLateral.appendChild(envoltorios[id]);
    for (const boton of navTabs.children) {
      boton.classList.toggle('tab--activo', boton.dataset.tab === id);
    }
    if (id === 'configuracion') panelConfiguracion.construir();
    actualizarTodo(true);
  }

  for (const boton of navTabs.children) {
    boton.addEventListener('click', () => mostrarTab(boton.dataset.tab));
  }

  let ultimoRapido = performance.now();
  let ultimoLento = 0;

  function actualizarTodo(forzar) {
    const ahora = performance.now();
    diagrama.actualizar(sim.estado(), Math.min(0.1, (ahora - ultimoRapido) / 1000));
    ultimoRapido = ahora;
    for (const panel of paneles[tabActiva]) panel.actualizar();
    if (forzar || ahora - ultimoLento > 1000) {
      ultimoLento = ahora;
      panelGraficas.actualizar();
      panelHistorial.actualizar();
    }
    cabecera.actualizar();
  }

  function ciclo() {
    sim.avanzarReloj();
    actualizarTodo(false);
    requestAnimationFrame(ciclo);
  }

  window.addEventListener('resize', () => panelGraficas.redimensionar());

  mostrarTab('telemetria');
  sim.iniciar();
  window.__sim = sim;
  window.__detenerIngesta = detenerIngesta;
  requestAnimationFrame(ciclo);
  return sim;
}

function crearCabecera(sim) {
  const titulo = crear('div', { class: 'cabecera__identidad' }, [
    crear('span', { class: 'cabecera__logo', texto: 'EB' }),
    crear('div', { class: 'cabecera__texto' }, [
      crear('span', { class: 'cabecera__nombre', texto: sim.config().estacion.nombre }),
      crear('span', { class: 'cabecera__sub', texto: `${sim.config().estacion.id} · ${sim.config().estacion.linea}` }),
    ]),
  ]);

  const relojReal = crear('span', { class: 'cabecera__reloj mono', texto: '--:--:--' });
  const relojSim = crear('span', { class: 'cabecera__reloj mono cabecera__reloj--sim', texto: '00:00:00' });
  const estadoSim = crear('span', { class: 'pill pill--pausa', texto: 'EN PAUSA' });
  const ledComunicacion = crear('span', { class: 'led' });
  const textoComunicacion = crear('span', { class: 'cabecera__comunicacion', texto: 'ONLINE' });
  const conteoAlarmas = crear('span', { class: 'pill', texto: 'SIN ALARMAS' });

  const btnIniciar = crear('button', { class: 'boton boton--primario', type: 'button' }, [
    crear('span', { texto: 'INICIAR SIMULACIÓN' }),
  ]);
  const btnReiniciar = crear('button', { class: 'boton boton--fantasma', type: 'button', texto: 'REINICIAR' });
  const selectorVelocidad = crear('select', { class: 'selector selector--cabecera' },
    [0.5, 1, 2, 5, 6, 10, 20, 60].map((v) => crear('option', { value: String(v), texto: `x${v}` })));
  selectorVelocidad.value = String(sim.reloj.velocidad);

  btnIniciar.addEventListener('click', () => sim.alternar());
  btnReiniciar.addEventListener('click', () => {
    const estabaCorriendo = sim.reloj.corriendo;
    sim.reiniciar();
    if (estabaCorriendo) sim.iniciar();
  });
  selectorVelocidad.addEventListener('change', () => {
    sim.establecerVelocidad(Number(selectorVelocidad.value));
  });

  const nodo = crear('header', { class: 'cabecera' }, [
    titulo,
    crear('div', { class: 'cabecera__telemetria' }, [
      crear('div', { class: 'cabecera__bloque' }, [
        crear('span', { class: 'cabecera__etiqueta', texto: 'HORA SISTEMA' }),
        relojReal,
      ]),
      crear('div', { class: 'cabecera__bloque' }, [
        crear('span', { class: 'cabecera__etiqueta', texto: 'HORA SIMULACIÓN' }),
        relojSim,
      ]),
      crear('div', { class: 'cabecera__bloque' }, [
        crear('span', { class: 'cabecera__etiqueta', texto: 'SIMULACIÓN' }),
        estadoSim,
      ]),
      crear('div', { class: 'cabecera__bloque cabecera__bloque--comunicacion' }, [
        ledComunicacion,
        textoComunicacion,
      ]),
      conteoAlarmas,
    ]),
    crear('div', { class: 'cabecera__controles' }, [
      btnIniciar,
      btnReiniciar,
      selectorVelocidad,
    ]),
  ]);

  function actualizar() {
    const estado = sim.estado();
    relojReal.textContent = horaSegundos(new Date());
    relojSim.textContent = duracion(estado.tiempo);
    const corriendo = sim.reloj.corriendo;
    estadoSim.textContent = corriendo ? 'EN CURSO' : 'EN PAUSA';
    estadoSim.className = `pill ${corriendo ? 'pill--activo' : 'pill--pausa'}`;
    btnIniciar.querySelector('span').textContent = corriendo ? 'PAUSAR SIMULACIÓN' : 'INICIAR SIMULACIÓN';
    btnIniciar.classList.toggle('boton--parar', corriendo);
    if (document.activeElement !== selectorVelocidad) selectorVelocidad.value = String(sim.reloj.velocidad);
    const online = estado.comunicacion.online;
    ledComunicacion.style.background = online ? '#35d07f' : '#e64a4a';
    ledComunicacion.style.boxShadow = online ? '0 0 8px #35d07f' : '0 0 8px #e64a4a';
    textoComunicacion.textContent = online ? 'ONLINE' : 'OFFLINE';
    textoComunicacion.classList.toggle('cabecera__comunicacion--offline', !online);
    const conteo = sim.alarmas().contar();
    conteoAlarmas.textContent = conteo.totales === 0 ? 'SIN ALARMAS' : `${conteo.totales} ALARMA${conteo.totales > 1 ? 'S' : ''}`;
    conteoAlarmas.className = `pill ${conteo.criticas ? 'pill--alarma' : conteo.totales ? 'pill--aviso' : ''}`;
  }

  return { nodo, actualizar };
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => arrancar(document.getElementById('app')));
  } else {
    arrancar(document.getElementById('app'));
  }
}
