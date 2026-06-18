import pika
import secrets
import logging
import json
import threading
import time
import datetime
from app import keys
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from app.config import RABBITMQ_URL
from app.redis_client import get_redis
from app.validation import validar_tx
from app.balances import calcular_saldo
from app.chain import formar_bloque
from app.chain import formar_bloque, leer_cadena, leer_bloque, leer_pool
from app.logging_config import setup_logging
from app.auth import verificar_firma
from fastapi.responses import RedirectResponse


app = FastAPI(title="NCT PopToken")

app.mount("/ui", StaticFiles(directory="static", html=True), name="ui")

setup_logging()
log = logging.getLogger("nct")


def _loop_auto_bloque():
    time.sleep(15)  # esperar que Redis esté listo
    while True:
        time.sleep(30)
        try:
            r = get_redis()
            if r.llen(keys.POOL_PENDING) > 0:
                resultado = formar_bloque(r)
                if resultado:
                    log.info("Auto-bloque formado: index=%s", resultado["block_index"])
        except Exception as e:
            log.error("Error en auto-bloque: %s", e)




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

@app.post("/register")
def register(data: dict):
    r = get_redis()
    wallet = data.get("wallet")
    public_key = data.get("public_key")
    if not wallet or not public_key:
        raise HTTPException(status_code=400, detail="faltan campos wallet o public_key")
    r.set(keys.pubkey(wallet), public_key)
    return {"status": "registrado", "wallet": wallet}


@app.get("/challenge/{wallet}")
def get_challenge(wallet: str):
    r = get_redis()
    if not r.exists(keys.pubkey(wallet)):
        raise HTTPException(status_code=404, detail="wallet no registrada")
    ch = secrets.token_hex(16)
    r.setex(keys.challenge(wallet), 60, ch)
    return {"challenge": ch}


@app.post("/auth")
def auth(data: dict):
    r = get_redis()
    wallet = data.get("wallet")
    signature = data.get("signature")
    ch = r.get(keys.challenge(wallet))
    if not ch:
        raise HTTPException(status_code=400, detail="challenge expirado o inexistente")
    public_key_pem = r.get(keys.pubkey(wallet))
    if not verificar_firma(public_key_pem, ch, signature):
        raise HTTPException(status_code=401, detail="firma invalida")
    token = secrets.token_hex(32)
    r.setex(keys.session(token), 3600, wallet)
    r.delete(keys.challenge(wallet))
    return {"token": token, "wallet": wallet}


def _require_auth(authorization: str, r):
    if not authorization:
        raise HTTPException(status_code=401, detail="se requiere autenticacion")
    token = authorization.replace("Bearer ", "")
    wallet = r.get(keys.session(token))
    if not wallet:
        raise HTTPException(status_code=401, detail="token invalido o expirado")
    return wallet


@app.post("/tx")
def recibir_tx(data: dict, authorization: str = Header(None)):
    r = get_redis()
    wallet_autenticada = _require_auth(authorization, r)
    if data.get("from") != wallet_autenticada:
        raise HTTPException(status_code=403, detail="no podés enviar transacciones en nombre de otra wallet")
    ok, motivo = validar_tx(data, r)
    log.info("Tx %s recibida: %s", "aceptada" if ok else "rechazada", motivo)
    if not ok:
        raise HTTPException(status_code=400, detail=motivo)
    return {"status": "aceptada", "motivo": motivo}


@app.get("/balance/{wallet}")
def balance(wallet: str, authorization: str = Header(None)):
    r = get_redis()
    _require_auth(authorization, r)
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


def _get_emisores(r):
    # emisores del genesis
    genesis = r.hgetall(keys.GENESIS)
    emisores = set(json.loads(genesis.get("emisores_autorizados", "[]")))
    # escanear todos los bloques confirmados buscando AutorizarEmisor
    altura = int(r.get(keys.CHAIN_HEIGHT) or 0)
    for i in range(1, altura + 1):
        bloque = r.hgetall(keys.block(i))
        if not bloque:
            continue
        for tx in json.loads(bloque.get("transactions", "[]")):
            if tx.get("type") == "autorizar_emisor":
                emisores.add(tx["solicitante"])
    return list(emisores)


