import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.app import app


class TestDashboardAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch('dashboard.app.obtener_dashboard')
    def test_api_dashboard_devuelve_json(self, obtener_dashboard):
        obtener_dashboard.return_value = {
            'estadisticas': {'total_registros': 2, 'total_detecciones': 1},
            'historial': [],
            'motores': ['M-01'],
        }
        response = self.client.get('/api/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['motores'], ['M-01'])

    @patch('dashboard.app.ejecutar_inferencia_y_guardar')
    def test_api_inferir_devuelve_cantidad_guardada(self, ejecutar):
        ejecutar.return_value = 3
        response = self.client.post('/api/inferir')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'ok': True, 'detecciones_guardadas': 3})

    @patch('dashboard.app.obtener_dashboard')
    def test_api_dashboard_informa_error_con_http_500(self, obtener_dashboard):
        obtener_dashboard.side_effect = RuntimeError('base no disponible')
        response = self.client.get('/api/dashboard')
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()['ok'])


if __name__ == '__main__':
    unittest.main()
