-- EdgeMant Database Schema
-- Fuente: simulador/src/simulacion/simulador.js (función capturar)
-- NO MODIFICAR EL SIMULADOR

PRAGMA journal_mode = WAL;

-- Catálogo de estaciones
CREATE TABLE IF NOT EXISTS estaciones (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    linea TEXT,
    zona TEXT,
    operador TEXT
);

-- Catálogo de motores / equipos de bombeo
CREATE TABLE IF NOT EXISTS motores (
    id TEXT PRIMARY KEY,
    estacion_id TEXT NOT NULL,
    descripcion TEXT,
    hp REAL,
    voltaje_nominal REAL,
    etapas INTEGER,
    eficiencia REAL,
    factor_potencia_nominal REAL,
    altura_cierre REAL,
    caudal_diseno REAL,
    FOREIGN KEY (estacion_id) REFERENCES estaciones(id)
);

-- Tabla principal de telemetría
-- Contiene todas las variables generadas por el simulador en cada muestra
CREATE TABLE IF NOT EXISTS registros_telemetria (
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
);

-- Registro de eventos del simulador (incluye alarmas como eventos)
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tiempo REAL NOT NULL,
    hora TEXT NOT NULL,
    tipo TEXT NOT NULL,
    equipo TEXT NOT NULL,
    severidad TEXT DEFAULT 'INFO',
    texto TEXT NOT NULL,
    estado TEXT DEFAULT ''
);

-- Alarmas stateful (capturadas desde el gestor de alarmas)
CREATE TABLE IF NOT EXISTS alarmas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tiempo_activacion REAL NOT NULL,
    tiempo_desactivacion REAL,
    id_regla TEXT NOT NULL,
    titulo TEXT NOT NULL,
    severidad TEXT DEFAULT 'MEDIA',
    equipo TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    valor REAL,
    limite REAL,
    veces INTEGER DEFAULT 1,
    acknowledge INTEGER DEFAULT 0
);

-- Índices para rendimiento en consultas ML
CREATE INDEX IF NOT EXISTS idx_telemetria_motor_tiempo ON registros_telemetria(motor_id, tiempo);
CREATE INDEX IF NOT EXISTS idx_telemetria_tiempo ON registros_telemetria(tiempo);
CREATE INDEX IF NOT EXISTS idx_eventos_tiempo ON eventos(tiempo);
CREATE INDEX IF NOT EXISTS idx_eventos_tipo ON eventos(tipo);
