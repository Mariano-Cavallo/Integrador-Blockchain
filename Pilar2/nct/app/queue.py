import json
import pika
from app.config import RABBITMQ_URL

MINING_TASKS = "mining_tasks"   # nombre de la cola de tareas de minado

def publicar_tarea(tarea: dict):
    # 1. conectar
    params = pika.URLParameters(RABBITMQ_URL)
    conexion = pika.BlockingConnection(params)
    canal = conexion.channel()

    # 2. declarar la cola (idempotente: si ya existe, no hace nada)
    canal.queue_declare(queue=MINING_TASKS, durable=True,
                        arguments={"x-queue-type": "quorum"})

    # 3. publicar el mensaje (la tarea serializada a JSON)
    canal.basic_publish(
        exchange="",
        routing_key=MINING_TASKS,
        body=json.dumps(tarea),
        properties=pika.BasicProperties(delivery_mode=2),  # mensaje persistente
    )

    # 4. cerrar
    conexion.close()
