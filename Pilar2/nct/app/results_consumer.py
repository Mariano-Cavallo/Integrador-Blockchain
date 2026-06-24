import threading
import json
import logging
import pika
from app.config import RABBITMQ_URL
from app.redis_client import get_redis
from app.sealer import sellar_bloque

MINING_RESULTS = "mining_results"
log = logging.getLogger("nct")


def _consumir():
    r = get_redis()
    params = pika.URLParameters(RABBITMQ_URL)
    conexion = pika.BlockingConnection(params)
    canal = conexion.channel()
    canal.queue_declare(queue=MINING_RESULTS, durable=True,
                        arguments={"x-queue-type": "quorum", "x-quorum-initial-group-size": 3})

    def callback(ch, method, props, body):
        resultado = json.loads(body)
        sellado = sellar_bloque(resultado, r)
        log.info("Bloque %s sellado=%s", resultado["block_index"], sellado)
        
        ch.basic_ack(delivery_tag=method.delivery_tag)

    canal.basic_consume(queue=MINING_RESULTS, on_message_callback=callback)
    canal.start_consuming()

def iniciar_consumidor():
    # corre _consumir en un thread daemon para no bloquear FastAPI
    hilo = threading.Thread(target=_consumir, daemon=True)
    hilo.start()
