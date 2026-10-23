import os
import sqlite3

from dashboard.servicios.servicio_historial import (
    obtener_estadisticas,
    obtener_historial,
)
from dashboard.servicios.servicio_apoyo_operador import construir_apoyo_operador
from integracion.procesador_ml import (
    obtener_estado_ml,
    preparar_evaluaciones_por_estado_operativo,
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

    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        with conn:
            conn.execute('PRAGMA busy_timeout = 10000')
            preparar_evaluaciones_por_estado_operativo(conn)
            total_registros = conn.execute(
                'SELECT COUNT(*) FROM registros_telemetria'
            ).fetchone()[0]
            motores = [
                fila[0] for fila in conn.execute(
                    'SELECT DISTINCT motor_id FROM registros_telemetria ORDER BY motor_id'
                ).fetchall()
            ]
    finally:
        conn.close()

    estadisticas = obtener_estadisticas()
    estado_ml = obtener_estado_ml(DB_PATH)
    historial = obtener_historial(50)
    apoyo_operador = construir_apoyo_operador(
        historial[0] if historial else None,
        total_registros=estado_ml['evaluados'],
        total_detecciones=estadisticas['total'],
        total_detecciones_revision=estadisticas['pendientes_revision'],
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
        'registros_no_aplicables_ml': estado_ml['no_aplican'],
        'detecciones_pendientes_revision': estadisticas['pendientes_revision'],
    })

    return {
        'estadisticas': estadisticas,
        'historial': historial,
        'motores': motores,
        'apoyo_operador': apoyo_operador,
        'procesamiento_ml': estado_ml,
    }
