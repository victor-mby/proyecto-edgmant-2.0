import csv
import math
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'edgemant.db')

# Encabezados reales del exportador del simulador. También se aceptan nombres
# de columnas en formato snake_case para facilitar archivos completos externos.
ENCABEZADOS = {
    'tiempo_simulacion': ('Tiempo simulación', 'Tiempo simulacion'),
    'fecha': ('Fecha',),
    'hora': ('Hora',),
    'motor_id': ('Motor',),
    'nivel': ('Nivel (m)',),
    'nivel_porcentaje': ('Nivel (%)',),
    'voltaje': ('Voltaje (V)',),
    'amperaje': ('Amperaje (A)',),
    'caudal': ('Caudal (L/s)',),
    'potencia': ('Potencia (kW)',),
    'estado_motor': ('Estado motor',),
    'estado_valvula': ('Estado válvula', 'Estado valvula'),
    'caudal_total': ('Caudal total (L/s)',),
    'potencia_total': ('Potencia total (kW)',),
    'nivel_destino': ('Nivel destino (m)',),
    'demanda': ('Demanda (L/s)',),
}

COLUMNAS = (
    'tiempo', 'tiempo_simulacion', 'timestamp', 'fecha', 'hora', 'motor_id',
    'nivel', 'nivel_porcentaje', 'voltaje', 'voltaje_terminal', 'amperaje',
    'corriente_nominal', 'caudal', 'potencia', 'potencia_nominal', 'carga',
    'altura', 'factor_potencia', 'estado_motor', 'estado_valvula',
    'posicion_valvula', 'velocidad_rotacion', 'horas_operacion', 'caudal_total',
    'potencia_total', 'corriente_total', 'nivel_destino', 'demanda',
    'nivel_tanque_maximo',
)

CAMPOS_OPCIONALES = {
    'timestamp', 'voltaje_terminal', 'corriente_nominal', 'potencia_nominal',
    'carga', 'altura', 'factor_potencia', 'posicion_valvula',
    'velocidad_rotacion', 'horas_operacion', 'corriente_total',
    'nivel_tanque_maximo',
}

NUMERICOS = {
    'timestamp', 'nivel', 'nivel_porcentaje', 'voltaje', 'voltaje_terminal',
    'amperaje', 'corriente_nominal', 'caudal', 'potencia', 'potencia_nominal',
    'carga', 'altura', 'factor_potencia', 'posicion_valvula',
    'velocidad_rotacion', 'horas_operacion', 'caudal_total', 'potencia_total',
    'corriente_total', 'nivel_destino', 'demanda', 'nivel_tanque_maximo',
}


def _crear_tabla_telemetria_nullable(conn):
    """Reconstruye la tabla conservando los datos si procede de un esquema antiguo."""
    columnas_info = conn.execute('PRAGMA table_info(registros_telemetria)').fetchall()
    if not columnas_info:
        raise RuntimeError('No existe la tabla registros_telemetria en la base de datos.')

    restricciones = {fila[1]: bool(fila[3]) for fila in columnas_info}
    if not any(restricciones.get(campo, False) for campo in CAMPOS_OPCIONALES):
        return

    vistas = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'view' AND sql IS NOT NULL"
    ).fetchall()

    conn.execute('PRAGMA foreign_keys = OFF')
    try:
        conn.execute('BEGIN IMMEDIATE')
        # SQLite puede impedir renombrar la tabla nueva mientras la vista
        # conserva una referencia temporal a la tabla que se está sustituyendo.
        for nombre_vista, _ in vistas:
            nombre_seguro = nombre_vista.replace('"', '""')
            conn.execute(f'DROP VIEW "{nombre_seguro}"')

        conn.execute('''
            CREATE TABLE registros_telemetria_nueva (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tiempo REAL NOT NULL,
                tiempo_simulacion TEXT,
                timestamp INTEGER,
                fecha TEXT,
                hora TEXT,
                motor_id TEXT NOT NULL,
                nivel REAL NOT NULL,
                nivel_porcentaje REAL NOT NULL,
                voltaje REAL NOT NULL,
                voltaje_terminal REAL,
                amperaje REAL NOT NULL,
                corriente_nominal REAL,
                caudal REAL NOT NULL,
                potencia REAL NOT NULL,
                potencia_nominal REAL,
                carga REAL,
                altura REAL,
                factor_potencia REAL,
                estado_motor TEXT NOT NULL,
                estado_valvula TEXT NOT NULL,
                posicion_valvula REAL,
                velocidad_rotacion REAL,
                horas_operacion REAL,
                caudal_total REAL NOT NULL,
                potencia_total REAL NOT NULL,
                corriente_total REAL,
                nivel_destino REAL NOT NULL,
                demanda REAL NOT NULL,
                nivel_tanque_maximo REAL,
                FOREIGN KEY (motor_id) REFERENCES motores(id)
            )
        ''')
        nombres = ', '.join(('id',) + COLUMNAS)
        conn.execute(
            f'INSERT INTO registros_telemetria_nueva ({nombres}) '
            f'SELECT {nombres} FROM registros_telemetria'
        )
        conn.execute('DROP TABLE registros_telemetria')
        conn.execute('ALTER TABLE registros_telemetria_nueva RENAME TO registros_telemetria')
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_telemetria_motor_tiempo '
            'ON registros_telemetria(motor_id, tiempo)'
        )
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_telemetria_tiempo '
            'ON registros_telemetria(tiempo)'
        )
        for _, sql_vista in vistas:
            conn.execute(sql_vista)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute('PRAGMA foreign_keys = ON')


