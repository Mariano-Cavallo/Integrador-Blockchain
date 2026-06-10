import json
import pika
import logging
import os
from common.config import RABBITMQ_URL

MINING_TASKS = "mining_tasks" 
MINING_RESULTS = "mining_results"
LOG_FILE = os.getenv("LOG_FILE", "worker.log")   # local: ./worker.log ; docker: /var/log/worker.log

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
        log.info("Tarea recibida: block %s, prefijo '%s'", tarea["block_index"], tarea["prefix"])
        nonce, h = minar(tarea["chain"], tarea["prefix"],
                         tarea["nonce_min"], tarea["nonce_max"])
        log.info("Minado OK: nonce=%s hash=%s", nonce, h)
        resultado = {"block_index": tarea["block_index"], "nonce": nonce, "hash": h}
        ch.basic_publish(exchange="", routing_key=MINING_RESULTS,
                         body=json.dumps(resultado),
                         properties=pika.BasicProperties(delivery_mode=2))
        ch.basic_ack(delivery_tag=method.delivery_tag)   # confirmo que termine
        log.info("Resultado publicado en %s", MINING_RESULTS)

    canal.basic_qos(prefetch_count=1)   # una tarea por worker a la vez
    canal.basic_consume(queue=MINING_TASKS, on_message_callback=callback)
    canal.start_consuming()



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),                  # consola
        logging.FileHandler("/var/log/worker.log"),  # disco
    ],
)
log = logging.getLogger("worker")

