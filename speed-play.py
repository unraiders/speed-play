import requests
import time
import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
def setup_logging():
    debug_mode = int(os.getenv('DEBUG_MODE', '0'))
    log_level = logging.DEBUG if debug_mode == 1 else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# Configuración desde variables de entorno
TAUTULLI_API_KEY = os.getenv('TAUTULLI_API_KEY')
TAUTULLI_IP = os.getenv('TAUTULLI_IP')
TAUTULLI_PORT = os.getenv('TAUTULLI_PORT')
TAUTULLI_BASE_URL = f"http://{TAUTULLI_IP}:{TAUTULLI_PORT}/api/v2"

QBITTORRENT_IP = os.getenv('QBITTORRENT_IP')
QBITTORRENT_PORT = os.getenv('QBITTORRENT_PORT')
QBITTORRENT_BASE_URL = f"http://{QBITTORRENT_IP}:{QBITTORRENT_PORT}"
QBITTORRENT_USER = os.getenv('QBITTORRENT_USER')
QBITTORRENT_PASSWORD = os.getenv('QBITTORRENT_PASSWORD')
WAIT_TIME = int(os.getenv('WAIT_TIME', '10'))
WAIT_CHECK = int(os.getenv('WAIT_CHECK', '20'))

# Sesión para qBittorrent
session = requests.Session()

def iniciar_sesion_qbittorrent():
    try:
        login_url = f"{QBITTORRENT_BASE_URL}/api/v2/auth/login"
        data = {'username': QBITTORRENT_USER, 'password': QBITTORRENT_PASSWORD}
        response = session.post(login_url, data=data)
        response.raise_for_status()
        if "Ok." in response.text:
            logging.info("Sesión iniciada en qBittorrent")
            return True
        else:
            logging.error("Error en el formato de respuesta de qBittorrent")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al iniciar sesión en qBittorrent: {str(e)}")
        return False

def comprobar_estado_velocidad_alternativa():
    try:
        url = f"{QBITTORRENT_BASE_URL}/api/v2/transfer/speedLimitsMode"
        response = session.get(url)
        response.raise_for_status()
        # La API devuelve "1" para activo y "0" para inactivo
        modo_alternativo = response.text == "1"
        logging.debug(f"Estado actual de velocidad alternativa: {'Activo' if modo_alternativo else 'Desactivado'}")
        return modo_alternativo
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al comprobar el modo de velocidad alternativa: {str(e)}")
        return None

def cambiar_velocidad_alternativa(activar):
    max_intentos = 3
    estado_deseado = True if activar else False
    accion = "activar" if activar else "desactivar"
    
    for intento in range(max_intentos):
        try:
            # Verificar estado actual
            estado_actual = comprobar_estado_velocidad_alternativa()
            if estado_actual == estado_deseado:
                logging.debug(f"La velocidad alternativa ya está {'activada' if activar else 'desactivada'}")
                return True
                
            # Cambiar estado
            url = f"{QBITTORRENT_BASE_URL}/api/v2/transfer/toggleSpeedLimitsMode"
            response = session.post(url)
            response.raise_for_status()
            
            # Esperar un momento y verificar que el cambio se aplicó
            time.sleep(1)
            estado_nuevo = comprobar_estado_velocidad_alternativa()
            
            if estado_nuevo == estado_deseado:
                logging.info(f"Velocidad alternativa modo: {accion} ejecutado correctamente")
                return True
            else:
                logging.warning(f"El cambio de velocidad no se aplicó correctamente. Intento {intento + 1}/{max_intentos}")
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Error al {accion} velocidad alternativa: {str(e)}")
            if intento < max_intentos - 1:
                time.sleep(2)  # Esperar antes de reintentar
                
    logging.error(f"No se pudo {accion} la velocidad alternativa después de {max_intentos} intentos")
    return False

