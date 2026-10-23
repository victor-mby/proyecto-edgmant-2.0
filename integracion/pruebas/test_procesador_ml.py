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

        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.executescript(VIEW_PATH.read_text(encoding="utf-8"))

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
                "detecciones": 0,
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
