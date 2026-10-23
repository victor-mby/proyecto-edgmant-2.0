"""Entrena el autoencoder y fija el umbral con validación separada.

Ejecutar desde la raíz del proyecto:
    py -m ml.entrenar_modelo

Los artefactos se escriben localmente. No publiques pesos, scaler ni umbral nuevos
hasta validar operación normal y fallas simuladas.
"""
import os

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

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
    datos_limpios = datos['df_clean']
    X_sin_escalar = datos_limpios.to_numpy(dtype=np.float64)

    if len(X_sin_escalar) < 20:
        raise ValueError(
            'Se necesitan al menos 20 registros completos para separar '
            'entrenamiento y validación de manera útil.'
        )

    indices_entrenamiento, indices_validacion = train_test_split(
        np.arange(len(X_sin_escalar)),
        test_size=FRACCION_VALIDACION,
        random_state=SEMILLA,
        shuffle=True,
    )

    # Ajustar el escalador únicamente sobre el subconjunto de entrenamiento
    # y aplicar ese mismo escalador tanto a validación como a inferencia.
    scaler = StandardScaler()
    X_entrenamiento = scaler.fit_transform(
        X_sin_escalar[indices_entrenamiento]
    ).astype(np.float32)
    X_validacion = scaler.transform(
        X_sin_escalar[indices_validacion]
    ).astype(np.float32)

    if not np.isfinite(X_entrenamiento).all() or not np.isfinite(X_validacion).all():
        raise ValueError('La normalización produjo valores no finitos.')

    modelo, device = entrenar_autoencoder(X_entrenamiento, epochs=50)

    # El umbral se calcula con filas que no se utilizaron para optimizar los
    # pesos del autoencoder.
    errores_validacion, _ = calcular_error_reconstruccion(
        modelo, X_validacion, device
    )
    umbral = calcular_umbral(errores_validacion, percentil=PERCENTIL_UMBRAL)

    df_validacion = (
        datos['df_raw']
        .iloc[indices_validacion]
        .copy()
        .reset_index(drop=True)
    )
    df_resultado = detectar(df_validacion, errores_validacion, umbral)

    cantidad_anomalias = int((df_resultado['anomalia'] == 1).sum())
    print(f'Registros totales: {len(X_sin_escalar)}')
    print(f'Registros de entrenamiento: {len(indices_entrenamiento)}')
    print(f'Registros de validación: {len(indices_validacion)}')
    print(f'Percentil de umbral: {PERCENTIL_UMBRAL:.1f}')
    print(f'Umbral de validación: {umbral:.8f}')
    print(
        'Registros sobre el umbral de validación: '
        f'{cantidad_anomalias}/{len(df_resultado)}'
    )
    print(
        'Nota: esta proporción no es una tasa real de falsos positivos si la '
        'validación contiene fallas sin etiquetar.'
    )

    guardar(
        modelo,
        scaler,
        datos['columnas'],
        umbral,
        ruta=RUTA_MODELO,
    )
    print(
        'Modelo guardado localmente. Antes de publicar los artefactos, valida '
        'telemetría normal en distintos estados y fallas inyectadas conocidas.'
    )
    return df_resultado, modelo, datos


if __name__ == '__main__':
    main()