def verificar_reproduccion_en_curso():
    try:
        url = f"{TAUTULLI_BASE_URL}?apikey={TAUTULLI_API_KEY}&cmd=get_activity"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        streams = data['response']['data']['sessions']
        num_streams = len(streams)
        logging.debug(f"Número de reproducciones activas: {num_streams}")
        return num_streams > 0
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al verificar reproducción en Tautulli: {str(e)}")
        return False
    except (KeyError, ValueError) as e:
        logging.error(f"Error al procesar la respuesta de Tautulli: {str(e)}")
        return False

def verificar_configuracion():
    required_vars = {
        'TAUTULLI_API_KEY': TAUTULLI_API_KEY,
        'TAUTULLI_IP': TAUTULLI_IP,
        'TAUTULLI_PORT': TAUTULLI_PORT,
        'QBITTORRENT_IP': QBITTORRENT_IP,
        'QBITTORRENT_PORT': QBITTORRENT_PORT,
        'QBITTORRENT_USER': QBITTORRENT_USER,
        'QBITTORRENT_PASSWORD': QBITTORRENT_PASSWORD
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        logging.error(f"Faltan las siguientes variables de entorno: {', '.join(missing_vars)}")
        return False
    return True

def main():
    setup_logging()
    logging.info("Iniciando Speed-Play")
    
    if not verificar_configuracion():
        return
    
    if not iniciar_sesion_qbittorrent():
        logging.error("No se pudo iniciar sesión en qBittorrent. Saliendo...")
        return

    reproduccion_en_curso = False
    errores_consecutivos = 0
    max_errores = 3
    ultimo_cambio = time.time()
    tiempo_minimo_entre_cambios = 5  # Mínimo 5 segundos entre cambios de velocidad

    while True:
        try:
            en_reproduccion = verificar_reproduccion_en_curso()
            tiempo_actual = time.time()
            
            if en_reproduccion and not reproduccion_en_curso:
                if tiempo_actual - ultimo_cambio >= tiempo_minimo_entre_cambios:
                    if cambiar_velocidad_alternativa(True):
                        reproduccion_en_curso = True
                        ultimo_cambio = tiempo_actual
                        logging.info("Reproducción detectada - Velocidad alternativa activada")
                
            elif not en_reproduccion and reproduccion_en_curso:
                logging.debug(f"No hay reproducción - Esperando {WAIT_TIME} segundos antes de desactivar")
                time.sleep(WAIT_TIME)
                
                # Verificar de nuevo por si ha comenzado una reproducción durante la espera
                if not verificar_reproduccion_en_curso():
                    if tiempo_actual - ultimo_cambio >= tiempo_minimo_entre_cambios:
                        if cambiar_velocidad_alternativa(False):
                            reproduccion_en_curso = False
                            ultimo_cambio = tiempo_actual
                            logging.info("Sin reproducción - Velocidad alternativa desactivada")
            
            # Verificación periódica del estado
            elif reproduccion_en_curso:
                estado_actual = comprobar_estado_velocidad_alternativa()
                if estado_actual is False:  # La velocidad se desactivó inesperadamente
                    logging.warning("La velocidad alternativa se desactivó inesperadamente, reactivando...")
                    if tiempo_actual - ultimo_cambio >= tiempo_minimo_entre_cambios:
                        if cambiar_velocidad_alternativa(True):
                            ultimo_cambio = tiempo_actual
                            logging.info("Velocidad alternativa reactivada con éxito")
            
            errores_consecutivos = 0  # Resetear contador de errores si todo va bien

        except Exception as e:
            logging.error(f"Error inesperado: {str(e)}")
            errores_consecutivos += 1
            if errores_consecutivos >= max_errores:
                logging.error(f"Demasiados errores consecutivos ({max_errores}). Reiniciando sesión...")
                if not iniciar_sesion_qbittorrent():
                    logging.error("No se pudo reiniciar la sesión. Esperando siguiente ciclo...")

        time.sleep(WAIT_CHECK)

if __name__ == "__main__":
    main()