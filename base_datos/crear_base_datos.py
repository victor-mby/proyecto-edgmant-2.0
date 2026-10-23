import argparse
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'edgemant.db')
SQL_PATH = os.path.join(os.path.dirname(__file__), 'base_datos.sql')
VIEW_PATH = os.path.join(os.path.dirname(__file__), 'view_ml.sql')


def crear_base_datos(reiniciar=False):
    """Inicializa el esquema sin borrar datos, salvo que se solicite un reinicio explícito."""
    existia = os.path.isfile(DB_PATH)
    if existia and reiniciar:
        os.remove(DB_PATH)
        existia = False

    conn = sqlite3.connect(DB_PATH)
    try:
        with open(SQL_PATH, 'r', encoding='utf-8') as archivo:
            conn.executescript(archivo.read())

        with open(VIEW_PATH, 'r', encoding='utf-8') as archivo:
            conn.executescript(archivo.read())

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    accion = 'Base de datos reiniciada' if reiniciar else (
        'Base de datos verificada; los datos existentes se conservaron'
        if existia else 'Base de datos creada'
    )
    print(f'{accion}: {DB_PATH}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Inicializa el esquema de EdgeMant sin borrar datos por defecto.'
    )
    parser.add_argument(
        '--reiniciar',
        action='store_true',
        help='ELIMINA la base de datos existente y crea una nueva vacía.',
    )
    argumentos = parser.parse_args()
    crear_base_datos(reiniciar=argumentos.reiniciar)
