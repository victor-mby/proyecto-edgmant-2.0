import numpy as np
import pandas as pd


def calcular_umbral(errores, percentil=95):
    try:
        percentil = float(percentil)
        valores = np.asarray(errores, dtype=float)
    except (TypeError, ValueError):
        raise ValueError('Los errores y el percentil deben ser numéricos.') from None
    if not np.isfinite(percentil) or percentil <= 0 or percentil >= 100:
        raise ValueError('El percentil debe ser un número finito entre 0 y 100 exclusivos.')
    if valores.ndim != 1 or valores.size == 0:
        raise ValueError('Se necesita una lista no vacía de errores de reconstrucción.')
    if not np.isfinite(valores).all() or (valores < 0).any():
        raise ValueError('Los errores deben ser finitos y no negativos.')
    return float(np.percentile(valores, percentil))


def detectar(df_raw, errores, umbral):
    valores = np.asarray(errores, dtype=float)
    try:
        umbral = float(umbral)
    except (TypeError, ValueError):
        raise ValueError('El umbral debe ser numérico.') from None
    if not np.isfinite(umbral) or umbral < 0:
        raise ValueError('El umbral debe ser finito y no negativo.')
    if valores.ndim != 1 or len(valores) != len(df_raw):
        raise ValueError('Debe existir exactamente un error de reconstrucción por cada registro.')
    if not np.isfinite(valores).all() or (valores < 0).any():
        raise ValueError('Los errores deben ser finitos y no negativos.')

    df = df_raw.copy().reset_index(drop=True)
    df['error_reconstruccion'] = valores
    df['umbral'] = umbral
    df['anomalia'] = (df['error_reconstruccion'] > umbral).astype(int)
    return df
