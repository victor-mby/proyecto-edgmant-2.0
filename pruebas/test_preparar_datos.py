import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))

from preparar_datos import limpiar_datos, seleccionar_variables


class TestPrepararDatos(unittest.TestCase):
    def test_excluye_variables_totalmente_ausentes_sin_imputar_ceros(self):
        df = pd.DataFrame({
            'nivel': [1.0, 2.0, 3.0],
            'nivel_porcentaje': [10.0, 20.0, 30.0],
            'voltaje': [220.0, 221.0, 219.0],
            'amperaje': [5.0, 5.2, 4.9],
            'caudal': [12.0, np.nan, 11.5],
            'potencia': [1.1, 1.2, 1.0],
            'voltaje_terminal': [np.nan, np.nan, np.nan],
            'carga': [np.nan, np.nan, np.nan],
            'altura': [np.nan, np.nan, np.nan],
            'factor_potencia': [np.nan, np.nan, np.nan],
            'caudal_total': [12.0, 12.1, 11.7],
            'potencia_total': [1.1, 1.2, 1.0],
            'corriente_total': [np.nan, np.nan, np.nan],
            'nivel_destino': [3.0, 3.1, 2.9],
            'demanda': [30.0, 31.0, 29.0],
            'posicion_valvula': [np.nan, np.nan, np.nan],
            'velocidad_rotacion': [np.nan, np.nan, np.nan],
            'horas_operacion': [np.nan, np.nan, np.nan],
        })

        variables, columnas = seleccionar_variables(df)
        self.assertNotIn('voltaje_terminal', columnas)
        self.assertNotIn('carga', columnas)
        self.assertIn('voltaje', columnas)
        self.assertEqual(len(columnas), 10)

        limpias = limpiar_datos(variables)
        self.assertEqual(len(limpias), 2)
        self.assertEqual(limpias.index.tolist(), [0, 2])
        self.assertFalse(limpias.isna().any().any())

    def test_falla_si_no_hay_variables_con_datos(self):
        columnas = [
            'nivel', 'nivel_porcentaje', 'voltaje', 'voltaje_terminal',
            'amperaje', 'caudal', 'potencia', 'carga', 'altura',
            'factor_potencia', 'caudal_total', 'potencia_total',
            'corriente_total', 'nivel_destino', 'demanda',
            'posicion_valvula', 'velocidad_rotacion', 'horas_operacion',
        ]
        df = pd.DataFrame({columna: [np.nan, np.nan] for columna in columnas})
        with self.assertRaisesRegex(ValueError, 'al menos 3 variables'):
            seleccionar_variables(df)

    def test_rechaza_menos_de_tres_variables_utilizables(self):
        columnas = [
            'nivel', 'nivel_porcentaje', 'voltaje', 'voltaje_terminal',
            'amperaje', 'caudal', 'potencia', 'carga', 'altura',
            'factor_potencia', 'caudal_total', 'potencia_total',
            'corriente_total', 'nivel_destino', 'demanda',
            'posicion_valvula', 'velocidad_rotacion', 'horas_operacion',
        ]
        datos = {columna: [np.nan, np.nan] for columna in columnas}
        datos['nivel'] = [1.0, 2.0]
        datos['voltaje'] = [220.0, 221.0]
        df = pd.DataFrame(datos)
        with self.assertRaisesRegex(ValueError, 'al menos 3 variables'):
            seleccionar_variables(df)


if __name__ == '__main__':
    unittest.main()
