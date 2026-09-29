import hashlib
import json
import datetime
from app import keys, metrics as m, config
from app.chain import hash_bloque


def _ajustar_dificultad(r, block, difficulty_actual):
    # dificultad movil: mas rapido que el target -> mas dificil, mas lento -> mas facil.
    # se ajusta DESPUES de sellar (no afecta la verificacion del PoW de este bloque).
    try:
        formado_en = datetime.datetime.fromisoformat(block["timestamp"])
    except (KeyError, ValueError):
        return
    elapsed = (datetime.datetime.now() - formado_en).total_seconds()

    nueva = difficulty_actual
    if elapsed < config.DIFFICULTY_TARGET_SEGUNDOS * 0.5 and len(difficulty_actual) < config.DIFFICULTY_MAX_LEN:
        nueva = difficulty_actual + "0"
    elif elapsed > config.DIFFICULTY_TARGET_SEGUNDOS * 2 and len(difficulty_actual) > config.DIFFICULTY_MIN_LEN:
        nueva = difficulty_actual[:-1]

    if nueva != difficulty_actual:
        # keys.CHAIN_DIFFICULTY, NUNCA keys.GENESIS - el genesis no se toca jamas
        # despues de sembrado (ver keys.py).
        r.set(keys.CHAIN_DIFFICULTY, nueva)


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
    difficulty = r.get(keys.CHAIN_DIFFICULTY)
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

    _ajustar_dificultad(r, block, difficulty)

    m.blocks_sealed.inc()

    # limpiar solicitudes de cines que fueron confirmados en este bloque
    for tx in json.loads(block.get("transactions", "[]")):
        if tx.get("type") == "autorizar_emisor":
            r.delete(keys.solicitud_emisor(tx["solicitante"]))

    return True
