import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))

from detectar_anomalias import calcular_umbral, detectar


class TestDeteccionAnomalias(unittest.TestCase):
    def test_calcula_umbral_valido(self):
        self.assertEqual(calcular_umbral([0.0, 1.0, 2.0, 3.0], 50), 1.5)

    def test_rechaza_errores_vacios(self):
        with self.assertRaisesRegex(ValueError, 'no vacía'):
            calcular_umbral([])

    def test_rechaza_errores_no_finitos(self):
        with self.assertRaisesRegex(ValueError, 'finitos'):
            calcular_umbral([0.1, np.nan, 0.3])

    def test_rechaza_percentil_fuera_de_rango(self):
        with self.assertRaisesRegex(ValueError, 'percentil'):
            calcular_umbral([0.1, 0.2], 100)

    def test_detecta_y_alinea_registros(self):
        df = detectar(pd.DataFrame({'id': [10, 11, 12]}), [0.1, 0.5, 0.2], 0.3)
        self.assertEqual(df['anomalia'].tolist(), [0, 1, 0])
        self.assertEqual(df['error_reconstruccion'].tolist(), [0.1, 0.5, 0.2])

    def test_rechaza_cantidad_de_errores_incorrecta(self):
        with self.assertRaisesRegex(ValueError, 'exactamente un error'):
            detectar(pd.DataFrame({'id': [1, 2]}), [0.1], 0.2)

    def test_rechaza_umbral_invalido(self):
        with self.assertRaisesRegex(ValueError, 'umbral'):
            detectar(pd.DataFrame({'id': [1]}), [0.1], np.nan)


if __name__ == '__main__':
    unittest.main()
