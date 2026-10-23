import { svg, vaciar } from './dom.js';
import { numero, porcentaje } from '../nucleo/formato.js';

export function crearDiagrama(contenedor, sim) {
  let refs = { motores: new Map(), ids: '' };
  let geometria = null;
  let reloj = 0;

  const raiz = svg('svg', { class: 'diagrama', preserveAspectRatio: 'xMidYMid meet' });
  const capaFondo = svg('g', { class: 'capa capa--fondo' });
  const capaTuberias = svg('g', { class: 'capa capa--tuberias' });
  const capaEquipos = svg('g', { class: 'capa capa--equipos' });
  const capaEtiquetado = svg('g', { class: 'capa capa--etiquetas' });
  raiz.appendChild(capaFondo);
  raiz.appendChild(capaTuberias);
  raiz.appendChild(capaEquipos);
  raiz.appendChild(capaEtiquetado);
  vaciar(contenedor).appendChild(raiz);

  const texto = (contenido, atributos) => svg('text', atributos, [document.createTextNode(contenido)]);

  function colorEstado(estado) {
    if (estado === 'OPERATIVO') return '#35d07f';
    if (estado === 'ARRANCANDO') return '#f5c451';
    if (estado === 'DETENIÉNDOSE') return '#f0934f';
    if (estado === 'FALLA') return '#e64a4a';
    return '#4a5a6a';
  }

  function trazo(segs) {
    return segs.map(([x1, y1, x2, y2]) => `M ${x1} ${y1} L ${x2} ${y2}`).join(' ');
  }

  function parDeTuberias(segs, clase) {
    const d = trazo(segs);
    const base = svg('path', { class: `tuberia ${clase || ''}`, d });
    const flujo = svg('path', { class: 'flujo', d, opacity: '0.12' });
    const grupo = svg('g', { class: 'tuberias' }, [base, flujo]);
    capaTuberias.appendChild(grupo);
    return { grupo, flujo, base };
  }

  function defs() {
    capaFondo.appendChild(
      svg('defs', {}, [
        svg('pattern', { id: 'rejilla', width: 34, height: 34, patternUnits: 'userSpaceOnUse' }, [
          svg('path', { d: 'M 34 0 L 0 0 0 34', fill: 'none', stroke: 'rgba(125,165,195,.06)', 'stroke-width': 1 }),
        ]),
        svg('linearGradient', { id: 'agua', x1: 0, y1: 0, x2: 0, y2: 1 }, [
          svg('stop', { offset: '0%', 'stop-color': '#2f86c4' }),
          svg('stop', { offset: '100%', 'stop-color': '#0b3552' }),
        ]),
        svg('linearGradient', { id: 'acero', x1: 0, y1: 0, x2: 1, y2: 0 }, [
          svg('stop', { offset: '0%', 'stop-color': '#26333f' }),
          svg('stop', { offset: '35%', 'stop-color': '#1b2732' }),
          svg('stop', { offset: '100%', 'stop-color': '#0f1720' }),
        ]),
      ]),
    );
  }

  function construir(cfg) {
    vaciar(capaFondo);
    vaciar(capaTuberias);
    vaciar(capaEquipos);
    vaciar(capaEtiquetado);
    refs = { motores: new Map(), ids: cfg.motores.map((m) => m.id).join('|'), cfg };

    const motores = cfg.motores;
    const n = motores.length;
    const paso = n > 2 ? 205 : 245;
    const columnas = motores.map((_, i) => 330 + i * paso);
    const ancho = Math.max(1020, columnas[n - 1] + 400);
    const alto = 660;
    raiz.setAttribute('viewBox', `0 0 ${ancho} ${alto}`);
    const ySuccion = 572;
    const yImpulsion = 178;
    const tanque = { x: 46, ancho: 196, arriba: 76, abajo: 476 };
    const destino = { x: columnas[n - 1] + 250, ancho: 162, arriba: 62, abajo: 320 };
    geometria = { ancho, alto, columnas, ySuccion, yImpulsion, tanque, destino };

    defs();
    capaFondo.appendChild(svg('rect', { x: 0, y: 0, width: ancho, height: alto, fill: 'url(#rejilla)' }));

    construirTanque(cfg, tanque, ySuccion);
    construirDestino(cfg, destino, yImpulsion);

    const xTanque = tanque.x + tanque.ancho / 2;
    refs.cabeceraSuccion = parDeTuberias([
      [xTanque, tanque.abajo, xTanque, ySuccion],
      [xTanque, ySuccion, columnas[n - 1], ySuccion],
    ], 'cabecera');
    refs.cabeceraImpulsion = parDeTuberias([
      [columnas[0] + 78, yImpulsion, destino.x + destino.ancho / 2, yImpulsion],
      [destino.x + destino.ancho / 2, yImpulsion, destino.x + destino.ancho / 2, destino.abajo],
    ], 'cabecera');

    motores.forEach((definicion, i) => {
      const xc = columnas[i];
      const succion = parDeTuberias([[xc, ySuccion, xc, 468]]);
      const impulso = parDeTuberias([
        [xc + 38, 430, xc + 78, 430],
        [xc + 78, 430, xc + 78, 470],
        [xc + 78, 470, xc + 78, yImpulsion],
      ]);
      refs.motores.set(definicion.id, construirColumna(cfg, definicion, xc, { succion, impulso }));
    });
  }

  function construirTanque(cfg, t, ySuccion) {
    const g = svg('g', { class: 'tanque' });
    const alto = t.abajo - t.arriba;
    g.appendChild(
      svg('path', {
        class: 'tanque__cuerpo',
        d: `M ${t.x + 10} ${t.arriba} L ${t.x + t.ancho - 10} ${t.arriba} L ${t.x + t.ancho} ${t.abajo} L ${t.x} ${t.abajo} Z`,
      }),
    );
    const bandaBaja = Math.max(0.02, 1 - cfg.alarmas.nivelBajo / cfg.tanque.altura);
    const bandaAlta = Math.min(0.99, cfg.alarmas.nivelCriticoAlto / cfg.tanque.altura);
    for (const [desde, hasta, clase] of [
      [0, bandaBaja, 'tanque__banda tanque__banda--baja'],
      [bandaBaja, bandaAlta, 'tanque__banda tanque__banda--ok'],
      [bandaAlta, 1, 'tanque__banda tanque__banda--alta'],
    ]) {
      g.appendChild(
        svg('rect', {
          class: clase,
          x: t.x + 2,
          y: t.arriba + alto * desde,
          width: t.ancho - 4,
          height: Math.max(0, alto * (hasta - desde)),
        }),
      );
    }
    const agua = svg('path', { class: 'tanque__aguaCuerpo', d: '', fill: 'url(#agua)' });
    const ola = svg('path', { class: 'tanque__ola', d: '' });
    g.appendChild(agua);
    g.appendChild(ola);
    for (let i = 0; i <= Math.floor(cfg.tanque.altura); i += 1) {
      const y = t.abajo - (alto * i) / cfg.tanque.altura;
      g.appendChild(svg('line', { class: 'tanque__marca', x1: t.x - 14, y1: y, x2: t.x - 1, y2: y }));
      g.appendChild(texto(String(i), { class: 'tanque__escala', x: t.x - 18, y: y + 4, 'text-anchor': 'end' }));
    }
    g.appendChild(texto(`${cfg.tanque.id} · ${cfg.tanque.nombre}`, { class: 'equipo-tag', x: t.x + t.ancho / 2, y: t.arriba - 52, 'text-anchor': 'middle' }));
    const lectura = texto('', { class: 'tanque__lectura', x: t.x + t.ancho / 2, y: t.arriba - 22, 'text-anchor': 'middle' });
    const porcentajeTexto = texto('', { class: 'tanque__lectura tanque__lectura--sub', x: t.x + t.ancho / 2, y: t.arriba - 6, 'text-anchor': 'middle' });
    g.appendChild(lectura);
    g.appendChild(porcentajeTexto);
    g.appendChild(
      svg('path', { class: 'tuberia', d: `M ${t.x + t.ancho / 2} 4 L ${t.x + t.ancho / 2} ${t.arriba - 66}` }),
    );
    const entrada = svg('path', { class: 'flujo', d: `M ${t.x + t.ancho / 2} 4 L ${t.x + t.ancho / 2} ${t.arriba - 66}`, opacity: '0.12' });
    g.appendChild(entrada);
    g.appendChild(texto('INGRESO DE AGUA CRUDA', { class: 'etiqueta', x: t.x + t.ancho / 2 + 12, y: 22 }));
    const caudalEntrada = texto('', { class: 'etiqueta etiqueta--valor', x: t.x + t.ancho / 2 + 12, y: 38 });
    g.appendChild(caudalEntrada);
    capaEquipos.appendChild(g);
    refs.tanque = { agua, ola, lectura, porcentajeTexto, caudalEntrada, entrada, alto, t };
  }

  function construirDestino(cfg, d, yImpulsion) {
    const g = svg('g', { class: 'tanque tanque--destino' });
    const alto = d.abajo - d.arriba;
    g.appendChild(
      svg('path', {
        class: 'tanque__cuerpo',
        d: `M ${d.x + 8} ${d.arriba} L ${d.x + d.ancho - 8} ${d.arriba} L ${d.x + d.ancho} ${d.abajo} L ${d.x} ${d.abajo} Z`,
      }),
    );
    const bandaAlta = Math.min(0.99, cfg.destino.nivelMaximo / cfg.destino.altura);
    g.appendChild(
      svg('rect', {
        class: 'tanque__banda tanque__banda--ok',
        x: d.x + 2,
        y: d.arriba + alto * bandaAlta,
        width: d.ancho - 4,
        height: alto * (1 - bandaAlta),
      }),
    );
    g.appendChild(
      svg('rect', {
        class: 'tanque__banda tanque__banda--baja',
        x: d.x + 2,
        y: d.arriba,
        width: d.ancho - 4,
        height: alto * (cfg.destino.nivelMinimo / cfg.destino.altura),
      }),
    );
    const agua = svg('path', { class: 'tanque__aguaCuerpo', d: '', fill: 'url(#agua)' });
    g.appendChild(agua);
    g.appendChild(texto(`${cfg.destino.id} · DESTINO`, { class: 'equipo-tag', x: d.x + d.ancho / 2, y: d.arriba - 32, 'text-anchor': 'middle' }));
    const lectura = texto('', { class: 'tanque__lectura', x: d.x + d.ancho / 2, y: d.arriba - 8, 'text-anchor': 'middle' });
    g.appendChild(lectura);
    const demanda = texto('', { class: 'etiqueta', x: d.x + d.ancho / 2, y: d.abajo + 24, 'text-anchor': 'middle' });
    g.appendChild(demanda);
    const presion = texto('', { class: 'etiqueta etiqueta--valor', x: d.x + d.ancho / 2, y: d.abajo + 40, 'text-anchor': 'middle' });
    g.appendChild(presion);
    capaEquipos.appendChild(g);
    refs.destino = { agua, lectura, demanda, presion, alto, d };
  }

  function construirColumna(cfg, definicion, xc, tuberias) {
    const g = svg('g', { class: 'columna-maquina', 'data-motor': definicion.id });
    const caja = svg('g', { class: 'motor-caja' });
    caja.appendChild(svg('rect', { class: 'motor-caja__cuerpo', x: xc - 92, y: 296, width: 152, height: 68, rx: 5 }));
    caja.appendChild(texto(definicion.id, { class: 'motor-caja__id', x: xc - 80, y: 322 }));
    caja.appendChild(texto(`${definicion.hp} HP · ${definicion.voltaje} V`, { class: 'motor-caja__dato', x: xc - 80, y: 342 }));
    const estadoTexto = texto('PARADO', { class: 'motor-caja__estado', x: xc + 52, y: 342, 'text-anchor': 'end' });
    caja.appendChild(estadoTexto);
    caja.appendChild(svg('circle', { class: 'led motor-caja__led', cx: xc + 42, cy: 313, r: 6 }));
    caja.appendChild(svg('rect', { class: 'motor-caja__barraFondo', x: xc - 80, y: 350, width: 132, height: 6, rx: 3 }));
    const cargaRelleno = svg('rect', { class: 'motor-caja__barra', x: xc - 80, y: 350, width: 0, height: 6, rx: 3 });
    caja.appendChild(cargaRelleno);
    g.appendChild(caja);
    g.appendChild(svg('path', { class: 'acople', d: `M ${xc} 364 L ${xc} 392` }));
    g.appendChild(svg('circle', { class: 'acople__punto', cx: xc, cy: 378, r: 4 }));

    const bomba = svg('g', { class: 'bomba', transform: `translate(${xc} 430)` });
    bomba.appendChild(svg('circle', { class: 'bomba__carcasa', cx: 0, cy: 0, r: 38 }));
    bomba.appendChild(svg('circle', { class: 'bomba__aro', cx: 0, cy: 0, r: 31 }));
    const rotor = svg('g', { class: 'bomba__rotor' });
    for (let i = 0; i < 5; i += 1) {
      rotor.appendChild(
        svg('path', { class: 'bomba__pala', d: 'M 2 -5 C 12 -17, 24 -15, 28 -3 C 19 -6, 9 -3, 2 -5 Z', transform: `rotate(${i * 72})` }),
      );
    }
    rotor.appendChild(svg('circle', { class: 'bomba__eje', cx: 0, cy: 0, r: 6 }));
    bomba.appendChild(rotor);
    bomba.appendChild(svg('circle', { class: 'led bomba__led', cx: 0, cy: -50, r: 5 }));
    g.appendChild(bomba);

    const valvula = svg('g', { class: 'valvula', transform: `translate(${xc + 78} 300)` });
    const simbolo = svg('g', { class: 'valvula__simbolo' });
    simbolo.appendChild(svg('path', { class: 'valvula__cuerpo', d: 'M -17 -15 L -2 0 L -17 15 Z' }));
    simbolo.appendChild(svg('path', { class: 'valvula__cuerpo', d: 'M 17 -15 L 2 0 L 17 15 Z' }));
    valvula.appendChild(simbolo);
    valvula.appendChild(svg('circle', { class: 'led valvula__led', cx: 0, cy: -28, r: 4.5 }));
    g.appendChild(valvula);

    capaEquipos.appendChild(g);

    const etiqueta = svg('g', { class: 'instrumento' });
    etiqueta.appendChild(svg('rect', { class: 'instrumento__fondo', x: xc - 92, y: 208, width: 152, height: 60, rx: 4 }));
    const textoQ = texto('Q 0.0 L/s', { class: 'instrumento__valor', x: xc - 80, y: 230 });
    const textoH = texto('H 0.0 m', { class: 'instrumento__valor', x: xc - 80, y: 252 });
    const textoEstado = texto('', { class: 'instrumento__nota', x: xc + 48, y: 230, 'text-anchor': 'end' });
    etiqueta.appendChild(textoQ);
    etiqueta.appendChild(textoH);
    etiqueta.appendChild(textoEstado);
    const tagValvula = texto(definicion.valvula.id, { class: 'equipo-tag', x: xc + 78, y: 336, 'text-anchor': 'middle' });
    etiqueta.appendChild(tagValvula);
    const posValvula = texto('', { class: 'equipo-tag equipo-tag--valor', x: xc + 78, y: 350, 'text-anchor': 'middle' });
    etiqueta.appendChild(posValvula);
    capaEtiquetado.appendChild(etiqueta);

    return {
      definicion,
      xc,
      grupo: g,
      led: caja.querySelector('.motor-caja__led'),
      ledBomba: bomba.querySelector('.bomba__led'),
      ledValvula: valvula.querySelector('.valvula__led'),
      estadoTexto,
      cargaRelleno,
      rotor,
      simbolo,
      textoQ,
      textoH,
      textoEstado,
      posValvula,
      angulo: 0,
      tuberias,
    };
  }

  function actualizar(estado, dtReal) {
    reloj += dtReal;
    const ids = estado.motores.map((m) => m.id).join('|');
    if (ids !== refs.ids) construir(sim.config());
    if (!geometria) construir(sim.config());

    const t = refs.tanque;
    const nivelRel = Math.max(0, Math.min(1, estado.tanque.nivel / estado.tanque.altura));
    const ySuperficie = t.t.abajo - t.alto * nivelRel;
    const amplitud = 2.6;
    const fase = reloj * 1.5;
    const x0 = t.t.x + 3;
    const x1 = t.t.x + t.t.ancho - 3;
    const mitad = t.t.x + t.t.ancho / 2;
    t.agua.setAttribute(
      'd',
      `M ${x0} ${t.t.abajo} L ${x0} ${ySuperficie} Q ${t.t.x + t.t.ancho * 0.25} ${ySuperficie + Math.sin(fase) * amplitud} ${mitad} ${ySuperficie} Q ${t.t.x + t.t.ancho * 0.75} ${ySuperficie - Math.sin(fase) * amplitud} ${x1} ${ySuperficie} L ${x1} ${t.t.abajo} Z`,
    );
    t.ola.setAttribute(
      'd',
      `M ${x0} ${ySuperficie} Q ${t.t.x + t.t.ancho * 0.25} ${ySuperficie + Math.sin(fase) * amplitud} ${mitad} ${ySuperficie} Q ${t.t.x + t.t.ancho * 0.75} ${ySuperficie - Math.sin(fase) * amplitud} ${x1} ${ySuperficie}`,
    );
    t.lectura.textContent = `${numero(estado.tanque.nivel, 2)} m`;
    t.porcentajeTexto.textContent = porcentaje(nivelRel, 0);
    t.caudalEntrada.textContent = `${numero(estado.tanque.ingreso, 1)} L/s`;
    animarSegmento(t.entrada, estado.tanque.ingreso * 20, dtReal);

    const d = refs.destino;
    const relDestino = Math.max(0, Math.min(1, estado.destino.nivel / estado.destino.altura));
    const yDestino = d.d.abajo - d.alto * relDestino;
    d.agua.setAttribute('d', `M ${d.d.x + 3} ${d.d.abajo} L ${d.d.x + 3} ${yDestino} L ${d.d.x + d.d.ancho - 3} ${yDestino} L ${d.d.x + d.d.ancho - 3} ${d.d.abajo} Z`);
    d.lectura.textContent = `${numero(estado.destino.nivel, 2)} m`;
    d.demanda.textContent = `Demanda de red ${numero(estado.destino.demanda, 1)} L/s`;
    d.presion.textContent = `${numero(estado.destino.presion * 10, 2)} bar en destino`;

    let caudalTotal = 0;
    let caudalSuccion = 0;
    for (const motor of estado.motores) {
      const ref = refs.motores.get(motor.id);
      if (!ref) continue;
      const color = colorEstado(motor.estado);
      ref.led.setAttribute('fill', color);
      ref.ledBomba.setAttribute('fill', color);
      ref.estadoTexto.textContent = motor.estado;
      ref.estadoTexto.setAttribute('fill', color);
      ref.grupo.classList.toggle('is-falla', motor.estado === 'FALLA');
      ref.grupo.classList.toggle('is-activo', motor.velocidad > 0.02);
      const carga = Math.max(0, Math.min(1.4, motor.carga));
      ref.cargaRelleno.setAttribute('width', Math.min(1, carga) * 132);
      ref.cargaRelleno.setAttribute('fill', carga > 1.12 ? '#e64a4a' : color);
      ref.angulo = (ref.angulo + motor.velocidad * 780 * dtReal) % 360;
      ref.rotor.setAttribute('transform', `rotate(${ref.angulo.toFixed(1)})`);
      ref.rotor.style.opacity = motor.velocidad > 0.02 ? '1' : '0.4';
      ref.textoQ.textContent = `Q ${numero(motor.caudal * 1000, 1)} L/s`;
      ref.textoH.textContent = `H ${numero(motor.altura, 1)} m · ${numero(motor.corriente, 1)} A`;
      ref.textoEstado.textContent = motor.retencionCerrada ? 'RETENCIÓN' : motor.estado;
      ref.textoEstado.setAttribute('fill', motor.retencionCerrada ? '#e64a4a' : '#7d93a8');
      const pos = motor.valvula.posicion;
      const ledValvula = motor.valvula.estado === 'ABIERTA' ? '#35d07f' : motor.valvula.estado === 'CERRADA' ? '#4a5a6a' : '#f5c451';
      ref.ledValvula.setAttribute('fill', ledValvula);
      ref.simbolo.setAttribute('transform', `rotate(${((1 - pos) * 90).toFixed(1)})`);
      ref.posValvula.textContent = `${motor.valvula.estado} ${Math.round(pos * 100)}%`;
      animarSegmento(ref.tuberias.succion.flujo, motor.caudal * 1000 + (motor.velocidad > 0.02 ? 6 : 0), dtReal);
      animarSegmento(ref.tuberias.impulso.flujo, motor.caudal * 1000, dtReal);
      caudalTotal += motor.caudal;
      caudalSuccion += motor.caudal + motor.velocidad * 0.004;
    }

    const activa = estado.motores.some((m) => m.velocidad > 0.02);
    animarSegmento(refs.cabeceraSuccion.flujo, activa ? caudalSuccion * 1000 : 0, dtReal);
    animarSegmento(refs.cabeceraImpulsion.flujo, caudalTotal * 1000, dtReal);
  }

  function animarSegmento(elemento, caudal, dtReal) {
    if (!elemento) return;
    if (caudal <= 0.5) {
      elemento.style.opacity = '0.1';
      return;
    }
    elemento.style.opacity = '0.95';
    const offset = (parseFloat(elemento.dataset.offset || '0') - caudal * 26 * dtReal) % 1000;
    elemento.dataset.offset = String(offset);
    elemento.setAttribute('stroke-dashoffset', offset.toFixed(1));
  }

  return {
    elemento: raiz,
    actualizar,
  };
}