import os
import sqlite3

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


RUTA_DB = os.path.join(os.path.dirname(__file__), '..', 'base_datos', 'edgemant.db')

VARIABLES_ML = [
    'nivel',
    'nivel_porcentaje',
    'voltaje',
    'voltaje_terminal',
    'amperaje',
    'caudal',
    'potencia',
    'carga',
    'altura',
    'factor_potencia',
    'caudal_total',
    'potencia_total',
    'corriente_total',
    'nivel_destino',
    'demanda',
    'posicion_valvula',
    'velocidad_rotacion',
    'horas_operacion',
]


def cargar_datos():
    if not os.path.exists(RUTA_DB):
        raise FileNotFoundError(f'Base de datos no encontrada: {RUTA_DB}')

    with sqlite3.connect(RUTA_DB) as conn:
        df = pd.read_sql_query('SELECT * FROM vista_telemetria_ml', conn)
    if df.empty:
        raise ValueError('La vista vista_telemetria_ml no contiene registros para preparar.')
    return df


def seleccionar_variables(df):
    faltantes = [columna for columna in VARIABLES_ML if columna not in df.columns]
    if faltantes:
        raise ValueError(
            'La vista de telemetría no contiene las columnas esperadas por el modelo: '
            + ', '.join(faltantes)
        )

    datos = df.loc[:, VARIABLES_ML].copy()
    for columna in VARIABLES_ML:
        datos[columna] = pd.to_numeric(datos[columna], errors='coerce')
    datos = datos.replace([np.inf, -np.inf], np.nan)

    # Los CSV del simulador no incluyen todas las variables de telemetría.
    # Excluir solo columnas sin ningún dato real evita descartar todo el lote
    # o inventar valores; las columnas elegidas quedan guardadas con el modelo.
    disponibles = [columna for columna in VARIABLES_ML if datos[columna].notna().any()]
    ausentes = [columna for columna in VARIABLES_ML if columna not in disponibles]
    if len(disponibles) < 3:
        raise ValueError(
            'Se necesitan al menos 3 variables de telemetría con datos numéricos '
            'para entrenar un modelo multivariable; se encontraron '
            f'{len(disponibles)}.'
        )
    if ausentes:
        print(
            'Variables sin datos en esta fuente (no se usarán en este entrenamiento): '
            + ', '.join(ausentes)
        )

    return datos.loc[:, disponibles].copy(), disponibles


def limpiar_datos(df):
    datos = df.replace([np.inf, -np.inf], np.nan)
    filas_antes = len(datos)
    datos = datos.dropna(axis=0, how='any')
    descartados = filas_antes - len(datos)
    if descartados:
        print(
            f'Registros incompletos o no numéricos descartados: {descartados} '
            f'de {filas_antes}. No se sustituyeron los valores ausentes por cero.'
        )
    if datos.empty:
        raise ValueError(
            'No quedan registros completos para entrenar con las variables disponibles. '
            'Revisa la calidad de la telemetría importada.'
        )
    return datos


def normalizar(df):
    scaler = StandardScaler()
    X = scaler.fit_transform(df.values)
    if not np.isfinite(X).all():
        raise ValueError('La normalización produjo valores no finitos; revisa los datos de entrada.')
    return X, scaler, df.columns.tolist()


def preparar():
    df_raw_completo = cargar_datos()
    print(f'Registros leídos desde VIEW: {len(df_raw_completo)}')
    df_vars, columnas = seleccionar_variables(df_raw_completo)
    df_clean = limpiar_datos(df_vars)
    X, scaler, nombres = normalizar(df_clean)

    # Alinear las filas originales con X para que cada error de reconstrucción
    # corresponda al registro correcto, incluso cuando se descartaron filas.
    df_raw_alineado = df_raw_completo.loc[df_clean.index].copy()
    print(f'Variables utilizadas: {nombres}')
    print(f'Datos preparados: {X.shape[0]} registros, {X.shape[1]} variables')

    return {
        'df_raw': df_raw_alineado,
        'df_raw_completo': df_raw_completo,
        'df_clean': df_clean,
        'X': X,
        'scaler': scaler,
        'columnas': nombres,
    }


if __name__ == '__main__':
    preparar()