@app.post("/solicitar_emisor")
def solicitar_emisor(authorization: str = Header(None)):
    r = get_redis()
    wallet = _require_auth(authorization, r)
    if wallet in _get_emisores(r):
        raise HTTPException(status_code=400, detail="ya sos emisor autorizado")
    if r.exists(keys.solicitud_emisor(wallet)):
        raise HTTPException(status_code=400, detail="ya tenés una solicitud pendiente")
    solicitud = {"wallet": wallet, "votos_a_favor": [], "votos_en_contra": []}
    r.set(keys.solicitud_emisor(wallet), json.dumps(solicitud))
    log.info("Solicitud de emisor recibida: %s", wallet)
    return {"status": "solicitud enviada"}


@app.get("/solicitudes_emisor")
def solicitudes_emisor(authorization: str = Header(None)):
    r = get_redis()
    _require_auth(authorization, r)
    solicitudes = []
    for k in r.scan_iter("solicitud:emisor:*"):
        solicitudes.append(json.loads(r.get(k)))
    return {"solicitudes": solicitudes}


@app.post("/votar_emisor")
def votar_emisor(data: dict, authorization: str = Header(None)):
    r = get_redis()
    votante = _require_auth(authorization, r)
    emisores = _get_emisores(r)
    if votante not in emisores:
        raise HTTPException(status_code=403, detail="solo emisores autorizados pueden votar")
    solicitante = data.get("wallet")
    voto = data.get("voto")
    key = keys.solicitud_emisor(solicitante)
    raw = r.get(key)
    if not raw:
        raise HTTPException(status_code=404, detail="solicitud no encontrada")
    solicitud = json.loads(raw)
    if votante in solicitud["votos_a_favor"] or votante in solicitud["votos_en_contra"]:
        raise HTTPException(status_code=400, detail="ya votaste esta solicitud")
    if voto == "aprobar":
        solicitud["votos_a_favor"].append(votante)
    else:
        solicitud["votos_en_contra"].append(votante)
    quorum = int(r.hget(keys.GENESIS, "quorum_requerido") or 1)
    total = len(emisores)
    if len(solicitud["votos_a_favor"]) >= quorum:
        # agregar AutorizarEmisor al pool para que se mine en un bloque
        tx_auth = {
            "type": "autorizar_emisor",
            "solicitante": solicitante,
            "aprobado_por": solicitud["votos_a_favor"],
            "timestamp": datetime.datetime.now().isoformat(),
        }
        r.lpush(keys.POOL_PENDING, json.dumps(tx_auth))
        # marcar solicitud como aprobada (pendiente de minado)
        solicitud["estado"] = "aprobado_pendiente"
        r.set(key, json.dumps(solicitud))
        log.info("Emisor aprobado, AutorizarEmisor en pool: %s", solicitante)
        return {"status": "aprobado"}
    if len(solicitud["votos_en_contra"]) > total - quorum:
        r.delete(key)
        r.delete(keys.pubkey(solicitante))
        log.info("Emisor rechazado: %s", solicitante)
        return {"status": "rechazado"}
    r.set(key, json.dumps(solicitud))
    return {"status": "voto registrado", "a_favor": len(solicitud["votos_a_favor"]), "en_contra": len(solicitud["votos_en_contra"])}


@app.get("/tipo_wallet/{wallet}")
def tipo_wallet(wallet: str):
    r = get_redis()
    if wallet in _get_emisores(r):
        return {"tipo": "cine"}
    if r.exists(keys.pubkey(wallet)):
        return {"tipo": "usuario"}
    return {"tipo": "desconocida"}


@app.get("/estado_emisor/{wallet}")
def estado_emisor(wallet: str, authorization: str = Header(None)):
    r = get_redis()
    _require_auth(authorization, r)
    if wallet in _get_emisores(r):
        return {"estado": "aprobado"}
    raw = r.get(keys.solicitud_emisor(wallet))
    if raw:
        s = json.loads(raw)
        if s.get("estado") == "aprobado_pendiente":
            return {"estado": "pendiente", "votos_a_favor": len(s["votos_a_favor"]), "votos_en_contra": len(s["votos_en_contra"]), "msg": "Aprobado — esperando que se mine el bloque"}
        return {"estado": "pendiente", "votos_a_favor": len(s["votos_a_favor"]), "votos_en_contra": len(s["votos_en_contra"]), "msg": "Esperando votos"}
    return {"estado": "no_solicitado"}


@app.post("/block")
def crear_bloque():
    r = get_redis()
    bloque = formar_bloque(r)
    log.info("Bloque %s formado, tarea publicada", bloque["block_index"])
    if bloque is None:
        raise HTTPException(status_code=400, detail="no hay transacciones pendientes")
    return bloque

