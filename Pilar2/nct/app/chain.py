import hashlib
import json
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

    task = {
        "block_index": nuevo_index,
        "chain": hash_bloque(bloque_redis),   # <-- hash de la version en Redis
        "prefix": difficulty,
        "nonce_min": 0,
        "nonce_max": 10_000_000,
    }
    publicar_tarea(task)
    return task


def cadena_pow(bloque: dict) -> str:
    # parte fija del bloque que el minero hashea (sin nonce ni block_hash)
    base = {k: v for k, v in bloque.items() if k not in ("nonce", "block_hash")}
    return json.dumps(base, sort_keys=True)

def block_pending(index):
    return f"block:pending:{index}"
