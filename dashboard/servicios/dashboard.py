import os
import sqlite3
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ML_DIR = os.path.join(BASE_DIR, 'ml')
DB_PATH = os.path.join(BASE_DIR, 'base_datos', 'edgemant.db')
RUTA_UMBRAL = os.path.join(ML_DIR, 'modelos', 'umbral.txt')

if ML_DIR not in sys.path:
    sys.path.insert(0, ML_DIR)

from inferir import inferir, cargar_modelo
from interpretar import interpretar_fila
from servicio_historial import (
    guardar_deteccion,
    obtener_historial,
    obtener_estadisticas,
    asegurar_tabla_detecciones,
)


def ejecutar_inferencia_y_guardar():
    df_resultado, _ = inferir()
    _, scaler, columnas, umbral = cargar_modelo()
    guardados = 0

    for _, fila in df_resultado.iterrows():
        if int(fila['anomalia']) != 1:
            continue

        interpretacion = interpretar_fila(fila, columnas, scaler, umbral)
        deteccion = {
            'id': int(fila['id']),
            'motor_id': str(fila.get('motor_id', '')),
            'tiempo': float(fila['tiempo']),
            'fecha': str(fila.get('fecha', '') or ''),
            'hora': str(fila.get('hora', '') or ''),
            'error_reconstruccion': float(fila['error_reconstruccion']),
            'umbral': float(umbral),
            'severidad': interpretacion['severidad'],
            'tipo_interpretacion': interpretacion['tipo_interpretacion'],
            'descripcion': interpretacion['descripcion'],
            'variables_relevantes': interpretacion['variables_relevantes'],
        }
        if guardar_deteccion(deteccion):
            guardados += 1

    return guardados


def obtener_dashboard():
    if not os.path.isfile(DB_PATH):
        raise FileNotFoundError(f'No se encontró la base de datos: {DB_PATH}')

    asegurar_tabla_detecciones()
    estadisticas = obtener_estadisticas()

    with sqlite3.connect(DB_PATH) as conn:
        total_registros = conn.execute(
            'SELECT COUNT(*) FROM registros_telemetria'
        ).fetchone()[0]
        motores = [
            fila[0] for fila in conn.execute(
                'SELECT DISTINCT motor_id FROM registros_telemetria ORDER BY motor_id'
            ).fetchall()
        ]

    try:
        with open(RUTA_UMBRAL, 'r', encoding='utf-8') as archivo:
            umbral = float(archivo.read().strip())
    except (OSError, ValueError):
        umbral = None

    estadisticas.update({
        'total_registros': int(total_registros),
        'total_detecciones': int(estadisticas['total']),
        'umbral': umbral,
    })

    return {
        'estadisticas': estadisticas,
        'historial': obtener_historial(50),
        'motores': motores,
    }
