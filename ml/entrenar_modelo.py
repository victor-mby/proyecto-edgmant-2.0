import os

if __package__:
    from .preparar_datos import preparar
    from .autoencoder import entrenar_autoencoder, calcular_error_reconstruccion
    from .detectar_anomalias import calcular_umbral, detectar
    from .guardar_modelo import guardar
else:
    # Compatibilidad con ejecución directa: py .\ml\entrenar_modelo.py
    from preparar_datos import preparar
    from autoencoder import entrenar_autoencoder, calcular_error_reconstruccion
    from detectar_anomalias import calcular_umbral, detectar
    from guardar_modelo import guardar


RUTA_MODELO = os.path.join(os.path.dirname(__file__), 'modelos')


def main():
    datos = preparar()
    X = datos['X']
    modelo, device = entrenar_autoencoder(X, epochs=50)
    errores, reconstruido = calcular_error_reconstruccion(modelo, X, device)
    umbral = calcular_umbral(errores, percentil=95)
    df_resultado = detectar(datos['df_raw'], errores, umbral)
    normales = int((df_resultado['anomalia'] == 0).sum())
    anomalias = int((df_resultado['anomalia'] == 1).sum())
    print(f'Umbral: {umbral:.6f}')
    print(f'Registros normales: {normales}')
    print(f'Posibles anomalias: {anomalias}')
    guardar(modelo, datos['scaler'], datos['columnas'], umbral, ruta=RUTA_MODELO)
    return df_resultado, modelo, datos


if __name__ == '__main__':
    main()
