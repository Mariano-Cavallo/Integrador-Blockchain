import json
import pika
import logging
import os
from common.config import RABBITMQ_URL

MINING_TASKS = "mining_tasks" 
MINING_RESULTS = "mining_results"
LOG_FILE = os.getenv("LOG_FILE", "worker.log")   # local: ./worker.log ; docker: /var/log/worker.log


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),                  # consola
        logging.FileHandler(LOG_FILE),  # disco
    ],
)
logging.getLogger("pika").setLevel(logging.WARNING)   # silenciar ruido de pika
log = logging.getLogger("worker")

def run_worker(minar):
    # minar es la funcion que cada tipo de worker provee (CPU o GPU)
    params = pika.URLParameters(RABBITMQ_URL)
    conexion = pika.BlockingConnection(params)
    canal = conexion.channel()
    canal.queue_declare(queue=MINING_TASKS, durable=True)
    canal.queue_declare(queue=MINING_RESULTS, durable=True)
    log.info("Worker conectado, esperando tareas en %s", MINING_TASKS)  

    def callback(ch, method, props, body):
        tarea = json.loads(body)
        nonce, h = minar(tarea["chain"], tarea["prefix"], tarea["nonce_min"], tarea["nonce_max"])
        if nonce is not None:
            resultado = {"block_index": tarea["block_index"], "nonce": nonce, "hash": h}
            ch.basic_publish(exchange="", routing_key=MINING_RESULTS,
                             body=json.dumps(resultado),
                             properties=pika.BasicProperties(delivery_mode=2))
            log.info("Fragmento [%s-%s] GANADOR: nonce=%s", tarea["nonce_min"], tarea["nonce_max"], nonce)
        else:
            log.info("Fragmento [%s-%s] sin solucion", tarea["nonce_min"], tarea["nonce_max"])
        ch.basic_ack(delivery_tag=method.delivery_tag)

    canal.basic_qos(prefetch_count=1)   # una tarea por worker a la vez
    canal.basic_consume(queue=MINING_TASKS, on_message_callback=callback)
    canal.start_consuming()


