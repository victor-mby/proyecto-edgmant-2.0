
import csv
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'base_datos'))

import importar_csv


CABECERAS = [
    'Fecha', 'Hora', 'Tiempo simulación', 'Motor', 'Nivel (m)', 'Nivel (%)',
    'Voltaje (V)', 'Amperaje (A)', 'Caudal (L/s)', 'Potencia (kW)',
    'Estado motor', 'Estado válvula', 'Caudal total (L/s)',
    'Potencia total (kW)', 'Nivel destino (m)', 'Demanda (L/s)',
]


class TestImportarCSV(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.db_original = importar_csv.DB_PATH
        self.addCleanup(setattr, importar_csv, 'DB_PATH', self.db_original)

        self.db_path = os.path.join(self.tempdir.name, 'edgemant.db')
        importar_csv.DB_PATH = self.db_path

        schema = (
            ROOT / 'base_datos' / 'base_datos.sql'
        ).read_text(encoding='utf-8')

        # Simula una base anterior, donde los campos ausentes del CSV
        # eran NOT NULL.
        campos_legacy = {
            'timestamp', 'voltaje_terminal', 'corriente_nominal',
            'potencia_nominal', 'carga', 'altura', 'factor_potencia',
            'posicion_valvula', 'velocidad_rotacion', 'horas_operacion',
            'corriente_total', 'nivel_tanque_maximo',
        }

        lineas = []
        for linea in schema.splitlines():
            partes = linea.strip().split()
            if (
                len(partes) >= 2
                and partes[0] in campos_legacy
                and 'NOT NULL' not in linea
            ):
                linea = linea.rstrip()
                if linea.endswith(','):
                    linea = linea[:-1] + ' NOT NULL,'
            lineas.append(linea)

        schema = '\n'.join(lineas)

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(schema)
            conn.executescript(
                (ROOT / 'base_datos' / 'view_ml.sql').read_text(
                    encoding='utf-8'
                )
            )

        self.csv_path = os.path.join(
            self.tempdir.name, 'muestras.csv'
        )

        with open(
            self.csv_path, 'w', encoding='utf-8-sig', newline=''
        ) as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow(CABECERAS)
            escritor.writerow([
                '18/10/2026', '10:00:10', '00:00:10', 'M-01',
                '4.2', '52.5', '220', '5.1', '12.5', '1.8',
                'OPERATIVO', 'ABIERTA', '12.5', '1.8', '3.4', '35',
            ])

    def test_importa_csv_actual_con_campos_ausentes_y_reintento_idempotente(self):
        importar_csv.importar_csv(self.csv_path)
        importar_csv.importar_csv(self.csv_path)

        with closing(sqlite3.connect(self.db_path)) as conn:
            filas = conn.execute(
                'SELECT tiempo, timestamp, voltaje_terminal, nivel, motor_id '
                'FROM registros_telemetria'
            ).fetchall()

        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0][0], 10.0)
        self.assertIsNone(filas[0][1])
        self.assertIsNone(filas[0][2])
        self.assertEqual(filas[0][3], 4.2)
        self.assertEqual(filas[0][4], 'M-01')

    def test_migracion_conserva_ids_y_vista_sql(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                'INSERT INTO estaciones (id, nombre) VALUES (?, ?)',
                ('EB-01', 'Estación de prueba'),
            )
            conn.execute(
                'INSERT INTO motores (id, estacion_id, descripcion) '
                'VALUES (?, ?, ?)',
                ('M-OLD', 'EB-01', 'Motor anterior'),
            )

            registro = {
                campo: 1.0 for campo in importar_csv.COLUMNAS
            }
            registro.update({
                'tiempo': 1.0,
                'tiempo_simulacion': '00:00:01',
                'timestamp': 1800000000001,
                'fecha': '18/10/2026',
                'hora': '10:00:01',
                'motor_id': 'M-OLD',
                'estado_motor': 'OPERATIVO',
                'estado_valvula': 'ABIERTA',
            })

            columnas = ', '.join(importar_csv.COLUMNAS)
            parametros = ', '.join(
                ':' + campo for campo in importar_csv.COLUMNAS
            )
            cursor = conn.execute(
                f'INSERT INTO registros_telemetria ({columnas}) '
                f'VALUES ({parametros})',
                registro,
            )
            id_anterior = cursor.lastrowid
            conn.commit()

        importar_csv.importar_csv(self.csv_path)

        with closing(sqlite3.connect(self.db_path)) as conn:
            ids = [
                fila[0]
                for fila in conn.execute(
                    'SELECT id FROM registros_telemetria ORDER BY id'
                ).fetchall()
            ]
            total_vista = conn.execute(
                'SELECT COUNT(*) FROM vista_telemetria_ml'
            ).fetchone()[0]

        self.assertIn(id_anterior, ids)
        self.assertEqual(total_vista, 2)

    def test_rechaza_csv_sin_cabeceras_esenciales(self):
        with open(
            self.csv_path, 'w', encoding='utf-8', newline=''
        ) as archivo:
            archivo.write(
                'Fecha,Hora\n18/10/2026,10:00:10\n'
            )

        with self.assertRaisesRegex(
            ValueError, 'columnas básicas necesarias'
        ):
            importar_csv.importar_csv(self.csv_path)

    def test_rechaza_timestamp_no_entero(self):
        with self.assertRaisesRegex(
            ValueError, 'timestamp debe ser un entero'
        ):
            importar_csv._numero('1800000000000.5', 'timestamp')


if __name__ == '__main__':
    unittest.main(verbosity=2)
