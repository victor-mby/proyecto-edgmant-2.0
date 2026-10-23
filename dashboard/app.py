import os
import sys

from flask import Flask, jsonify, render_template

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dashboard.servicios.dashboard import obtener_dashboard, ejecutar_inferencia_y_guardar


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/dashboard')
def api_dashboard():
    try:
        return jsonify(obtener_dashboard())
    except Exception as error:
        app.logger.exception('No se pudo cargar el dashboard')
        return jsonify({'ok': False, 'error': str(error)}), 500


@app.route('/api/inferir', methods=['POST'])
def api_inferir():
    try:
        guardados = ejecutar_inferencia_y_guardar()
        return jsonify({'ok': True, 'detecciones_guardadas': guardados})
    except Exception as error:
        app.logger.exception('Falló la inferencia')
        return jsonify({'ok': False, 'error': str(error)}), 500


if __name__ == '__main__':
    # Solo acceso local y sin depurador interactivo expuesto en la red.
    app.run(debug=False, host='127.0.0.1', port=5000)
