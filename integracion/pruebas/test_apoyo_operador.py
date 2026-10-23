import unittest

from dashboard.servicios.servicio_apoyo_operador import construir_apoyo_operador


class TestApoyoOperador(unittest.TestCase):
    def test_alerta_saturacion_prioriza_validar_modelo(self):
        deteccion = {
            "motor_id": "M-01",
            "fecha": "22/10/2026",
            "hora": "21:12:59",
            "severidad": "CRITICO",
            "error_reconstruccion": 608.9,
            "umbral": 0.366954,
            "tipo_interpretacion": "Comportamiento operativo fuera del patron normal",
            "variables_relevantes": ["voltaje", "caudal"],
        }

        apoyo = construir_apoyo_operador(deteccion, 5518, 5518)

        self.assertEqual(apoyo["estado"], "VALIDAR_MODELO")
        self.assertTrue(apoyo["priorizar_validacion_modelo"])
        self.assertEqual(apoyo["porcentaje_anomalias"], 100.0)
        self.assertIn("no confirma por sí sola", apoyo["advertencia"])
        self.assertTrue(any("scaler.json" in accion for accion in apoyo["acciones"]))

    def test_recomendacion_electrica_es_accionable(self):
        deteccion = {
            "motor_id": "M-01",
            "severidad": "ATENCION",
            "error_reconstruccion": 0.8,
            "umbral": 0.5,
            "tipo_interpretacion": "Posible comportamiento electrico anormal",
            "variables_relevantes": ["voltaje", "amperaje"],
        }

        apoyo = construir_apoyo_operador(deteccion, 100, 15)

        self.assertEqual(apoyo["estado"], "REVISION_TECNICA")
        self.assertFalse(apoyo["priorizar_validacion_modelo"])
        self.assertTrue(any("placa del motor" in accion for accion in apoyo["acciones"]))

    def test_sin_detecciones_muestra_acciones_de_vigilancia(self):
        apoyo = construir_apoyo_operador(None, 25, 0)

        self.assertEqual(apoyo["estado"], "VIGILANCIA")
        self.assertIsNone(apoyo["deteccion"])
        self.assertTrue(apoyo["acciones"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
