import json
import hashlib
from app import keys
from pydantic import TypeAdapter, ValidationError
from app.models import Transaccion
from app.balances import calcular_saldo
from app.chain import get_emisores

_adapter = TypeAdapter(Transaccion)

def validar_tx(data, r):
    # bloquear envio externo de autorizar_emisor (es una tx interna del sistema)
    if data.get("type") == "autorizar_emisor":
        return (False, "tipo de transaccion reservado al sistema")

    # 1. estructura
    try:
        tx = _adapter.validate_python(data)
    except ValidationError as e:
        return (False, f"estructura invalida: {e}")

    # emisores = genesis + cines aprobados por votacion (sellados en bloques)
    emisores = get_emisores(r)

    # 2. emisor autorizado (solo emision)
    if tx.type == "emision":
        if tx.from_ not in emisores:
            return (False, f"emisor no autorizado: {tx.from_}")

    # 3. anti-duplicado
    tid = tx_id(data)
    if r.sismember(keys.SEEN_TX, tid):
        return (False, "transaccion duplicada (ya fue procesada)")

    # 4. saldo (solo transferencia y canje)
    if tx.type in ("transferencia", "canje"):
        saldo = calcular_saldo(tx.from_, r)
        if saldo < tx.tokens:
            return (False, f"saldo insuficiente: tiene {saldo}, necesita {tx.tokens}")

    # 5. validar destinatario: debe estar registrado y ser del tipo correcto
    # origen y destino no pueden ser el mismo (transferirse a uno mismo no tiene sentido
    # y, por como se calcula el saldo, generaria tokens de la nada)
    if tx.type in ("transferencia", "canje") and tx.from_ == tx.to:
        return (False, "el origen y el destino no pueden ser la misma wallet")

    to_es_cine = tx.to in emisores
    to_registrado = bool(r.exists(keys.pubkey(tx.to)))
    if not to_registrado:
        return (False, f"destinatario '{tx.to}' no esta registrado en el sistema")
    if tx.type == "emision" and to_es_cine:
        return (False, "no se puede emitir tokens a un cine emisor")
    if tx.type == "canje" and not to_es_cine:
        return (False, "el canje debe realizarse a un cine registrado")
    if tx.type == "transferencia" and to_es_cine:
        return (False, "no se puede transferir tokens a un cine")

    # 6. encolar + registrar el id
    r.lpush(keys.POOL_PENDING, json.dumps(data))
    r.sadd(keys.SEEN_TX, tid)
    return (True, "ok")


def tx_id(data: dict) -> str:
    # identidad unica de la tx: hash de todos sus campos (determinístico)
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
