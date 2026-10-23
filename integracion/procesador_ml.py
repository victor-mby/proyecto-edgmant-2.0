"""Evaluación post-captura de telemetría con el modelo de EdgeMant.

El simulador solo transporta muestras. Este módulo se ejecuta desde el receptor
de EdgeMant una vez confirmada la escritura de la telemetría en SQLite.
"""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "base_datos" / "edgemant.db"
RUTA_MODELOS = ROOT_DIR / "ml" / "modelos"


def _conectar(db_path: str | Path | None = None) -> sqlite3.Connection:
    ruta = Path(db_path) if db_path is not None else DB_PATH
    conn = sqlite3.connect(str(ruta), timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


@contextmanager
def _sesion(db_path: str | Path | None = None):
    """Garantiza cierre de conexión y commit/rollback en cada operación."""
    conn = _conectar(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def asegurar_tabla_evaluaciones(conn: sqlite3.Connection) -> None:
    """Asegura la cola y migra su CHECK antiguo sin perder evaluaciones existentes."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluaciones_ml (
            registro_id INTEGER PRIMARY KEY,
            estado TEXT NOT NULL DEFAULT 'PENDIENTE'
                CHECK (estado IN ('PENDIENTE', 'EVALUADO', 'ERROR', 'NO_APLICA')),
            error_reconstruccion REAL,
            umbral REAL,
            anomalia INTEGER CHECK (anomalia IS NULL OR anomalia IN (0, 1)),
            modelo_version TEXT,
            evaluado_en TEXT,
            detalle_error TEXT,
            FOREIGN KEY (registro_id) REFERENCES registros_telemetria(id)
        )
        """
    )
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'evaluaciones_ml'"
    ).fetchone()
    if ddl and "NO_APLICA" not in str(ddl[0]).upper():
        # Las bases existentes tenían un CHECK que no admitía NO_APLICA.
        # La migración copia todas las filas antes de sustituir solo la estructura.
        conn.execute("DROP INDEX IF EXISTS idx_evaluaciones_estado")
        conn.execute("DROP TABLE IF EXISTS evaluaciones_ml_migracion")
        conn.execute(
            """
            CREATE TABLE evaluaciones_ml_migracion (
                registro_id INTEGER PRIMARY KEY,
                estado TEXT NOT NULL DEFAULT 'PENDIENTE'
                    CHECK (estado IN ('PENDIENTE', 'EVALUADO', 'ERROR', 'NO_APLICA')),
                error_reconstruccion REAL,
                umbral REAL,
                anomalia INTEGER CHECK (anomalia IS NULL OR anomalia IN (0, 1)),
                modelo_version TEXT,
                evaluado_en TEXT,
                detalle_error TEXT,
                FOREIGN KEY (registro_id) REFERENCES registros_telemetria(id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO evaluaciones_ml_migracion (
                registro_id, estado, error_reconstruccion, umbral, anomalia,
                modelo_version, evaluado_en, detalle_error
            )
            SELECT registro_id, estado, error_reconstruccion, umbral, anomalia,
                   modelo_version, evaluado_en, detalle_error
            FROM evaluaciones_ml
            """
        )
        conn.execute("DROP TABLE evaluaciones_ml")
        conn.execute(
            "ALTER TABLE evaluaciones_ml_migracion RENAME TO evaluaciones_ml"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_evaluaciones_estado "
        "ON evaluaciones_ml(estado, registro_id)"
    )


def preparar_evaluaciones_por_estado_operativo(conn: sqlite3.Connection) -> int:
    """Omite ML fuera del régimen OPERATIVO y conserva predicciones antiguas para auditoría."""
    asegurar_tabla_evaluaciones(conn)
    from dashboard.servicios.servicio_historial import (
        asegurar_tabla_detecciones,
        marcar_detecciones_no_vigentes_por_estado_motor,
    )

    asegurar_tabla_detecciones(conn)
    ahora = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """
        UPDATE evaluaciones_ml
        SET estado = 'NO_APLICA',
            anomalia = NULL,
            evaluado_en = COALESCE(evaluado_en, ?),
            detalle_error = (
                SELECT 'No se aplicó el Autoencoder: el régimen requerido es OPERATIVO; '
                       || 'estado registrado: '
                       || COALESCE(NULLIF(TRIM(r.estado_motor), ''), 'SIN DATO')
                       || '. Se conserva la telemetría y no se infiere una avería ML.'
                FROM registros_telemetria AS r
                WHERE r.id = evaluaciones_ml.registro_id
            )
        WHERE estado <> 'NO_APLICA'
          AND EXISTS (
              SELECT 1
              FROM registros_telemetria AS r
              WHERE r.id = evaluaciones_ml.registro_id
                AND UPPER(TRIM(COALESCE(r.estado_motor, ''))) <> 'OPERATIVO'
          )
        """
    )
    marcar_detecciones_no_vigentes_por_estado_motor(conn)
    return int(cursor.rowcount)


def _version_modelo() -> str:
    """Huella de los artefactos utilizados para que cada evaluación sea rastreable."""
    digest = hashlib.sha256()
    for nombre in ("autoencoder.pth", "columnas.json", "scaler.json", "umbral.txt"):
        ruta = RUTA_MODELOS / nombre
        if not ruta.is_file():
            raise FileNotFoundError("Falta el artefacto del modelo: " + str(ruta))
        digest.update(nombre.encode("utf-8"))
        digest.update(ruta.read_bytes())
    return digest.hexdigest()[:16]


