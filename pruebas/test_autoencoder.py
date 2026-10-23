import sys
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))

from autoencoder import Autoencoder, calcular_error_reconstruccion, entrenar_autoencoder


class ModeloNoFinito(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.peso = torch.nn.Parameter(torch.tensor(1.0))

    def forward(self, x):
        return x * self.peso * float('nan')


class TestErrorReconstruccion(unittest.TestCase):
    def test_entrenamiento_rechaza_matriz_vacia(self):
        with self.assertRaisesRegex(ValueError, 'matriz 2D no vacía'):
            entrenar_autoencoder(np.empty((0, 3), dtype=np.float32), epochs=1)

    def test_entrenamiento_rechaza_entrada_no_finita(self):
        with self.assertRaisesRegex(ValueError, 'valores no finitos'):
            entrenar_autoencoder(np.array([[1.0, np.inf]], dtype=np.float32), epochs=1)

    def test_entrenamiento_rechaza_epocas_invalidas(self):
        with self.assertRaisesRegex(ValueError, 'epochs'):
            entrenar_autoencoder(np.array([[1.0, 2.0]], dtype=np.float32), epochs=0)

    def test_rechaza_entrada_no_finita(self):
        modelo = Autoencoder(input_dim=3, bottleneck_dim=2)
        X = np.array([[1.0, np.nan, 3.0]], dtype=np.float32)
        with self.assertRaisesRegex(ValueError, 'entrada.*no finitos'):
            calcular_error_reconstruccion(modelo, X)

    def test_rechaza_reconstruccion_no_finita(self):
        modelo = ModeloNoFinito()
        X = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        with self.assertRaisesRegex(ValueError, 'valores no finitos'):
            calcular_error_reconstruccion(modelo, X)


if __name__ == '__main__':
    unittest.main()
