"""Receptor local de telemetría para EdgeMant.

Valida y guarda las capturas usando la biblioteca estándar. Tras confirmar
la escritura, puede invocar de forma diferida al procesador ML de EdgeMant.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DB_PATH = ROOT_DIR / "base_datos" / "edgemant.db"
SCHEMA_PATH = ROOT_DIR / "base_datos" / "base_datos.sql"
VIEW_PATH = ROOT_DIR / "base_datos" / "view_ml.sql"

HOST = "127.0.0.1"
PORT = int(os.environ.get("EDGEMANT_INGESTA_PORT", "8765"))

ALLOWED_ORIGINS = {
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:8081",
    "http://localhost:8081",
}

MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_BATCH_SIZE = 500
AUTO_PROCESAR_ML = os.environ.get("EDGEMANT_AUTO_INFERENCIA", "1").strip().lower() not in {"0", "false", "no", "off"}


NUMERIC_FIELDS = (
    "tiempo",
    "timestamp",
    "nivel",
    "nivel_porcentaje",
    "voltaje",
    "voltaje_terminal",
    "amperaje",
    "corriente_nominal",
    "caudal",
    "potencia",
    "potencia_nominal",
    "carga",
    "altura",
    "factor_potencia",
    "posicion_valvula",
    "velocidad_rotacion",
    "horas_operacion",
    "caudal_total",
    "potencia_total",
    "corriente_total",
    "nivel_destino",
    "demanda",
    "nivel_tanque_maximo",
)

STRING_FIELDS = (
    "tiempo_simulacion",
    "fecha",
    "hora",
    "motor_id",
    "estado_motor",
    "estado_valvula",
)


def connect_db() -> sqlite3.Connection:
    """Abre una conexión con la base de datos SQLite."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


@contextmanager
def database_connection():
    """Gestiona la transacción y cierra siempre la conexión SQLite."""
    conn = connect_db()

    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize_db() -> None:
    """Crea el esquema si falta, sin borrar una base ya existente."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el esquema: {SCHEMA_PATH}"
        )

    with database_connection() as conn:
        conn.executescript(
            SCHEMA_PATH.read_text(encoding="utf-8")
        )

        if VIEW_PATH.exists():
            conn.executescript(
                VIEW_PATH.read_text(encoding="utf-8")
            )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingestas_simulador (
                clave_origen TEXT PRIMARY KEY,
                registro_id INTEGER NOT NULL,
                recibido_en TEXT NOT NULL,
                FOREIGN KEY (registro_id)
                    REFERENCES registros_telemetria(id)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ingestas_recibido
            ON ingestas_simulador(recibido_en)
        """)


def normalize_record(item: Any) -> dict[str, Any]:
    """Valida y normaliza una muestra recibida del simulador."""
    if not isinstance(item, dict):
        raise ValueError(
            "Cada muestra debe ser un objeto JSON."
        )

    missing = [
        field
        for field in (*NUMERIC_FIELDS, *STRING_FIELDS)
        if field not in item
    ]

    if missing:
        raise ValueError(
            "Faltan campos: " + ", ".join(missing)
        )

    record: dict[str, Any] = {}

    for field in NUMERIC_FIELDS:
        try:
            value = float(item[field])
        except (TypeError, ValueError):
            raise ValueError(
                f"El campo {field} debe ser numérico."
            ) from None

        if not (value == value and abs(value) != float("inf")):
            raise ValueError(
                f"El campo {field} debe ser finito."
            )

        record[field] = value

    for field in STRING_FIELDS:
        value = item[field]

        if value is None:
            raise ValueError(
                f"El campo {field} no puede ser nulo."
            )

        record[field] = str(value).strip()

    if not record["motor_id"]:
        raise ValueError(
            "motor_id no puede estar vacío."
        )

    record["timestamp"] = int(record["timestamp"])

    return record


def source_key(record: dict[str, Any]) -> str:
    """Genera una clave para identificar muestras repetidas."""
    return (
        f'{record["motor_id"]}|'
        f'{record["timestamp"]}|'
        f'{record["tiempo"]:.6f}'
    )


