import pika
import logging
from app import keys
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from app.config import RABBITMQ_URL
from app.redis_client import get_redis
from app.validation import validar_tx
from app.balances import calcular_saldo
from app.chain import formar_bloque
from app.results_consumer import iniciar_consumidor
from app.chain import formar_bloque, leer_cadena, leer_bloque, leer_pool
from app.logging_config import setup_logging
from fastapi.responses import RedirectResponse


app = FastAPI(title="NCT PopToken")

app.mount("/ui", StaticFiles(directory="static", html=True), name="ui")

setup_logging()
log = logging.getLogger("nct")   


@app.get("/")
def root():
    return RedirectResponse(url="/ui")


@app.get("/chain")
def get_chain():
    r = get_redis()
    return {"height": int(r.get(keys.CHAIN_HEIGHT) or 0), "blocks": leer_cadena(r)}

@app.get("/block/{index}")
def get_block(index: int):
    r = get_redis()
    bloque = leer_bloque(r, index)
    if bloque is None:
        raise HTTPException(status_code=404, detail="bloque no existe")
    return bloque

@app.get("/pool")
def get_pool():
    r = get_redis()
    return {"pending": leer_pool(r)}

@app.get("/status")
def status():
    r = get_redis()
    return {
        "height": int(r.get(keys.CHAIN_HEIGHT) or 0),
        "pending": len(leer_pool(r)),
        "redis": "ok",
    }

@app.post("/tx")
def recibir_tx(data: dict):
    r = get_redis()
    ok, motivo = validar_tx(data, r)
    log.info("Tx %s recibida: %s", "aceptada" if ok else "rechazada", motivo)
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
    estado = {}
    # Redis
    try:
        r.ping()
        estado["redis"] = "ok"
    except Exception:
        estado["redis"] = "down"

    # RabbitMQ
    try:
        conexion = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        conexion.close()
        estado["rabbitmq"] = "ok"
    except Exception:
        estado["rabbitmq"] = "down"

    return estado


@app.post("/block")
def crear_bloque():
    r = get_redis()
    bloque = formar_bloque(r)
    log.info("Bloque %s formado, tarea publicada", bloque["block_index"])
    if bloque is None:
        raise HTTPException(status_code=400, detail="no hay transacciones pendientes")
    return bloque

