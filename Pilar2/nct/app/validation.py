import json
from pydantic import TypeAdapter, ValidationError
from app.models import Transaccion
from app.balances import calcular_saldo
from app import keys

_adapter = TypeAdapter(Transaccion)

def validar_tx(data, r):
    # 1. estructura
    try:
        tx = _adapter.validate_python(data)
    except ValidationError as e:
        return (False, f"estructura invalida: {e}")

    # 2. saldo (solo transferencia y canje)
    if tx.type in ("transferencia", "canje"):
        saldo = calcular_saldo(tx.from_, r)
        if saldo < tx.tokens:
            return (False, f"saldo insuficiente: tiene {saldo}, necesita {tx.tokens}")

    # 3. encolar
    r.lpush(keys.POOL_PENDING, json.dumps(data))
    return (True, "ok")
