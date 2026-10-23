import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'base_datos', 'edgemant.db')


def _conectar():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('PRAGMA busy_timeout = 10000')
    return conn


def asegurar_tabla_detecciones(conn=None):
    propia = conn is None
    if propia:
        conn = _conectar()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS detecciones_anomalias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registro_id INTEGER,
                motor_id TEXT NOT NULL,
                tiempo REAL NOT NULL,
                fecha TEXT,
                hora TEXT,
                error_reconstruccion REAL NOT NULL,
                umbral REAL NOT NULL,
                severidad TEXT NOT NULL,
                tipo_interpretacion TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                variables_relevantes TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_detecciones_motor_tiempo
            ON detecciones_anomalias(motor_id, tiempo)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_detecciones_tiempo
            ON detecciones_anomalias(tiempo)
        ''')
        if propia:
            conn.commit()
    finally:
        if propia:
            conn.close()


def guardar_deteccion(deteccion):
    """Guarda una detecciÃ³n una sola vez por registro de telemetrÃ­a."""
    conn = _conectar()
    try:
        asegurar_tabla_detecciones(conn)
        # Serializar la comprobaciÃ³n y la inserciÃ³n para evitar duplicados
        # cuando dos peticiones del dashboard analizan el mismo registro.
        conn.execute('BEGIN IMMEDIATE')
        registro_id = deteccion.get('id')
        if registro_id is not None:
            existente = conn.execute(
                'SELECT 1 FROM detecciones_anomalias WHERE registro_id = ? LIMIT 1',
                (registro_id,),
            ).fetchone()
            if existente:
                conn.commit()
                return False

        conn.execute('''
            INSERT INTO detecciones_anomalias (
                registro_id, motor_id, tiempo, fecha, hora,
                error_reconstruccion, umbral, severidad,
                tipo_interpretacion, descripcion, variables_relevantes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            registro_id,
            deteccion['motor_id'],
            deteccion['tiempo'],
            deteccion.get('fecha'),
            deteccion.get('hora'),
            deteccion['error_reconstruccion'],
            deteccion['umbral'],
            deteccion['severidad'],
            deteccion['tipo_interpretacion'],
            deteccion['descripcion'],
            json.dumps(deteccion['variables_relevantes'], ensure_ascii=False),
        ))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_historial(limit=100):
    conn = _conectar()
    try:
        asegurar_tabla_detecciones(conn)
        filas = conn.execute('''
            SELECT id, registro_id, motor_id, tiempo, fecha, hora,
                   error_reconstruccion, umbral, severidad,
                   tipo_interpretacion, descripcion, variables_relevantes
            FROM detecciones_anomalias
            ORDER BY tiempo DESC, id DESC
            LIMIT ?
        ''', (max(0, int(limit)),)).fetchall()
    finally:
        conn.close()

    historial = []
    for fila in filas:
        try:
            variables = json.loads(fila[11])
        except (TypeError, json.JSONDecodeError):
            variables = []
        historial.append({
            'id': fila[0],
            'registro_id': fila[1],
            'motor_id': fila[2],
            'tiempo': fila[3],
            'fecha': fila[4],
            'hora': fila[5],
            'error_reconstruccion': fila[6],
            'umbral': fila[7],
            'severidad': fila[8],
            'tipo_interpretacion': fila[9],
            'descripcion': fila[10],
            'variables_relevantes': variables,
        })
    return historial


def obtener_estadisticas():
    conn = _conectar()
    try:
        asegurar_tabla_detecciones(conn)
        total = conn.execute(
            'SELECT COUNT(*) FROM detecciones_anomalias'
        ).fetchone()[0]
        filas = conn.execute(
            'SELECT severidad, COUNT(*) FROM detecciones_anomalias GROUP BY severidad'
        ).fetchall()
    finally:
        conn.close()
    return {'total': total, 'por_severidad': {fila[0]: fila[1] for fila in filas}}

