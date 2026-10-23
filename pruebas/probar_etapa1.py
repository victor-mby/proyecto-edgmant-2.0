import importlib.util
import os
import tempfile

BASE_DATOS_DIR = os.path.join(os.path.dirname(__file__), '..', 'base_datos')
ML_DIR = os.path.join(os.path.dirname(__file__), '..', 'ml')


def cargar_modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def main():
    print('=== EdgeMant - Prueba Etapa 1 ===')
    print()

    # Nunca reiniciar la base de datos real del proyecto al ejecutar una prueba.
    with tempfile.TemporaryDirectory(prefix='edgemant_etapa1_') as temporal:
        db_prueba = os.path.join(temporal, 'edgemant.db')

        print('Paso 1: Crear base de datos aislada de prueba...')
        crear = cargar_modulo(
            'crear_base_datos_etapa1',
            os.path.join(BASE_DATOS_DIR, 'crear_base_datos.py'),
        )
        crear.DB_PATH = db_prueba
        crear.crear_base_datos(reiniciar=True)
        print()

        print('Paso 2: Generar datos de prueba...')
        generar = cargar_modulo(
            'generar_datos_prueba_etapa1',
            os.path.join(BASE_DATOS_DIR, 'generar_datos_prueba.py'),
        )
        generar.DB_PATH = db_prueba
        generar.generar_datos_prueba()
        print()

        print('Paso 3: Leer VIEW desde Python...')
        leer = cargar_modulo(
            'leer_view_etapa1',
            os.path.join(ML_DIR, 'leer_view.py'),
        )
        leer.DB_PATH = db_prueba
        df = leer.leer_vista_ml()
        print()

        if df.empty:
            raise RuntimeError('ERROR: No se cargaron datos de prueba desde la VIEW.')

        print('OK: Flujo BASE DE DATOS -> VIEW -> PYTHON -> DATAFRAME funcionando.')
        print(f'Registros validados: {len(df)}')
        print('La base de datos temporal se eliminará al finalizar la prueba.')


if __name__ == '__main__':
    main()
