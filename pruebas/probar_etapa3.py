import sys
import os

BASE_DATOS_DIR = os.path.join(os.path.dirname(__file__), '..', 'base_datos')
ML_DIR = os.path.join(os.path.dirname(__file__), '..', 'ml')
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), '..', 'dashboard')
SERVICIOS_DIR = os.path.join(DASHBOARD_DIR, 'servicios')

sys.path.insert(0, BASE_DATOS_DIR)
sys.path.insert(0, ML_DIR)
sys.path.insert(0, DASHBOARD_DIR)
sys.path.insert(0, SERVICIOS_DIR)


def main():
    print('========================================')
    print('EDGEMANT - PRUEBA ETAPA 3')
    print('========================================')
    print()

    print('Base de datos: ', end='')
    try:
        from crear_tabla_detecciones import crear_tabla_detecciones
        crear_tabla_detecciones()
        print('OK')
    except Exception as e:
        print('ERROR:', e)
        raise

    print('VIEW: ', end='')
    try:
        from inferir import inferir
        df_resultado, df_raw = inferir()
        print('OK')
    except Exception as e:
        print('ERROR:', e)
        raise

    print('Modelo: ', end='')
    try:
        from inferir import cargar_modelo
        modelo, scaler, columnas, umbral = cargar_modelo()
        print('OK')
    except Exception as e:
        print('ERROR:', e)
        raise

    print('Scaler: ', end='')
    try:
        from preparar_datos import seleccionar_variables, limpiar_datos
        df_vars, _ = seleccionar_variables(df_raw)
        df_clean = limpiar_datos(df_vars)
        X = scaler.transform(df_clean[columnas].values)
        print('OK')
    except Exception as e:
        print('ERROR:', e)
        raise

    print('Umbral: ', end='')
    try:
        print(f'OK ({umbral:.6f})')
    except Exception as e:
        print('ERROR:', e)
        raise

    print('Inferencia: ', end='')
    try:
        df_resultado, _ = inferir()
        print('OK')
    except Exception as e:
        print('ERROR:', e)
        raise

    print('Deteccion: ', end='')
    try:
        anomalias = df_resultado[df_resultado['anomalia'] == 1]
        print(f'OK ({len(anomalias)} posibles anomalias)')
    except Exception as e:
        print('ERROR:', e)
        raise

    print('Interpretacion: ', end='')
    try:
        from interpretar import interpretar_fila
        ejemplos = 0
        for _, fila in anomalias.iterrows():
            resultado = interpretar_fila(fila, columnas, scaler, umbral)
            if resultado['severidad'] in ('ATENCION', 'CRITICO'):
                ejemplos += 1
        print(f'OK (ejemplos interpretados: {ejemplos})')
    except Exception as e:
        print('ERROR:', e)
        raise

    print('Historial: ', end='')
    try:
        from servicio_historial import obtener_estadisticas
        stats = obtener_estadisticas()
        print(f'OK (total detecciones: {stats["total"]})')
    except Exception as e:
        print('ERROR:', e)
        raise

    print('Dashboard: ', end='')
    try:
        from dashboard import obtener_dashboard
        datos_dashboard = obtener_dashboard()
        print('OK')
    except Exception as e:
        print('ERROR:', e)
        raise

    print('----------------------------------------')
    print(f'Registros analizados: {len(df_resultado)}')
    print(f'Posibles anomalias: {len(anomalias)}')
    print('ETAPA 3: OK')
    print('========================================')


if __name__ == '__main__':
    main()
