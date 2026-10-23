import json
import os
import sqlite3

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler

# Reutiliza exactamente la arquitectura utilizada durante el entrenamiento.


RUTA_DB = os.path.join(os.path.dirname(__file__), '..', 'base_datos', 'edgemant.db')
RUTA_MODELOS = os.path.join(os.path.dirname(__file__), 'modelos')
COLUMNAS_IDENTIFICACION = ('id', 'motor_id', 'tiempo', 'fecha', 'hora')
from .autoencoder import Autoencoder, calcular_error_reconstruccion

def cargar_modelo():
    ruta_columnas = os.path.join(RUTA_MODELOS, 'columnas.json')
    ruta_scaler = os.path.join(RUTA_MODELOS, 'scaler.json')
    ruta_umbral = os.path.join(RUTA_MODELOS, 'umbral.txt')
    ruta_pesos = os.path.join(RUTA_MODELOS, 'autoencoder.pth')

    rutas_requeridas = (ruta_columnas, ruta_scaler, ruta_umbral, ruta_pesos)
    faltantes = [ruta for ruta in rutas_requeridas if not os.path.isfile(ruta)]
    if faltantes:
        nombres = ', '.join(os.path.basename(ruta) for ruta in faltantes)
        raise FileNotFoundError(
            f'Faltan archivos del modelo en {RUTA_MODELOS}: {nombres}. '
            'Entrena el modelo antes de ejecutar la inferencia.'
        )

    with open(ruta_columnas, 'r', encoding='utf-8') as archivo:
        columnas = json.load(archivo)
    with open(ruta_scaler, 'r', encoding='utf-8') as archivo:
        scaler_data = json.load(archivo)
    with open(ruta_umbral, 'r', encoding='utf-8') as archivo:
        texto_umbral = archivo.read().strip()

    if not isinstance(columnas, list) or not columnas or not all(
        isinstance(columna, str) and columna for columna in columnas
    ):
        raise ValueError('columnas.json debe contener una lista válida de variables.')
    if len(set(columnas)) != len(columnas):
        raise ValueError('columnas.json contiene variables duplicadas.')
    if not isinstance(scaler_data, dict) or 'mean' not in scaler_data or 'scale' not in scaler_data:
        raise ValueError('scaler.json debe contener las claves mean y scale.')

    try:
        media = np.asarray(scaler_data['mean'], dtype=float)
        escala = np.asarray(scaler_data['scale'], dtype=float)
        umbral = float(texto_umbral)
    except (TypeError, ValueError):
        raise ValueError('Los metadatos del modelo contienen valores no numéricos.') from None

    if media.shape != (len(columnas),) or escala.shape != (len(columnas),):
        raise ValueError(
            'El scaler guardado no coincide con las variables de columnas.json. '
            'Vuelve a entrenar el modelo para generar archivos compatibles.'
        )
    if not np.isfinite(media).all() or not np.isfinite(escala).all() or (escala <= 0).any():
        raise ValueError('scaler.json contiene medias o escalas inválidas.')
    if not np.isfinite(umbral) or umbral < 0:
        raise ValueError('umbral.txt debe contener un número finito no negativo.')

    scaler = StandardScaler()
    scaler.mean_ = media
    scaler.scale_ = escala
    scaler.var_ = np.asarray(scaler_data.get('var', np.square(escala)), dtype=float)
    scaler.n_features_in_ = len(columnas)

    modelo = Autoencoder(len(columnas), max(4, len(columnas) // 3))
    try:
        state_dict = torch.load(ruta_pesos, map_location='cpu', weights_only=True)
        modelo.load_state_dict(state_dict)
    except (RuntimeError, ValueError, TypeError) as error:
        raise ValueError(
            'Los pesos del Autoencoder no coinciden con la arquitectura o las variables '
            'guardadas. Vuelve a entrenar el modelo.'
        ) from error
    modelo.eval()

    return modelo, scaler, columnas, umbral


def leer_view():
    if not os.path.isfile(RUTA_DB):
        raise FileNotFoundError(
            f'No se encontró la base de datos: {RUTA_DB}. '
            'Ejecuta primero base_datos/crear_base_datos.py.'
        )

    with sqlite3.connect(RUTA_DB) as conn:
        df = pd.read_sql_query('SELECT * FROM vista_telemetria_ml', conn)
    return df


def preparar_datos(df, columnas):
    if df.empty:
        raise ValueError('La vista vista_telemetria_ml no contiene registros para analizar.')

    faltantes = [columna for columna in columnas if columna not in df.columns]
    if faltantes:
        raise ValueError(
            'La vista de telemetría no contiene todas las variables del modelo: '
            + ', '.join(faltantes)
            + '. Revisa la vista SQL y el esquema de la base de datos.'
        )

    datos = df.loc[:, columnas].copy()
    datos = datos.apply(pd.to_numeric, errors='coerce')
    datos = datos.replace([np.inf, -np.inf], np.nan)
    datos = datos.loc[datos.notna().all(axis=1)]

    if datos.empty:
        raise ValueError(
            'No hay registros completos para las variables del modelo. '
            'La telemetría importada puede no incluir todas las variables necesarias; '
            'usa la captura completa o importa registros con todas las variables.'
        )

    return datos


def normalizar(df, scaler):
    return scaler.transform(df.values)


def inferir():
    modelo, scaler, columnas, umbral = cargar_modelo()
    df_raw = leer_view()
    df_clean = preparar_datos(df_raw, columnas)
    X = normalizar(df_clean, scaler)
    errores, _ = calcular_error_reconstruccion(modelo, X)

    # Conservar metadatos y variables de sensores: el diagnóstico necesita
    # los valores originales para explicar qué variables se desviaron.
    indices_validos = df_clean.index
    columnas_identificacion = [
        columna for columna in COLUMNAS_IDENTIFICACION if columna in df_raw.columns
    ]
    faltantes_identificacion = [
        columna for columna in ('id', 'motor_id', 'tiempo')
        if columna not in df_raw.columns
    ]
    if faltantes_identificacion:
        raise ValueError(
            'La vista no contiene los campos de identificación requeridos: '
            + ', '.join(faltantes_identificacion)
        )

    # Usar los valores numéricos ya validados, no posibles cadenas originales
    # que SQLite podría devolver por su tipado dinámico.
    df_resultado = df_raw.loc[indices_validos, columnas_identificacion].copy()
    df_resultado = df_resultado.join(df_clean, how='left').reset_index(drop=True)
    df_resultado['error_reconstruccion'] = errores
    df_resultado['umbral'] = umbral
    df_resultado['anomalia'] = (df_resultado['error_reconstruccion'] > umbral).astype(int)

    return df_resultado, df_raw
