import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dashboard' / 'servicios'))

import servicio_historial


class TestServicioHistorial(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_original = servicio_historial.DB_PATH
        servicio_historial.DB_PATH = os.path.join(self.tempdir.name, 'historial.db')

    def tearDown(self):
        servicio_historial.DB_PATH = self.db_original
        self.tempdir.cleanup()

    def test_no_guarda_dos_veces_el_mismo_registro(self):
        deteccion = {
            'id': 45,
            'motor_id': 'M-01',
            'tiempo': 10.0,
            'fecha': '18/10/2026',
            'hora': '10:00:10',
            'error_reconstruccion': 0.8,
            'umbral': 0.3,
            'severidad': 'CRITICO',
            'tipo_interpretacion': 'Posible comportamiento eléctrico anormal',
            'descripcion': 'Revisar alimentación y corriente.',
            'variables_relevantes': ['voltaje', 'amperaje'],
        }
        self.assertTrue(servicio_historial.guardar_deteccion(deteccion))
        self.assertFalse(servicio_historial.guardar_deteccion(deteccion))
        self.assertEqual(len(servicio_historial.obtener_historial()), 1)
        self.assertEqual(servicio_historial.obtener_estadisticas()['total'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
