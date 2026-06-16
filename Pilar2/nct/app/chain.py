import hashlib
import json
from app.config import N_FRAGMENTOS
from app import keys
import datetime
from app.queue import publicar_tarea


def hash_bloque(bloque: dict) -> str:
    # copia sin el campo block_hash (no se hashea a si mismo)
    base = {k: v for k, v in bloque.items() if k != "block_hash"}
    serializado = json.dumps(base, sort_keys=True)
    return hashlib.md5(serializado.encode()).hexdigest()

def ultimo_hash(r) -> str:
    altura = int(r.get(keys.CHAIN_HEIGHT) or 0)
    if altura == 0:
        # primer bloque: encadena al genesis
        genesis = r.hgetall(keys.GENESIS)
        return hash_bloque(genesis)
    ultimo = r.hgetall(keys.block(altura))
    return ultimo["block_hash"]

def formar_bloque(r):
    pendientes = r.lrange(keys.POOL_PENDING, 0, -1)
    if not pendientes:
        return None
    txs = [json.loads(t) for t in pendientes]

    altura = int(r.get(keys.CHAIN_HEIGHT) or 0)
    nuevo_index = altura + 1
    bloque = {
        "index": nuevo_index,
        "previous_hash": ultimo_hash(r),
        "timestamp": datetime.datetime.now().isoformat(),
        "transactions": json.dumps(txs),
    }

    # 1. guardar el bloque pendiente PRIMERO
    r.hset(keys.block_pending(nuevo_index), mapping=bloque)

    # 2. releer de Redis (ahora todo es string) y hashear ESA version
    bloque_redis = r.hgetall(keys.block_pending(nuevo_index))

    genesis = r.hgetall(keys.GENESIS)
    difficulty = genesis["difficulty"]
    chain_hash = hash_bloque(bloque_redis)

    NONCE_MAX = 10_000_000
    tam = NONCE_MAX // N_FRAGMENTOS
    for i in range(N_FRAGMENTOS):
        task = {
            "block_index": nuevo_index,
            "chain": chain_hash,
            "prefix": difficulty,
            "nonce_min": i * tam,
            "nonce_max": (i + 1) * tam - 1,
        }
        publicar_tarea(task)

    return {"block_index": nuevo_index, "fragmentos": N_FRAGMENTOS}



def leer_bloque(r, index):
    # devuelve el bloque {index} como dict, o None si no existe
    b = r.hgetall(keys.block(index))
    if not b:
        return None
    b["transactions"] = json.loads(b["transactions"])   # de-serializar las txs
    return b

def leer_cadena(r):
    # genesis + todos los bloques confirmados, en orden
    altura = int(r.get(keys.CHAIN_HEIGHT) or 0)
    bloques = [leer_bloque(r, i) for i in range(1, altura + 1)]
    return bloques

def leer_pool(r):
    # txs pendientes (aun sin minar)
    return [json.loads(t) for t in r.lrange(keys.POOL_PENDING, 0, -1)]


def block_pending(index):
    return f"block:pending:{index}"