def procesar_pendientes(
    db_path: str | Path | None = None,
    limit: int = 500,
) -> dict[str, int]:
    """Evalúa únicamente capturas encoladas y guarda resultados de forma idempotente."""
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("limit debe ser un entero positivo.")

    ruta_db = Path(db_path) if db_path is not None else DB_PATH

    with _sesion(ruta_db) as conn:
        preparar_evaluaciones_por_estado_operativo(conn)
        ids = [
            int(row[0])
            for row in conn.execute(
                """
                SELECT e.registro_id
                FROM evaluaciones_ml AS e
                JOIN registros_telemetria AS r ON r.id = e.registro_id
                WHERE e.estado = 'PENDIENTE'
                  AND UPPER(TRIM(COALESCE(r.estado_motor, ''))) = 'OPERATIVO'
                ORDER BY e.registro_id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]

    if not ids:
        estado = obtener_estado_ml(ruta_db)
        return {
            "evaluados": 0,
            "normales": 0,
            "anomalias": 0,
            "detecciones_guardadas": 0,
            "pendientes": estado["pendientes"],
            "no_aplican": estado["no_aplican"],
        }

    # Importaciones diferidas: la ingesta y la persistencia siguen funcionando
    # incluso si el entorno de ML no está instalado o el modelo necesita revisión.
    from ml.inferir import cargar_modelo, inferir
    from ml.interpretar import interpretar_fila
    from dashboard.servicios.servicio_historial import guardar_deteccion

    bundle = cargar_modelo()
    _, scaler, columnas, umbral = bundle
    version = _version_modelo()
    resultados, _ = inferir(
        registro_ids=ids,
        db_path=ruta_db,
        modelo_cargado=bundle,
    )

    ahora = datetime.now(timezone.utc).isoformat()
    ids_evaluados: set[int] = set()
    normales = 0
    anomalias = 0
    detecciones_guardadas = 0

    for _, fila in resultados.iterrows():
        registro_id = int(fila["id"])
        ids_evaluados.add(registro_id)
        es_anomalia = int(fila["anomalia"]) == 1

        if es_anomalia:
            interpretacion = interpretar_fila(fila, columnas, scaler, umbral)
            deteccion = {
                "id": registro_id,
                "motor_id": str(fila.get("motor_id", "")),
                "tiempo": float(fila["tiempo"]),
                "fecha": str(fila.get("fecha", "") or ""),
                "hora": str(fila.get("hora", "") or ""),
                "error_reconstruccion": float(fila["error_reconstruccion"]),
                "umbral": float(umbral),
                "severidad": interpretacion["severidad"],
                "tipo_interpretacion": interpretacion["tipo_interpretacion"],
                "descripcion": interpretacion["descripcion"],
                "variables_relevantes": interpretacion["variables_relevantes"],
            }
            if guardar_deteccion(deteccion, db_path=ruta_db):
                detecciones_guardadas += 1
            anomalias += 1
        else:
            normales += 1

        with _sesion(ruta_db) as conn:
            conn.execute(
                """
                UPDATE evaluaciones_ml
                SET estado = 'EVALUADO',
                    error_reconstruccion = ?,
                    umbral = ?,
                    anomalia = ?,
                    modelo_version = ?,
                    evaluado_en = ?,
                    detalle_error = NULL
                WHERE registro_id = ? AND estado = 'PENDIENTE'
                """,
                (
                    float(fila["error_reconstruccion"]),
                    float(umbral),
                    int(es_anomalia),
                    version,
                    ahora,
                    registro_id,
                ),
            )

    # Si una muestra no tiene las variables numéricas completas del modelo,
    # se deja identificada como error en vez de volver a procesarla infinitamente.
    omitidos = set(ids) - ids_evaluados
    for registro_id in omitidos:
        with _sesion(ruta_db) as conn:
            conn.execute(
                """
                UPDATE evaluaciones_ml
                SET estado = 'ERROR',
                    evaluado_en = ?,
                    detalle_error = ?
                WHERE registro_id = ? AND estado = 'PENDIENTE'
                """,
                (
                    ahora,
                    "La muestra no contiene todas las variables numéricas válidas del modelo.",
                    registro_id,
                ),
            )

    estado = obtener_estado_ml(ruta_db)
    return {
        "evaluados": len(ids_evaluados),
        "normales": normales,
        "anomalias": anomalias,
        "detecciones_guardadas": detecciones_guardadas,
        "pendientes": estado["pendientes"],
        "no_aplican": estado["no_aplican"],
    }


def obtener_estado_ml(db_path: str | Path | None = None) -> dict[str, int]:
    """Devuelve contadores de cola sin ejecutar inferencia ni modificar muestras."""
    ruta_db = Path(db_path) if db_path is not None else DB_PATH
    with _sesion(ruta_db) as conn:
        preparar_evaluaciones_por_estado_operativo(conn)
        filas = {
            str(row[0]): int(row[1])
            for row in conn.execute(
                "SELECT estado, COUNT(*) FROM evaluaciones_ml GROUP BY estado"
            ).fetchall()
        }
        detecciones = int(
            conn.execute(
                "SELECT COUNT(*) FROM detecciones_anomalias WHERE estado_revision = 'VIGENTE'"
            ).fetchone()[0]
        )
        detecciones_revision = int(
            conn.execute(
                "SELECT COUNT(*) FROM detecciones_anomalias WHERE estado_revision = 'PENDIENTE_REVISION'"
            ).fetchone()[0]
        )
    return {
        "evaluados": filas.get("EVALUADO", 0),
        "pendientes": filas.get("PENDIENTE", 0),
        "errores": filas.get("ERROR", 0),
        "no_aplican": filas.get("NO_APLICA", 0),
        "detecciones": detecciones,
        "detecciones_revision": detecciones_revision,
    }
