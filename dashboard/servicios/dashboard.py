import os
import sqlite3

from dashboard.servicios.servicio_historial import (
    asegurar_tabla_detecciones,
    obtener_estadisticas,
    obtener_historial,
)
from dashboard.servicios.servicio_apoyo_operador import construir_apoyo_operador
from integracion.procesador_ml import (
    asegurar_tabla_evaluaciones,
    obtener_estado_ml,
    procesar_pendientes,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_PATH = os.path.join(BASE_DIR, 'base_datos', 'edgemant.db')
RUTA_UMBRAL = os.path.join(BASE_DIR, 'ml', 'modelos', 'umbral.txt')


def ejecutar_inferencia_y_guardar():
    """Evalúa únicamente capturas pendientes; no vuelve a recorrer todo el histórico."""
    resumen = procesar_pendientes(db_path=DB_PATH)
    return int(resumen['detecciones_guardadas'])


def obtener_dashboard():
    if not os.path.isfile(DB_PATH):
        raise FileNotFoundError(f'No se encontró la base de datos: {DB_PATH}')

    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.execute('PRAGMA busy_timeout = 10000')
        asegurar_tabla_evaluaciones(conn)
        asegurar_tabla_detecciones(conn)
        total_registros = conn.execute(
            'SELECT COUNT(*) FROM registros_telemetria'
        ).fetchone()[0]
        motores = [
            fila[0] for fila in conn.execute(
                'SELECT DISTINCT motor_id FROM registros_telemetria ORDER BY motor_id'
            ).fetchall()
        ]

    estadisticas = obtener_estadisticas()
    estado_ml = obtener_estado_ml(DB_PATH)
    historial = obtener_historial(50)
    apoyo_operador = construir_apoyo_operador(
        historial[0] if historial else None,
        total_registros=total_registros,
        total_detecciones=estadisticas['total'],
    )

    try:
        with open(RUTA_UMBRAL, 'r', encoding='utf-8') as archivo:
            umbral = float(archivo.read().strip())
    except (OSError, ValueError):
        umbral = None

    estadisticas.update({
        'total_registros': int(total_registros),
        'total_detecciones': int(estadisticas['total']),
        'umbral': umbral,
        'registros_evaluados_ml': estado_ml['evaluados'],
        'registros_pendientes_ml': estado_ml['pendientes'],
    })

    return {
        'estadisticas': estadisticas,
        'historial': historial,
        'motores': motores,
        'apoyo_operador': apoyo_operador,
        'procesamiento_ml': estado_ml,
    }