def _valor(fila, campo):
    if campo in fila and fila[campo] not in (None, ''):
        return fila[campo]
    for encabezado in ENCABEZADOS.get(campo, ()):
        if encabezado in fila and fila[encabezado] not in (None, ''):
            return fila[encabezado]
    # Acepta la variante antigua del nombre de tiempo, si contiene segundos.
    if campo == 'tiempo_simulacion' and fila.get('Tiempo simulación (s)') not in (None, ''):
        return fila['Tiempo simulación (s)']
    return None


def _numero(valor, campo, obligatorio=False):
    if valor is None or str(valor).strip() == '':
        if obligatorio:
            raise ValueError(f'Falta el valor obligatorio del campo {campo}.')
        return None
    try:
        numero = float(str(valor).strip())
    except (TypeError, ValueError):
        raise ValueError(f'El campo {campo} debe ser numérico; se recibió {valor!r}.') from None
    if not math.isfinite(numero):
        raise ValueError(f'El campo {campo} debe ser un número finito.')
    if campo == 'timestamp':
        if not numero.is_integer():
            raise ValueError(f'El campo timestamp debe ser un entero; se recibió {valor!r}.')
        return int(numero)
    return numero


def _segundos_simulacion(valor):
    if valor is None or str(valor).strip() == '':
        raise ValueError('Falta el tiempo de simulación, necesario para ordenar las muestras.')
    texto = str(valor).strip()
    try:
        return float(texto)
    except ValueError:
        partes = texto.split(':')
        if len(partes) != 3:
            raise ValueError(
                f'Tiempo de simulación inválido: {texto!r}. Usa HH:MM:SS o segundos.'
            ) from None
        try:
            horas, minutos, segundos = (float(parte) for parte in partes)
        except ValueError:
            raise ValueError(f'Tiempo de simulación inválido: {texto!r}.') from None
        if horas < 0 or not 0 <= minutos < 60 or not 0 <= segundos < 60:
            raise ValueError(f'Tiempo de simulación fuera de rango: {texto!r}.')
        return horas * 3600 + minutos * 60 + segundos


def _normalizar_fila(fila, numero_fila):
    resultado = {}
    for campo in ('tiempo_simulacion', 'fecha', 'hora', 'motor_id',
                  'estado_motor', 'estado_valvula'):
        valor = _valor(fila, campo)
        resultado[campo] = None if valor is None else str(valor).strip()

    if not resultado['motor_id']:
        raise ValueError(f'Fila {numero_fila}: el motor está vacío.')

    tiempo_csv = _valor(fila, 'tiempo')
    if tiempo_csv is not None:
        resultado['tiempo'] = _numero(tiempo_csv, 'tiempo', obligatorio=True)
    else:
        resultado['tiempo'] = _segundos_simulacion(resultado['tiempo_simulacion'])

    requeridos = {
        'nivel', 'nivel_porcentaje', 'voltaje', 'amperaje', 'caudal',
        'potencia', 'caudal_total', 'potencia_total', 'nivel_destino', 'demanda',
    }
    for campo in NUMERICOS:
        valor = _valor(fila, campo)
        resultado[campo] = _numero(valor, campo, obligatorio=campo in requeridos)

    for campo in ('fecha', 'hora', 'estado_motor', 'estado_valvula'):
        if resultado[campo] is None:
            if campo in ('estado_motor', 'estado_valvula'):
                raise ValueError(f'Fila {numero_fila}: falta el campo obligatorio {campo}.')
            resultado[campo] = ''

    return resultado


