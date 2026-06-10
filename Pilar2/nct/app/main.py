from fastapi import FastAPI, HTTPException
from app.redis_client import get_redis
from app.validation import validar_tx
from app.balances import calcular_saldo
from app.chain import formar_bloque

app = FastAPI(title="NCT PopToken")


@app.post("/tx")
def recibir_tx(data: dict):
    r = get_redis()
    ok, motivo = validar_tx(data, r)
    if not ok:
        raise HTTPException(status_code=400, detail=motivo)
    
    return {"status": "aceptada", "motivo": motivo}


@app.get("/balance/{wallet}")
def balance(wallet: str):
    r = get_redis()
    return {"wallet": wallet, "saldo": calcular_saldo(wallet, r)}


@app.get("/health")
def health():
    r = get_redis()
    try:
        r.ping()
        return {"redis": "ok"}
    except Exception:
        return {"redis": "down"}


@app.post("/block")
def crear_bloque():
    r = get_redis()
    bloque = formar_bloque(r)
    if bloque is None:
        raise HTTPException(status_code=400, detail="no hay transacciones pendientes")
    return bloque
