import argparse
import sqlite3
import os
import random
import math
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'edgemant.db')

random.seed(20260420)


def limpiar_datos_anteriores(conn):
    """Limpia muestras y tablas dependientes sin dejar claves idempotentes obsoletas."""
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()

    # Estas tablas aparecen solo después de usar los servicios de importación,
    # integración o dashboard, por eso se comprueba su existencia.
    tablas_dependientes = (
        'ingestas_csv',
        'ingestas_simulador',
        'detecciones_anomalias',
    )
    for tabla in tablas_dependientes:
        existe = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (tabla,),
        ).fetchone()
        if existe:
            cursor.execute(f'DELETE FROM "{tabla}"')

    cursor.execute('DELETE FROM registros_telemetria')
    cursor.execute('DELETE FROM eventos')
    cursor.execute('DELETE FROM alarmas')
    cursor.execute('DELETE FROM motores')
    cursor.execute('DELETE FROM estaciones')


def generar_datos_prueba(reiniciar=False):
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f'Base de datos no encontrada: {DB_PATH}')

    conn = sqlite3.connect(DB_PATH)
    try:
        if reiniciar:
            limpiar_datos_anteriores(conn)
        else:
            tablas = (
                'estaciones', 'motores', 'registros_telemetria',
                'eventos', 'alarmas', 'ingestas_csv',
                'ingestas_simulador', 'detecciones_anomalias',
            )
            con_datos = []
            for tabla in tablas:
                existe = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                    (tabla,),
                ).fetchone()
                if existe and conn.execute(
                    f'SELECT EXISTS(SELECT 1 FROM "{tabla}" LIMIT 1)'
                ).fetchone()[0]:
                    con_datos.append(tabla)
            if con_datos:
                raise RuntimeError(
                    'La base de datos ya contiene datos (' + ', '.join(con_datos) + '). '
                    'No se modificó nada. Usa generar_datos_prueba(reiniciar=True) '
                    'solo si quieres reemplazar los datos existentes.'
                )
        cursor = conn.cursor()

        cursor.execute(
            'INSERT INTO estaciones (id, nombre, linea, zona, operador) VALUES (?, ?, ?, ?, ?)',
            ('EB-01', 'ESTACIÓN DE BOMBEO PRINCIPAL', 'Impulsión EB-01 → Red de distribución Norte', 'SECTOR NORTE', 'Sala de Control SCADA')
        )

        motores = [
            ('M-01', 'Bomba de impulsión principal 1', 20, 220, 3, 0.88, 0.85, 78, 25),
            ('M-02', 'Bomba de impulsión principal 2', 50, 220, 3, 0.9, 0.86, 48.7, 80),
        ]
        for m in motores:
            cursor.execute(
                'INSERT INTO motores (id, estacion_id, descripcion, hp, voltaje_nominal, etapas, eficiencia, factor_potencia_nominal, altura_cierre, caudal_diseno) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (m[0], 'EB-01', m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8])
            )

        tiempo_inicio = datetime(2026, 4, 20, 8, 0, 0)
        duracion_segundos = 3600
        paso = 1.0
        muestras = int(duracion_segundos / paso)

        registros = []
        for i in range(muestras):
            t = i * paso
            ts = tiempo_inicio + timedelta(seconds=t)
            timestamp = int(ts.timestamp() * 1000)
            fecha = ts.strftime('%d/%m/%Y')
            hora = ts.strftime('%H:%M:%S')
            tiempo_sim = f'{int(t) // 3600:02d}:{(int(t) % 3600) // 60:02d}:{int(t) % 60:02d}'

            for motor_id in ['M-01', 'M-02']:
                altura = 22 + random.uniform(-0.5, 0.5)
                if motor_id == 'M-01':
                    voltaje = 220 + random.uniform(-1.5, 1.5) + random.uniform(-3, 3) * math.sin(t / 60)
                    amperaje = max(0, 45 + random.uniform(-2, 2) + 5 * math.sin(t / 120))
                    caudal = max(0, 22 + random.uniform(-1, 1) + 3 * math.sin(t / 90))
                    potencia = caudal * 0.001 * altura * 9810 / 0.88 / 1000
                    carga = potencia / (20 * 0.7457) * 100
                    factor_potencia = 0.85 + random.uniform(-0.02, 0.02)
                    estado_motor = 'OPERATIVO' if random.random() > 0.01 else 'ARRANCANDO'
                    estado_valvula = 'ABIERTA' if random.random() > 0.01 else 'ABRIENDO'
                    posicion_valvula = 100 if random.random() > 0.01 else random.uniform(80, 99)
                    velocidad_rotacion = 100 if random.random() > 0.01 else random.uniform(90, 99)
                    horas_operacion = t / 3600
                    caudal_total = caudal + 68
                    potencia_total = potencia + (68 * 0.001 * altura * 9810 / 0.9 / 1000)
                else:
                    voltaje = 220 + random.uniform(-1.5, 1.5) + random.uniform(-3, 3) * math.sin(t / 60)
                    amperaje = max(0, 85 + random.uniform(-3, 3) + 8 * math.sin(t / 120))
                    caudal = max(0, 68 + random.uniform(-2, 2) + 5 * math.sin(t / 90))
                    potencia = caudal * 0.001 * altura * 9810 / 0.9 / 1000
                    carga = potencia / (50 * 0.7457) * 100
                    factor_potencia = 0.86 + random.uniform(-0.02, 0.02)
                    estado_motor = 'OPERATIVO' if random.random() > 0.01 else 'ARRANCANDO'
                    estado_valvula = 'ABIERTA' if random.random() > 0.01 else 'ABRIENDO'
                    posicion_valvula = 100 if random.random() > 0.01 else random.uniform(80, 99)
                    velocidad_rotacion = 100 if random.random() > 0.01 else random.uniform(90, 99)
                    horas_operacion = t / 3600
                    caudal_total = caudal + 22
                    potencia_total = potencia + (22 * 0.001 * altura * 9810 / 0.88 / 1000)

                nivel = 4.2 + random.uniform(-0.5, 0.5) + 0.3 * math.sin(t / 300)
                registros.append((
                    t, tiempo_sim, timestamp, fecha, hora, motor_id,
                    nivel, nivel / 8 * 100,
                    voltaje, voltaje - abs(amperaje) * 0.02, amperaje,
                    45 if motor_id == 'M-01' else 120,
                    caudal, potencia,
                    20 if motor_id == 'M-01' else 50,
                    carga, altura, factor_potencia,
                    estado_motor, estado_valvula, posicion_valvula, velocidad_rotacion, horas_operacion,
                    caudal_total, potencia_total,
                    amperaje + (85 if motor_id == 'M-01' else 45),
                    3.4 + random.uniform(-0.3, 0.3) + 0.2 * math.sin(t / 400),
                    35 + random.uniform(-2, 2) + 3 * math.sin(t / 200),
                    8.0,
                ))

        cursor.executemany('''
            INSERT INTO registros_telemetria (
                tiempo, tiempo_simulacion, timestamp, fecha, hora, motor_id,
                nivel, nivel_porcentaje, voltaje, voltaje_terminal, amperaje, corriente_nominal,
                caudal, potencia, potencia_nominal, carga, altura, factor_potencia,
                estado_motor, estado_valvula, posicion_valvula, velocidad_rotacion, horas_operacion,
                caudal_total, potencia_total, corriente_total, nivel_destino, demanda, nivel_tanque_maximo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', registros)

        eventos = [
            (0, tiempo_inicio.strftime('%H:%M:%S'), 'SISTEMA', 'ESTACIÓN', 'INFO', 'Simulación iniciada. Adquisición de datos activa.', ''),
            (0, tiempo_inicio.strftime('%H:%M:%S'), 'OPERACIÓN', 'M-01', 'INFO', 'Orden de arranque de M-01 (20 HP) aceptada.', ''),
            (5, (tiempo_inicio + timedelta(seconds=5)).strftime('%H:%M:%S'), 'OPERACIÓN', 'M-01', 'INFO', 'M-01 en OPERATIVO (velocidad 100 %, 45.2 A).', ''),
        ]
        for evento in eventos:
            cursor.execute(
                'INSERT INTO eventos (tiempo, hora, tipo, equipo, severidad, texto, estado) VALUES (?, ?, ?, ?, ?, ?, ?)',
                evento
            )

        conn.commit()
        print(f'Datos de prueba generados: {len(registros)} registros de telemetría')
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Genera telemetría sintética para pruebas de EdgeMant.'
    )
    parser.add_argument(
        '--reiniciar',
        action='store_true',
        help='Borra los datos existentes de la base de datos antes de generar los datos de prueba.',
    )
    args = parser.parse_args()
    generar_datos_prueba(reiniciar=args.reiniciar)
