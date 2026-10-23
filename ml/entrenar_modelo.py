"""Entrena el autoencoder y calcula el umbral con una validación separada.

Ejecutar desde la raíz del proyecto:
    py -m ml.entrenar_modelo

El entrenamiento genera los archivos del modelo localmente. No se deben versionar
pesos/scaler/umbral nuevos hasta verificar la tasa de falsas alarmas y las pruebas
de fallas simuladas.
"""
import os

import numpy as np
from sklearn.model_selection import train_test_split

from .preparar_datos import preparar
from .autoencoder import entrenar_autoencoder, calcular_error_reconstruccion
from .detectar_anomalias import calcular_umbral, detectar
from .guardar_modelo import guardar


RUTA_MODELO = os.path.join(os.path.dirname(__file__), 'modelos')
SEMILLA = 42
FRACCION_VALIDACION = 0.20
PERCENTIL_UMBRAL = 99.0


def main():
    datos = preparar()
    X = np.asarray(datos['X'], dtype=np.float32)

    if len(X) < 20:
        raise ValueError(
            'Se necesitan al menos 20 registros completos para separar '
            'entrenamiento y validación de manera útil.'
        )

    X_entrenamiento, X_validacion = train_test_split(
        X,
        test_size=FRACCION_VALIDACION,
        random_state=SEMILLA,
        shuffle=True,
    )

    modelo, device = entrenar_autoencoder(X_entrenamiento, epochs=50)

    # El umbral se calcula con datos apartados del ajuste del modelo; no con
    # los mismos registros usados para optimizar los pesos.
    errores_validacion, _ = calcular_error_reconstruccion(
        modelo, X_validacion, device
    )
    umbral = calcular_umbral(errores_validacion, percentil=PERCENTIL_UMBRAL)

    # Métricas descriptivas de validación: no representan una tasa real de
    # falsos positivos si el conjunto contiene fallas sin etiquetar.
    anomalias_validacion = errores_validacion > umbral
    print(f'Registros totales: {len(X)}')
    print(f'Registros de entrenamiento: {len(X_entrenamiento)}')
    print(f'Registros de validación: {len(X_validacion)}')
    print(f'Percentil del umbral: {PERCENTIL_UMBRAL:.1f}')
    print(f'Umbral de validación: {umbral:.8f}')
    print(
        'Anomalías en validación por umbral: '
        f'{int(anomalias_validacion.sum())}/{len(X_validacion)}'
    )

    # "detectar" valida la correspondencia entre errores y filas; el dataframe
    # informado corresponde solo al conjunto de validación.
    indices_validacion = X_validacion.shape[0]
    df_validacion = datos['df_raw'].iloc[:indices_validacion].copy().reset_index(drop=True)
    df_resultado = detectar(df_validacion, errores_validacion, umbral)

    guardar(
        modelo,
        datos['scaler'],
        datos['columnas'],
        umbral,
        ruta=RUTA_MODELO,
    )
    print(
        'Modelo guardado localmente. Antes de publicar sus artefactos, '
        'valida datos normales de diferentes estados y fallas inyectadas.'
    )
    return df_resultado, modelo, datos


if __name__ == '__main__':
    main()
