import sqlite3
import tempfile
import unittest
from pathlib import Path

from integracion import procesador_ml


ROOT_DIR = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT_DIR / "base_datos" / "base_datos.sql"
VIEW_PATH = ROOT_DIR / "base_datos" / "view_ml.sql"


class TestProcesadorML(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "edgemant.db"

        # El gestor de contexto de sqlite3 confirma o revierte transacciones,
        # pero no cierra la conexión; se cierra explícitamente para Windows.
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.executescript(VIEW_PATH.read_text(encoding="utf-8"))
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_sin_pendientes_no_carga_ni_ejecuta_modelo(self):
        resultado = procesador_ml.procesar_pendientes(
            db_path=self.db_path,
            limit=25,
        )

        self.assertEqual(
            resultado,
            {
                "evaluados": 0,
                "normales": 0,
                "anomalias": 0,
                "detecciones_guardadas": 0,
                "pendientes": 0,
                "no_aplican": 0,
            },
        )

    def test_estado_ml_informa_colas_vacias(self):
        resultado = procesador_ml.obtener_estado_ml(self.db_path)

        self.assertEqual(
            resultado,
            {
                "evaluados": 0,
                "pendientes": 0,
                "errores": 0,
                "no_aplican": 0,
                "detecciones": 0,
                "detecciones_revision": 0,
            },
        )

    def test_motor_parado_pendiente_no_carga_el_modelo(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO estaciones (id, nombre) VALUES ('EB-01', 'Estación de prueba')"
            )
            conn.execute(
                "INSERT INTO motores (id, estacion_id, descripcion) VALUES ('M-01', 'EB-01', 'Bomba')"
            )
            cursor = conn.execute("""
                INSERT INTO registros_telemetria (
                    tiempo, timestamp, motor_id, nivel, nivel_porcentaje, voltaje,
                    amperaje, caudal, potencia, estado_motor, estado_valvula,
                    caudal_total, potencia_total, nivel_destino, demanda
                ) VALUES (1, 1000, 'M-01', 4.2, 52.5, 220, 0.1, 0, 0,
                          'PARADO', 'CERRADA', 0, 0, 3.4, 35)
            """)
            conn.execute(
                "INSERT INTO evaluaciones_ml (registro_id, estado) VALUES (?, 'PENDIENTE')",
                (int(cursor.lastrowid),),
            )
            conn.commit()
        finally:
            conn.close()

        resultado = procesador_ml.procesar_pendientes(db_path=self.db_path)

        self.assertEqual(resultado["evaluados"], 0)
        self.assertEqual(resultado["no_aplican"], 1)
        self.assertEqual(resultado["pendientes"], 0)
        conn = sqlite3.connect(self.db_path)
        try:
            estado = conn.execute(
                "SELECT estado, anomalia FROM evaluaciones_ml"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(estado, ("NO_APLICA", None))

    def test_motor_parado_pasa_a_no_aplica_y_conserva_el_historial(self):
        # Recrea la estructura antigua de la cola para verificar la migración.
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DROP TABLE evaluaciones_ml")
            conn.execute("""
                CREATE TABLE evaluaciones_ml (
                    registro_id INTEGER PRIMARY KEY,
                    estado TEXT NOT NULL DEFAULT 'PENDIENTE'
                        CHECK (estado IN ('PENDIENTE', 'EVALUADO', 'ERROR')),
                    error_reconstruccion REAL,
                    umbral REAL,
                    anomalia INTEGER CHECK (anomalia IS NULL OR anomalia IN (0, 1)),
                    modelo_version TEXT,
                    evaluado_en TEXT,
                    detalle_error TEXT,
                    FOREIGN KEY (registro_id) REFERENCES registros_telemetria(id)
                )
            """)
            conn.execute(
                "INSERT INTO estaciones (id, nombre) VALUES ('EB-01', 'Estación de prueba')"
            )
            conn.execute(
                "INSERT INTO motores (id, estacion_id, descripcion) VALUES ('M-01', 'EB-01', 'Bomba')"
            )
            cursor = conn.execute("""
                INSERT INTO registros_telemetria (
                    tiempo, timestamp, motor_id, nivel, nivel_porcentaje, voltaje,
                    amperaje, caudal, potencia, estado_motor, estado_valvula,
                    caudal_total, potencia_total, nivel_destino, demanda
                ) VALUES (1, 1000, 'M-01', 4.2, 52.5, 220, 0.1, 0, 0,
                          'PARADO', 'CERRADA', 0, 0, 3.4, 35)
            """)
            registro_id = int(cursor.lastrowid)
            conn.execute("""
                INSERT INTO evaluaciones_ml (
                    registro_id, estado, error_reconstruccion, umbral, anomalia,
                    modelo_version, detalle_error
                ) VALUES (?, 'EVALUADO', 608.9, 0.366954, 1, 'anterior', NULL)
            """, (registro_id,))
            conn.commit()
        finally:
            conn.close()

        from dashboard.servicios.servicio_historial import guardar_deteccion

        guardado = guardar_deteccion({
            "id": registro_id,
            "motor_id": "M-01",
            "tiempo": 1.0,
            "fecha": "22/10/2026",
            "hora": "21:12:59",
            "error_reconstruccion": 608.9,
            "umbral": 0.366954,
            "severidad": "CRITICO",
            "tipo_interpretacion": "Comportamiento operativo fuera del patron normal",
            "descripcion": "Resultado anterior para revisión",
            "variables_relevantes": ["velocidad_rotacion"],
        }, db_path=self.db_path)
        self.assertTrue(guardado)

        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                procesador_ml.preparar_evaluaciones_por_estado_operativo(conn)
            evaluacion = conn.execute(
                "SELECT estado, anomalia FROM evaluaciones_ml WHERE registro_id = ?",
                (registro_id,),
            ).fetchone()
            revision = conn.execute(
                "SELECT estado_revision FROM detecciones_anomalias WHERE registro_id = ?",
                (registro_id,),
            ).fetchone()
            total_registros = conn.execute(
                "SELECT COUNT(*) FROM registros_telemetria"
            ).fetchone()[0]
            total_detecciones = conn.execute(
                "SELECT COUNT(*) FROM detecciones_anomalias"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(evaluacion, ("NO_APLICA", None))
        self.assertEqual(revision, ("PENDIENTE_REVISION",))
        self.assertEqual(total_registros, 1)
        self.assertEqual(total_detecciones, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
