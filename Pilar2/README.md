# Pilar 2 — Arquitectura Distribuida (NCT)

Nodo Coordinador de Tareas (NCT) del proyecto **PopToken**. Implementado en Python con
FastAPI + Redis. Ver el caso de uso en [../Propuesta/Propuesta.md](../Propuesta/Propuesta.md).

## Estado

| Paso | Descripción | Estado |
|---|---|---|
| 1 | Validación de transacciones + Redis | Hecho |
| 2 | `pool:pending` + formación de bloque | Hecho |
| 3 | RabbitMQ — publicar tarea PoW | Hecho |
| 4 | Conectar minero del Pilar 1 como worker | Hecho |
| 5 | Recibir nonce ganador + MULTI/EXEC | Hecho |
| 6 | Pool de transacciones (P5) — fragmentación + HPA | Pendiente |
| 7 | REST API completa + Web UI | Hecho |

## Pasos 1 y 2 — Validación de txs y formación de bloque (resumen)

El NCT recibe transacciones por HTTP, valida su **estructura** y el **saldo** del emisor,
y si son válidas las encola en `pool:pending` (Redis). Cuando se forma un bloque, toma todas
las txs pendientes, las encadena al bloque anterior mediante hashes y vacía el pool.

### Archivos y qué hace cada uno

| Archivo | Para qué sirve |
|---|---|
| `nct/app/models.py` | Define qué es una transacción válida (esquemas pydantic de los 4 tipos: emisión, transferencia, canje, autorizar_emisor). Discrimina por el campo `type`. |
| `nct/app/keys.py` | Único lugar con los nombres de las claves de Redis (`genesis`, `chain:height`, `pool:pending`, `block:<i>`). Evita typos. |
| `nct/app/config.py` | Lee `REDIS_URL` del entorno (con default local). |
| `nct/app/redis_client.py` | Crea el cliente de conexión a Redis. |
| `nct/app/balances.py` | Calcula el saldo de una wallet recorriendo la cadena (modelo UTXO: recibido − enviado). Incluye `pool:pending` para evitar doble gasto. |
| `nct/app/validation.py` | Valida la tx en orden: estructura (models) → emisor autorizado (solo emisión, contra el génesis) → anti-duplicado (`tx_id` MD5 contra el set `seen:tx`) → saldo (transferencia/canje). Si pasa, encola en `pool:pending` y registra el `tx_id`. |
| `nct/app/chain.py` | Lógica de la cadena: calcula el hash de un bloque (MD5, determinístico con `sort_keys`), arma `cadena_pow` (bloque serializado sin nonce ni block_hash, lo que el minero hashea) y forma el bloque tomando todo el pool, encadenándolo al anterior y publicando la tarea de PoW. |
| `nct/app/queue.py` | Conexión a RabbitMQ (pika) y `publicar_tarea`: declara la cola `mining_tasks` (durable) y publica la tarea de minado como mensaje persistente. |
| `nct/app/sealer.py` | `sellar_bloque`: recupera el bloque pendiente, **verifica el PoW** (recalcula el hash y chequea dificultad + match), y sella atómicamente (`MULTI/EXEC`): mueve a `block:{i}`, sube height, borra pending, vacía pool. |
| `nct/app/results_consumer.py` | Consumidor en background (thread daemon) que escucha `mining_results` y llama a `sellar_bloque` por cada nonce ganador. Arranca con FastAPI. |
| `nct/app/main.py` | API HTTP (FastAPI). Escritura: `POST /tx`, `POST /block`. Lectura: `GET /chain`, `/block/{i}`, `/pool`, `/status`, `/balance/{wallet}`, `/health` (Redis + RabbitMQ). Sirve la UI en `/ui`. Al startup arranca el consumidor de resultados. |
| `nct/static/index.html` | Web UI (HTML+JS vanilla): explorador de bloques, formulario de tx, consulta de saldo, botón de formar bloque y semáforos de salud. Servida por FastAPI en `/ui`. |
| `nct/scripts/seed_genesis.py` | Siembra el bloque génesis en Redis (emisores autorizados, quórum, tokens por entrada, dificultad del PoW). |
| `worker/` | Mineros que consumen `mining_tasks` y publican en `mining_results`. `common/consumer.py` (lógica compartida `run_worker(minar)`), `cpu/miner.py` (Python), `gpu/miner.py` (invoca el binario CUDA del Pilar 1). Dockerizado, escalable con `--scale worker-cpu=N`. |
| `nct/tests/` | Tests con pytest (usan `fakeredis`, no tocan el Redis real): validación de estructura, de saldo, anti-doble-gasto, formación de bloque y `cadena_pow` determinística. |
| `docker-compose.yml` | Levanta Redis (persistencia AOF, `PopToken-redis`), RabbitMQ (`PopToken-rabbitmq`, UI en :15672) y el `worker-cpu` (escalable). |

