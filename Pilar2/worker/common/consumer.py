import json
import pika
import logging
import os
from prometheus_client import Counter, start_http_server
from common.config import RABBITMQ_URL

MINING_TASKS = "mining_tasks" 
MINING_RESULTS = "mining_results"

tasks_processed = Counter("worker_tasks_processed_total", "Fragmentos de minado procesados")
tasks_won       = Counter("worker_tasks_won_total", "Fragmentos ganados (nonce encontrado)")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),                  # consola
    ],
)
logging.getLogger("pika").setLevel(logging.WARNING)   # silenciar ruido de pika
log = logging.getLogger("worker")

def run_worker(minar):
    start_http_server(8001)           # expone métricas en puerto 8001
    params = pika.URLParameters(RABBITMQ_URL)
    conexion = pika.BlockingConnection(params)
    canal = conexion.channel()
    canal.queue_declare(queue=MINING_TASKS, durable=True,
                        arguments={"x-queue-type": "quorum", "x-quorum-initial-group-size": 3})
    canal.queue_declare(queue=MINING_RESULTS, durable=True,
                        arguments={"x-queue-type": "quorum", "x-quorum-initial-group-size": 3})
    log.info("Worker conectado, esperando tareas en %s", MINING_TASKS)  

    def callback(ch, method, props, body):
        tarea = json.loads(body)
        nonce, h = minar(tarea["chain"], tarea["prefix"], tarea["nonce_min"], tarea["nonce_max"])
        tasks_processed.inc()
        if nonce is not None:
            tasks_won.inc()
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


