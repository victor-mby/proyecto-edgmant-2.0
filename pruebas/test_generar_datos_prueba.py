import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'base_datos'))

import crear_base_datos
import generar_datos_prueba
from generar_datos_prueba import limpiar_datos_anteriores


class TestLimpiarDatosPrueba(unittest.TestCase):
    def test_limpia_registros_y_claves_idempotentes_antiguas(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta_db = Path(directorio) / 'prueba.db'
            conn = sqlite3.connect(ruta_db)
            try:
                conn.executescript("""
                    PRAGMA foreign_keys = ON;
                    CREATE TABLE estaciones (id TEXT PRIMARY KEY);
                    CREATE TABLE motores (
                        id TEXT PRIMARY KEY,
                        estacion_id TEXT NOT NULL REFERENCES estaciones(id)
                    );
                    CREATE TABLE registros_telemetria (
                        id INTEGER PRIMARY KEY,
                        motor_id TEXT NOT NULL REFERENCES motores(id)
                    );
                    CREATE TABLE eventos (id INTEGER PRIMARY KEY);
                    CREATE TABLE alarmas (id INTEGER PRIMARY KEY);
                    CREATE TABLE ingestas_csv (
                        clave_origen TEXT PRIMARY KEY,
                        registro_id INTEGER NOT NULL REFERENCES registros_telemetria(id)
                    );
                    CREATE TABLE ingestas_simulador (
                        clave_origen TEXT PRIMARY KEY,
                        registro_id INTEGER NOT NULL REFERENCES registros_telemetria(id)
                    );
                    CREATE TABLE detecciones_anomalias (
                        id INTEGER PRIMARY KEY,
                        registro_id INTEGER
                    );
                    INSERT INTO estaciones VALUES ('EB-01');
                    INSERT INTO motores VALUES ('M-01', 'EB-01');
                    INSERT INTO registros_telemetria VALUES (1, 'M-01');
                    INSERT INTO eventos VALUES (1);
                    INSERT INTO alarmas VALUES (1);
                    INSERT INTO ingestas_csv VALUES ('csv-1', 1);
                    INSERT INTO ingestas_simulador VALUES ('sim-1', 1);
                    INSERT INTO detecciones_anomalias VALUES (1, 1);
                """)

                limpiar_datos_anteriores(conn)

                for tabla in (
                    'ingestas_csv', 'ingestas_simulador',
                    'detecciones_anomalias', 'registros_telemetria',
                    'eventos', 'alarmas', 'motores', 'estaciones',
                ):
                    cantidad = conn.execute(
                        f'SELECT COUNT(*) FROM "{tabla}"'
                    ).fetchone()[0]
                    self.assertEqual(cantidad, 0, tabla)
            finally:
                conn.close()

    def test_generador_usa_tiempo_transcurrido_y_potencia_en_kw(self):
        with tempfile.TemporaryDirectory() as directorio:
            db_path = str(Path(directorio) / 'edgemant.db')
            db_original = crear_base_datos.DB_PATH
            generar_original = generar_datos_prueba.DB_PATH
            try:
                crear_base_datos.DB_PATH = db_path
                generar_datos_prueba.DB_PATH = db_path
                crear_base_datos.crear_base_datos(reiniciar=True)
                generar_datos_prueba.generar_datos_prueba()

                conn = sqlite3.connect(db_path)
                try:
                    fila = conn.execute(
                        'SELECT tiempo, tiempo_simulacion, caudal, potencia, carga, '
                        'caudal_total, potencia_total, amperaje, corriente_total '
                        'FROM registros_telemetria ORDER BY id LIMIT 1'
                    ).fetchone()
                finally:
                    conn.close()

                self.assertEqual(fila[0], 0.0)
                self.assertEqual(fila[1], '00:00:00')
                self.assertGreater(fila[2], 0)
                self.assertGreater(fila[3], 0)
                self.assertLess(fila[3], 10)  # kW, no miles de veces mayor por unidades.
                self.assertGreater(fila[4], 0)
                self.assertLess(fila[4], 100)
                self.assertGreater(fila[5], fila[2])
                self.assertGreater(fila[6], fila[3])
                self.assertGreater(fila[8], fila[7])
            finally:
                crear_base_datos.DB_PATH = db_original
                generar_datos_prueba.DB_PATH = generar_original

    def test_no_borra_datos_existentes_sin_confirmacion(self):
        with tempfile.TemporaryDirectory() as directorio:
            db_path = str(Path(directorio) / 'edgemant.db')
            db_original = crear_base_datos.DB_PATH
            generar_original = generar_datos_prueba.DB_PATH
            try:
                crear_base_datos.DB_PATH = db_path
                generar_datos_prueba.DB_PATH = db_path
                crear_base_datos.crear_base_datos(reiniciar=True)

                conn = sqlite3.connect(db_path)
                try:
                    conn.execute(
                        'INSERT INTO estaciones (id, nombre) VALUES (?, ?)',
                        ('ESTACION-REAL', 'No borrar'),
                    )
                    conn.commit()
                finally:
                    conn.close()

                with self.assertRaisesRegex(RuntimeError, 'No se modificó nada'):
                    generar_datos_prueba.generar_datos_prueba()

                conn = sqlite3.connect(db_path)
                try:
                    filas = conn.execute(
                        'SELECT id, nombre FROM estaciones'
                    ).fetchall()
                finally:
                    conn.close()
                self.assertEqual(filas, [('ESTACION-REAL', 'No borrar')])
            finally:
                crear_base_datos.DB_PATH = db_original
                generar_datos_prueba.DB_PATH = generar_original


if __name__ == '__main__':
    unittest.main()