### Decisiones de diseño

- **Saldo estilo UTXO**: no se almacena, se calcula recorriendo la historia.
- **`emision` acuña tokens** (no descuenta al emisor); `transferencia` y `canje` suman al destino y restan al origen.
- **Anti-doble-gasto**: el saldo cuenta también las txs en `pool:pending`.
- Las funciones reciben el cliente Redis por parámetro → permite testear con `fakeredis`.
- **Bloque**: un bloque agrupa todas las txs pendientes (no una sola) → el costo del PoW se paga una vez por paquete.
- **Encadenamiento**: el `previous_hash` del bloque 1 es el hash MD5 del génesis (no ceros); cada bloque referencia el hash del anterior → inmutabilidad.
- **Hash determinístico**: se serializa con `json.dumps(sort_keys=True)` y se excluye `block_hash`, para que sea reproducible (necesario para el PoW del minero).
- **PoW distribuido**: el NCT no mina; publica la tarea (`chain`, `prefix`, rango de nonce) en RabbitMQ (`mining_tasks`) para que los mineros del Pilar 1 compitan. El minero busca un nonce tal que `MD5(chain + nonce)` empiece con el prefijo (`difficulty`, leído del génesis).
- **Verificación de PoW (consenso)**: el NCT no confía en el worker; recalcula el hash con el nonce reportado y confirma que cumple la dificultad antes de sellar. Barato verificar, caro producir.
- **Sellado atómico (`MULTI/EXEC`)**: guardar el bloque + subir height + borrar pending + vaciar pool ocurren todo-o-nada, para no quedar en estado corrupto si el NCT se cae a mitad.
- **Hash sobre la representación de Redis**: tanto al publicar la tarea como al verificar, el hash se calcula sobre el bloque tal como sale de Redis (todos los campos string). Si se hashea el dict en memoria (con int) en un lado y el de Redis (string) en el otro, los hashes no coinciden y la verificación falla.
- **Idempotencia de duplicados**: si llegan varios nonces para el mismo bloque, el primero lo sella y borra el pending; los siguientes no encuentran el pending y se descartan.
- **`cadena_pow` excluye el nonce**: porque el nonce es justo lo que el minero varía; la "cadena fija" es todo el bloque menos `nonce` y `block_hash`.

## Cómo ejecutar

Requisitos: Docker, Python 3.x. Instalar deps: `pip install -r nct/requirements.txt`.

```bash
# 1. Levantar Redis (desde Pilar2/)
docker compose up -d

# 2. Sembrar el génesis (desde Pilar2/nct/)
python -m scripts.seed_genesis

# 3. Levantar la API (desde Pilar2/nct/)
python -m uvicorn app.main:app --reload --port 8888
#    Docs interactivas: http://localhost:8888/docs

# 4. Correr los tests (desde Pilar2/nct/)
python -m pytest tests/ -v
```

> Nota: todos los comandos de Python se corren parados en `Pilar2/nct/` (ahí vive el paquete `app`).
