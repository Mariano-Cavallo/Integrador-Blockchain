import hashlib
import json
from app import keys
import datetime


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

def formar_bloque(r) -> dict:
    # 1. tomar todas las txs pendientes
    pendientes = r.lrange(keys.POOL_PENDING, 0, -1)
    if not pendientes:
        return None   # no hay nada que minar
    txs = [json.loads(t) for t in pendientes]

    # 2. armar el bloque
    altura = int(r.get(keys.CHAIN_HEIGHT) or 0)
    nuevo_index = altura + 1
    bloque = {
        "index": nuevo_index,
        "previous_hash": ultimo_hash(r),
        "timestamp": datetime.datetime.now().isoformat(),                  # time / ISO
        "transactions": json.dumps(txs),   # serializado (Redis hash no guarda listas)
        "nonce": 0,                        # lo encontrara el minero (paso 3-5)
    }
    bloque["block_hash"] = hash_bloque(bloque)

    # 3. persistir: guardar bloque, subir height, vaciar el pool
    r.hset(keys.block(nuevo_index), mapping=bloque)
    r.set(keys.CHAIN_HEIGHT, nuevo_index)
    r.delete(keys.POOL_PENDING)

    return bloque
