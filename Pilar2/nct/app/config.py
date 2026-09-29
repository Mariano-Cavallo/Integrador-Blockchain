import os
import ssl
import pika


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

N_FRAGMENTOS = int(os.getenv("N_FRAGMENTOS", "4"))

# Dificultad movil: target de segundos por bloque, y topes de largo del prefijo hex.
# Con NONCE_MAX=10_000_000 y N_FRAGMENTOS=4, un prefijo de 4 chars da ~152 nonces
# validos esperados en el rango (16**4 / 10_000_000) - margen seguro para que el
# bloque siga siendo minable. No subir DIFFICULTY_MAX_LEN sin revisar tambien
# NONCE_MAX en chain.py.
DIFFICULTY_TARGET_SEGUNDOS = int(os.getenv("DIFFICULTY_TARGET_SEGUNDOS", "17"))
DIFFICULTY_MIN_LEN = int(os.getenv("DIFFICULTY_MIN_LEN", "1"))
DIFFICULTY_MAX_LEN = int(os.getenv("DIFFICULTY_MAX_LEN", "4"))


def rabbitmq_params():
    """Parametros de conexion a RabbitMQ a partir de RABBITMQ_URL.

    Si la URL es amqps:// el broker usa un cert autofirmado, asi que ciframos el
    canal pero no validamos la identidad del server (coherente con verify_none).
    """
    params = pika.URLParameters(RABBITMQ_URL)
    if RABBITMQ_URL.startswith("amqps://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        params.ssl_options = pika.SSLOptions(ctx)
    return params
