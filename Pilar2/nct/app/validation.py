import json
import hashlib
from app import keys
from pydantic import TypeAdapter, ValidationError
from app.models import Transaccion
from app.balances import calcular_saldo

_adapter = TypeAdapter(Transaccion)

def validar_tx(data, r):
    # 1. estructura
    try:
        tx = _adapter.validate_python(data)
    except ValidationError as e:
        return (False, f"estructura invalida: {e}")
    
    # 2. emisor autorizado (solo emision)
    if tx.type == "emision":
        genesis = r.hgetall(keys.GENESIS)
        autorizados = json.loads(genesis["emisores_autorizados"])
        if tx.from_ not in autorizados:
            return (False, f"emisor no autorizado: {tx.from_} no esta en la lista de emisores del genesis")

    # 3. anti-duplicado
    tid = tx_id(data)
    if r.sismember(keys.SEEN_TX, tid):
        return (False, "transaccion duplicada (ya fue procesada)")
    
    # 4. saldo (solo transferencia y canje)
    if tx.type in ("transferencia", "canje"):
        saldo = calcular_saldo(tx.from_, r)
        if saldo < tx.tokens:
            return (False, f"saldo insuficiente: tiene {saldo}, necesita {tx.tokens}")
    
    # 5. encolar + registrar el id
    r.lpush(keys.POOL_PENDING, json.dumps(data))
    r.sadd(keys.SEEN_TX, tid)
    return (True, "ok")


def tx_id(data: dict) -> str:
    # identidad unica de la tx: hash de todos sus campos (determinístico)
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
