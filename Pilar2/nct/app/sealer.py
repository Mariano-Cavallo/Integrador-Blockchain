import hashlib
import json
from app import keys
from app.chain import hash_bloque

def sellar_bloque(resultado: dict, r) -> bool:
    block_index = resultado["block_index"]
    nonce = resultado["nonce"]
    hash_reportado = resultado["hash"]

    # 1. recuperar el bloque pendiente
    pending_key = keys.block_pending(block_index)
    block = r.hgetall(pending_key)
    if not block:
        # ya fue sellado por otro resultado, o no existe -> ignorar (duplicado)
        return False

    # 2. verificar el PoW
    chain = hash_bloque(block)                      # el "header hash" sobre el que se mina
    h = hashlib.md5((chain + str(nonce)).encode()).hexdigest()
    difficulty = r.hget(keys.GENESIS, "difficulty")
    if not h.startswith(difficulty) or h != hash_reportado:
        # nonce invalido -> worker con bug o malicioso -> descartar
        return False

    # 3. sellar: pegar nonce + block_hash, mover a block:{i}, subir height, vaciar pool
    block["nonce"] = nonce
    block["block_hash"] = h

    pipe = r.pipeline(transaction=True)               # MULTI/EXEC
    pipe.hset(keys.block(block_index), mapping=block)
    pipe.set(keys.CHAIN_HEIGHT, block_index)
    pipe.delete(pending_key)
    pipe.delete(keys.POOL_PENDING)
    pipe.execute()

    # limpiar solicitudes de cines que fueron confirmados en este bloque
    for tx in json.loads(block.get("transactions", "[]")):
        if tx.get("type") == "autorizar_emisor":
            r.delete(keys.solicitud_emisor(tx["solicitante"]))

    return True