def _clave_origen(registro):
    if registro['timestamp'] is not None:
        marca = str(registro['timestamp'])
    else:
        marca = '|'.join((
            registro.get('fecha') or '',
            registro.get('hora') or '',
            f"{registro['tiempo']:.6f}",
        ))
    return f"{registro['motor_id']}|{marca}"


def importar_csv(ruta_csv, estacion_id='EB-01'):
    if not os.path.isfile(ruta_csv):
        raise FileNotFoundError(f'CSV no encontrado: {ruta_csv}')
    if not os.path.isfile(DB_PATH):
        raise FileNotFoundError(f'Base de datos no encontrada: {DB_PATH}. Créala primero.')

    with open(ruta_csv, 'r', encoding='utf-8-sig', newline='') as archivo:
        lector = csv.DictReader(archivo)
        encabezados = set(lector.fieldnames or [])
        if not encabezados:
            raise ValueError('El CSV está vacío o no contiene una fila de encabezados.')

        faltantes = []
        for campo, variantes in ENCABEZADOS.items():
            if campo == 'tiempo_simulacion':
                continue
            if campo not in encabezados and not any(v in encabezados for v in variantes):
                faltantes.append(variantes[0])
        # El tiempo puede venir en segundos o como texto HH:MM:SS.
        tiene_tiempo = any(
            nombre in encabezados
            for nombre in (
                'tiempo', 'tiempo_simulacion', 'Tiempo simulación',
                'Tiempo simulacion', 'Tiempo simulación (s)', 'Tiempo simulacion (s)',
            )
        )
        if not tiene_tiempo:
            faltantes.append('Tiempo simulación')
        if faltantes:
            raise ValueError(
                'El CSV no contiene las columnas básicas necesarias: '
                + ', '.join(faltantes)
            )
        filas = list(lector)

    registros = [
        _normalizar_fila(fila, numero_fila)
        for numero_fila, fila in enumerate(filas, start=2)
    ]

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        _crear_tabla_telemetria_nullable(conn)
        with conn:
            conn.execute(
                'INSERT OR IGNORE INTO estaciones (id, nombre, linea, zona, operador) '
                'VALUES (?, ?, ?, ?, ?)',
                (estacion_id, 'Estación de bombeo importada', 'Importación CSV', 'Local', 'EdgeMant'),
            )
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ingestas_csv (
                    clave_origen TEXT PRIMARY KEY,
                    registro_id INTEGER NOT NULL,
                    importado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (registro_id) REFERENCES registros_telemetria(id)
                )
            ''')
            motores = {
                fila[0] for fila in conn.execute('SELECT id FROM motores').fetchall()
            }
            insertados = 0
            duplicados = 0

            for registro in registros:
                motor_id = registro['motor_id']
                if motor_id not in motores:
                    conn.execute(
                        'INSERT INTO motores (id, estacion_id, descripcion) VALUES (?, ?, ?)',
                        (motor_id, estacion_id, f'Equipo {motor_id} importado desde CSV'),
                    )
                    motores.add(motor_id)

                clave = _clave_origen(registro)
                existe = conn.execute(
                    'SELECT 1 FROM ingestas_csv WHERE clave_origen = ?', (clave,)
                ).fetchone()
                if existe:
                    duplicados += 1
                    continue

                cursor = conn.execute(
                    f'INSERT INTO registros_telemetria ({", ".join(COLUMNAS)}) '
                    f'VALUES ({", ".join(":" + campo for campo in COLUMNAS)})',
                    registro,
                )
                conn.execute(
                    'INSERT INTO ingestas_csv (clave_origen, registro_id) VALUES (?, ?)',
                    (clave, cursor.lastrowid),
                )
                insertados += 1
    finally:
        conn.close()

    faltantes_ml = sorted(
        campo for campo in CAMPOS_OPCIONALES
        if not any(_valor(fila, campo) is not None for fila in filas)
    )
    print(
        f'Importación finalizada: {insertados} nuevos, {duplicados} duplicados omitidos, '
        f'{len(registros)} filas válidas.'
    )
    if faltantes_ml:
        print('Campos no disponibles en este CSV (se guardaron como NULL): ' + ', '.join(faltantes_ml))
        print('El modelo omitirá las variables sin datos; las filas incompletas para las variables elegidas se descartarán sin imputar valores. Vuelve a entrenar el modelo después de importar el CSV.')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uso: python importar_csv.py <ruta_csv>')
        sys.exit(1)
    importar_csv(sys.argv[1])
