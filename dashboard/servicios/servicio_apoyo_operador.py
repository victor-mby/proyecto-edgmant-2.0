"""Apoyo operativo determinista a partir de las detecciones registradas.

No confirma averías: entrega comprobaciones orientativas y da prioridad a
validar el modelo cuando la tasa de anomalías sugiere falta de calibración.
"""
from __future__ import annotations

from typing import Any


UMBRAL_SATURACION_ANOMALIAS = 0.80
MINIMO_REGISTROS_PARA_ALERTA = 20


def construir_apoyo_operador(
    deteccion: dict[str, Any] | None,
    total_registros: int,
    total_detecciones: int,
) -> dict[str, Any]:
    """Construye el plan que muestra el dashboard, sin alterar el modelo."""
    registros = max(0, int(total_registros))
    detecciones = max(0, int(total_detecciones))
    tasa = detecciones / registros if registros else 0.0
    tasa = min(tasa, 1.0)

    metadatos = None
    variables: list[str] = []
    if deteccion:
        variables = [
            str(valor)
            for valor in (deteccion.get("variables_relevantes") or [])
            if valor is not None
        ]
        metadatos = {
            "motor_id": str(deteccion.get("motor_id") or "No identificado"),
            "fecha": str(deteccion.get("fecha") or "No disponible"),
            "hora": str(deteccion.get("hora") or "No disponible"),
            "severidad_modelo": str(deteccion.get("severidad") or "No clasificada"),
            "error_reconstruccion": _numero_o_none(
                deteccion.get("error_reconstruccion")
            ),
            "umbral": _numero_o_none(deteccion.get("umbral")),
            "tipo_interpretacion": str(
                deteccion.get("tipo_interpretacion")
                or "Posible comportamiento fuera del patrón normal"
            ),
        }

    # Una saturación de alertas puede indicar incompatibilidad entre datos,
    # unidades, scaler, columnas o artefactos del modelo. Evita recomendar una
    # reparación física basándose solamente en ese resultado.
    saturacion = (
        registros >= MINIMO_REGISTROS_PARA_ALERTA
        and tasa >= UMBRAL_SATURACION_ANOMALIAS
    )
    if saturacion:
        return {
            "estado": "VALIDAR_MODELO",
            "titulo": "Validar la calibración antes de atribuir una avería",
            "resumen": (
                f"{tasa:.1%} de los registros almacenados aparece como posible anomalía "
                f"({detecciones} de {registros}). Una tasa tan alta requiere comprobar "
                "la compatibilidad entre el modelo y la telemetría."
            ),
            "advertencia": (
                "La clasificación del modelo no confirma por sí sola una falla física. "
                "Hasta validar la calibración, no uses esta severidad como diagnóstico "
                "definitivo ni cambies el umbral automáticamente."
            ),
            "acciones": [
                "Revisar una muestra reciente de telemetría y confirmar que las unidades, rangos y valores coincidan con los generados por el simulador.",
                "Verificar que columnas.json, scaler.json, umbral.txt y autoencoder.pth pertenezcan a la misma versión entrenada y al mismo orden de variables.",
                "Comparar el error de reconstrucción con datos de operación normal conocidos antes de decidir un mantenimiento o modificar el umbral.",
            ],
            "variables": variables,
            "deteccion": metadatos,
            "porcentaje_anomalias": round(tasa * 100, 2),
            "priorizar_validacion_modelo": True,
        }

    if not deteccion:
        return {
            "estado": "VIGILANCIA",
            "titulo": "Sin detecciones disponibles para analizar",
            "resumen": (
                "El sistema no tiene una detección registrada para generar una "
                "recomendación específica."
            ),
            "advertencia": None,
            "acciones": [
                "Mantener la vigilancia de las variables de operación.",
                "Confirmar que el receptor continúe recibiendo muestras y que las evaluaciones ML no acumulen pendientes o errores.",
            ],
            "variables": [],
            "deteccion": None,
            "porcentaje_anomalias": round(tasa * 100, 2),
            "priorizar_validacion_modelo": False,
        }

    tipo = metadatos["tipo_interpretacion"].casefold()
    vars_normalizadas = {variable.casefold() for variable in variables}
    if "sobrecarga" in tipo:
        acciones = [
            "Comparar corriente, potencia y carga con los valores nominales de placa y con el historial reciente del motor.",
            "Si la desviación se confirma, solicitar la inspección del equipo conforme al procedimiento de mantenimiento y seguridad de la instalación.",
        ]
    elif "electric" in tipo:
        acciones = [
            "Contrastar tensión de red, tensión en terminales y corriente con la placa del motor y los límites de la instalación.",
            "Revisar tendencias y consistencia de las lecturas eléctricas; si se confirma una desviación, solicitar inspección al personal autorizado según el procedimiento de seguridad.",
        ]
    elif "hidraulic" in tipo or "flujo" in tipo or "caudal" in tipo:
        acciones = [
            "Comparar caudal, nivel de succión/destino y posición de la válvula con el punto de operación esperado.",
            "Verificar visualmente la posición de las válvulas y comprobar si hay indicios de obstrucción, fuga o entrada de aire, siguiendo el procedimiento de la estación.",
            "Confirmar las lecturas con instrumentos o tendencias independientes antes de intervenir en la bomba.",
        ]
    elif vars_normalizadas.intersection(
        {"voltaje", "voltaje_terminal", "amperaje", "corriente_total", "factor_potencia"}
    ):
        acciones = [
            "Contrastar tensión de red, tensión en terminales y corriente con la placa del motor y los límites de la instalación.",
            "Revisar tendencias y consistencia de las lecturas eléctricas; si se confirma una desviación, solicitar inspección al personal autorizado según el procedimiento de seguridad.",
        ]
    elif vars_normalizadas.intersection(
        {"caudal", "caudal_total", "nivel", "nivel_destino", "posicion_valvula", "altura", "demanda"}
    ):
        acciones = [
            "Comparar caudal, nivel de succión/destino y posición de la válvula con el punto de operación esperado.",
            "Verificar visualmente la posición de las válvulas y comprobar si hay indicios de obstrucción, fuga o entrada de aire, siguiendo el procedimiento de la estación.",
            "Confirmar las lecturas con instrumentos o tendencias independientes antes de intervenir en la bomba.",
        ]
    elif vars_normalizadas.intersection(
        {"carga", "potencia", "potencia_total", "amperaje", "corriente_total"}
    ):
        acciones = [
            "Comparar corriente, potencia y carga con los valores nominales de placa y con el historial reciente del motor.",
            "Si la desviación se confirma, solicitar la inspección del equipo conforme al procedimiento de mantenimiento y seguridad de la instalación.",
        ]
    else:
        acciones = [
            "Comparar los valores señalados con las muestras inmediatamente anteriores y posteriores del mismo motor.",
            "Verificar la calidad del sensor, las unidades y el estado operativo registrado antes de atribuir la desviación a una avería.",
            "Si la desviación se confirma con datos independientes, seguir el procedimiento técnico de inspección de la estación.",
        ]

    acciones.insert(
        0,
        "Confirmar que la lectura sigue fuera del patrón esperado y revisar su tendencia; una detección aislada del modelo no demuestra por sí sola una avería.",
    )
    return {
        "estado": "REVISION_TECNICA",
        "titulo": metadatos["tipo_interpretacion"],
        "resumen": (
            f"El modelo registró una posible anomalía para el motor {metadatos['motor_id']}. "
            "Las comprobaciones siguientes son orientativas y deben contrastarse con las señales reales."
        ),
        "advertencia": (
            "No se ha confirmado una avería física. Si hay riesgo para las personas o el equipo, "
            "aplica el procedimiento de seguridad de la instalación y consulta al responsable."
        ),
        "acciones": acciones,
        "variables": variables,
        "deteccion": metadatos,
        "porcentaje_anomalias": round(tasa * 100, 2),
        "priorizar_validacion_modelo": False,
    }


def _numero_o_none(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if numero == numero and abs(numero) != float("inf") else None