def insert_batch(items: list[Any]) -> dict[str, int]:
    """Valida e inserta un lote de muestras sin duplicarlas."""
    if not isinstance(items, list):
        raise ValueError(
            "El campo 'registros' debe ser una lista."
        )

    if len(items) > MAX_BATCH_SIZE:
        raise ValueError(
            f"Máximo {MAX_BATCH_SIZE} registros por lote."
        )

    valid = [normalize_record(item) for item in items]

    inserted = 0
    skipped = 0
    registros_insertados: list[int] = []

    received_at = datetime.now(timezone.utc).isoformat()

    with database_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO estaciones
                (id, nombre, linea, zona, operador)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "EB-01",
                "Estación de bombeo simulada",
                "Simulador EdgeMant",
                "Local",
                "EdgeMant",
            ),
        )

        for record in valid:
            key = source_key(record)

            exists = conn.execute(
                """
                SELECT 1
                FROM ingestas_simulador
                WHERE clave_origen = ?
                """,
                (key,),
            ).fetchone()

            if exists:
                skipped += 1
                continue

            motor_id = record["motor_id"]

            conn.execute(
                """
                INSERT OR IGNORE INTO motores
                    (id, estacion_id, descripcion)
                VALUES (?, ?, ?)
                """,
                (
                    motor_id,
                    "EB-01",
                    f"Motor del simulador {motor_id}",
                ),
            )

            cursor = conn.execute(
                """
                INSERT INTO registros_telemetria (
                    tiempo,
                    tiempo_simulacion,
                    timestamp,
                    fecha,
                    hora,
                    motor_id,
                    nivel,
                    nivel_porcentaje,
                    voltaje,
                    voltaje_terminal,
                    amperaje,
                    corriente_nominal,
                    caudal,
                    potencia,
                    potencia_nominal,
                    carga,
                    altura,
                    factor_potencia,
                    estado_motor,
                    estado_valvula,
                    posicion_valvula,
                    velocidad_rotacion,
                    horas_operacion,
                    caudal_total,
                    potencia_total,
                    corriente_total,
                    nivel_destino,
                    demanda,
                    nivel_tanque_maximo
                )
                VALUES (
                    :tiempo,
                    :tiempo_simulacion,
                    :timestamp,
                    :fecha,
                    :hora,
                    :motor_id,
                    :nivel,
                    :nivel_porcentaje,
                    :voltaje,
                    :voltaje_terminal,
                    :amperaje,
                    :corriente_nominal,
                    :caudal,
                    :potencia,
                    :potencia_nominal,
                    :carga,
                    :altura,
                    :factor_potencia,
                    :estado_motor,
                    :estado_valvula,
                    :posicion_valvula,
                    :velocidad_rotacion,
                    :horas_operacion,
                    :caudal_total,
                    :potencia_total,
                    :corriente_total,
                    :nivel_destino,
                    :demanda,
                    :nivel_tanque_maximo
                )
                """,
                record,
            )

            registro_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT OR IGNORE INTO evaluaciones_ml (registro_id, estado)
                VALUES (?, 'PENDIENTE')
                """,
                (registro_id,),
            )
            registros_insertados.append(registro_id)

            conn.execute(
                """
                INSERT INTO ingestas_simulador
                    (clave_origen, registro_id, recibido_en)
                VALUES (?, ?, ?)
                """,
                (
                    key,
                    registro_id,
                    received_at,
                ),
            )

            inserted += 1

    if registros_insertados and AUTO_PROCESAR_ML:
        try:
            from integracion.procesador_ml import procesar_pendientes

            resumen = procesar_pendientes(db_path=DB_PATH, limit=MAX_BATCH_SIZE)
            print(
                "[EdgeMant ML] Evaluados: {evaluados}; normales: {normales}; "
                "anomalías: {anomalias}; detecciones nuevas: {detecciones_guardadas}; "
                "pendientes: {pendientes}".format(**resumen)
            )
        except Exception as exc:
            # La captura permanece guardada en la cola si el modelo falla o falta.
            print(
                "[EdgeMant ML] La telemetría quedó guardada; la evaluación "
                f"permanece pendiente: {exc}"
            )

    return {
        "recibidos": len(items),
        "insertados": inserted,
        "duplicados": skipped,
    }


class IngestaHandler(BaseHTTPRequestHandler):
    server_version = "EdgeMantIngesta/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("[ingesta] " + (fmt % args))

    def send_json(
        self,
        status: int,
        payload: dict[str, Any],
    ) -> None:
        body = (
            b""
            if status == 204
            else json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8")
        )

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.send_header("Cache-Control", "no-store")

        origin = self.headers.get("Origin", "")

        if origin in ALLOWED_ORIGINS:
            self.send_header(
                "Access-Control-Allow-Origin",
                origin,
            )
            self.send_header("Vary", "Origin")
            self.send_header(
                "Access-Control-Allow-Methods",
                "GET, POST, OPTIONS",
            )
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type",
            )
            self.send_header(
                "Access-Control-Allow-Private-Network",
                "true",
            )

        self.end_headers()

        if status != 204:
            self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin", "")

        if origin not in ALLOWED_ORIGINS:
            self.send_json(
                403,
                {
                    "ok": False,
                    "error": "Origen no permitido.",
                },
            )
            return

        self.send_json(204, {})

    def do_GET(self) -> None:
        if self.path == "/api/salud":
            try:
                with database_connection() as conn:
                    count = conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM ingestas_simulador
                        """
                    ).fetchone()[0]
                    por_estado = {
                        fila[0]: int(fila[1])
                        for fila in conn.execute(
                            "SELECT estado, COUNT(*) FROM evaluaciones_ml GROUP BY estado"
                        ).fetchall()
                    }

                self.send_json(
                    200,
                    {
                        "ok": True,
                        "servicio": "EdgeMant",
                        "muestras_ingestadas": count,
                        "evaluaciones_ml": {
                            "pendientes": por_estado.get("PENDIENTE", 0),
                            "evaluadas": por_estado.get("EVALUADO", 0),
                            "errores": por_estado.get("ERROR", 0),
                        },
                    },
                )

            except Exception as exc:
                self.send_json(
                    500,
                    {
                        "ok": False,
                        "error": str(exc),
                    },
                )

            return

        self.send_json(
            404,
            {
                "ok": False,
                "error": "Ruta no encontrada.",
            },
        )

    def do_POST(self) -> None:
        if self.path != "/api/telemetria":
            self.send_json(
                404,
                {
                    "ok": False,
                    "error": "Ruta no encontrada.",
                },
            )
            return

        origin = self.headers.get("Origin", "")

        if origin and origin not in ALLOWED_ORIGINS:
            self.send_json(
                403,
                {
                    "ok": False,
                    "error": "Origen no permitido.",
                },
            )
            return

        try:
            length = int(
                self.headers.get("Content-Length", "0")
            )

            if length <= 0 or length > MAX_BODY_BYTES:
                self.send_json(
                    413,
                    {
                        "ok": False,
                        "error": "Tamaño de solicitud inválido.",
                    },
                )
                return

            payload = json.loads(
                self.rfile.read(length).decode("utf-8")
            )

            if (
                not isinstance(payload, dict)
                or "registros" not in payload
            ):
                raise ValueError(
                    "Se esperaba un objeto JSON con 'registros'."
                )

            result = insert_batch(payload["registros"])

            self.send_json(
                200,
                {
                    "ok": True,
                    **result,
                },
            )

        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(
                400,
                {
                    "ok": False,
                    "error": (
                        "El cuerpo no contiene JSON UTF-8 válido."
                    ),
                },
            )

        except ValueError as exc:
            self.send_json(
                400,
                {
                    "ok": False,
                    "error": str(exc),
                },
            )

        except Exception as exc:
            self.send_json(
                500,
                {
                    "ok": False,
                    "error": f"Error interno de ingesta: {exc}",
                },
            )

    def do_PUT(self) -> None:
        self.send_json(
            405,
            {
                "ok": False,
                "error": "Método no permitido.",
            },
        )

    def do_DELETE(self) -> None:
        self.send_json(
            405,
            {
                "ok": False,
                "error": "Método no permitido.",
            },
        )


def main() -> None:
    initialize_db()

    server = ThreadingHTTPServer(
        (HOST, PORT),
        IngestaHandler,
    )

    print(
        "EdgeMant: receptor local iniciado en "
        f"http://{HOST}:{PORT}"
    )
    print(f"Base de datos: {DB_PATH}")
    print("Pulsa Ctrl+C para detener el receptor.")

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\nReceptor detenido.")

    finally:
        server.server_close()


if __name__ == "__main__":
    main()
