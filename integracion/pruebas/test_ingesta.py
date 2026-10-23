import sys
import tempfile
import unittest
from pathlib import Path

INTEGRACION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INTEGRACION_DIR))

import servidor_ingesta as ingesta


def muestra():
    return {
        "tiempo": 10.0,
        "tiempo_simulacion": "00:00:10",
        "timestamp": 1_800_000_000_000,
        "fecha": "16/10/2026",
        "hora": "12:00:10",
        "motor_id": "M-01",
        "nivel": 3.2,
        "nivel_porcentaje": 64.0,
        "voltaje": 220.0,
        "voltaje_terminal": 218.0,
        "amperaje": 5.1,
        "corriente_nominal": 5.0,
        "caudal": 12.5,
        "potencia": 1.8,
        "potencia_nominal": 2.2,
        "carga": 82.0,
        "altura": 14.0,
        "factor_potencia": 0.91,
        "estado_motor": "MARCHA",
        "estado_valvula": "ABIERTA",
        "posicion_valvula": 100.0,
        "velocidad_rotacion": 98.0,
        "horas_operacion": 120.0,
        "caudal_total": 12.5,
        "potencia_total": 1.8,
        "corriente_total": 5.1,
        "nivel_destino": 4.2,
        "demanda": 11.0,
        "nivel_tanque_maximo": 5.0,
    }


class TestIngesta(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)

        proyecto_dir = Path(__file__).resolve().parents[2]
        base_datos_dir = proyecto_dir / "base_datos"

        self.configuracion_original = (
            ingesta.DB_PATH,
            ingesta.SCHEMA_PATH,
            ingesta.VIEW_PATH,
            ingesta.AUTO_PROCESAR_ML,
        )
        ingesta.DB_PATH = root / "edgemant.db"
        ingesta.SCHEMA_PATH = base_datos_dir / "base_datos.sql"
        ingesta.VIEW_PATH = base_datos_dir / "view_ml.sql"
        ingesta.AUTO_PROCESAR_ML = False

        ingesta.initialize_db()

    def tearDown(self):
        (
            ingesta.DB_PATH,
            ingesta.SCHEMA_PATH,
            ingesta.VIEW_PATH,
            ingesta.AUTO_PROCESAR_ML,
        ) = self.configuracion_original
        self.tempdir.cleanup()

    def test_inserta_29_campos(self):
        result = ingesta.insert_batch([muestra()])

        self.assertEqual(
            result,
            {
                "recibidos": 1,
                "insertados": 1,
                "duplicados": 0,
            },
        )

        with ingesta.database_connection() as conn:
            row = conn.execute(
                "SELECT * FROM registros_telemetria"
            ).fetchone()

            self.assertIsNotNone(row)
            self.assertEqual(row["motor_id"], "M-01")
            self.assertEqual(row["voltaje_terminal"], 218.0)
            self.assertEqual(row["factor_potencia"], 0.91)
            self.assertEqual(row["horas_operacion"], 120.0)

            evaluacion = conn.execute(
                "SELECT estado FROM evaluaciones_ml WHERE registro_id = ?",
                (row["id"],),
            ).fetchone()
            self.assertIsNotNone(evaluacion)
            self.assertEqual(evaluacion["estado"], "PENDIENTE")

    def test_reintento_no_duplica(self):
        record = muestra()

        first = ingesta.insert_batch([record])
        second = ingesta.insert_batch([record])

        self.assertEqual(first["insertados"], 1)
        self.assertEqual(second["insertados"], 0)
        self.assertEqual(second["duplicados"], 1)

        with ingesta.database_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM registros_telemetria"
            ).fetchone()[0]

            self.assertEqual(count, 1)

            evaluaciones = conn.execute(
                "SELECT COUNT(*) FROM evaluaciones_ml"
            ).fetchone()[0]
            self.assertEqual(evaluaciones, 1)

    def test_rechaza_campos_faltantes(self):
        bad = muestra()
        del bad["voltaje_terminal"]

        with self.assertRaisesRegex(ValueError, "voltaje_terminal"):
            ingesta.insert_batch([bad])


if __name__ == "__main__":
    unittest.main(verbosity=2)