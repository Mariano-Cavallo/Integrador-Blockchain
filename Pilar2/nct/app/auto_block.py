import time
import logging
import threading
from app.redis_client import get_redis
from app.chain import formar_bloque
from app import keys

log = logging.getLogger("nct")

LOCK_KEY = "lock:auto_block"
INTERVALO = 30   # segundos entre intentos de formar bloque


def _loop_auto_bloque():
    time.sleep(15)  # esperar que Redis esté listo
    while True:
        time.sleep(INTERVALO)
        try:
            r = get_redis()
            if r.llen(keys.POOL_PENDING) > 0:
                # lock distribuido: con varias réplicas, solo UNA forma el bloque por ciclo.
                # nx=True -> set sólo si no existe (atómico). ex -> expira solo (tolerante a fallos:
                # si la réplica que lo tomó se cae, el lock se libera y otra lo toma el próximo ciclo).
                if r.set(LOCK_KEY, "1", nx=True, ex=INTERVALO - 5):
                    resultado = formar_bloque(r)
                    if resultado:
                        log.info("Auto-bloque formado: index=%s", resultado["block_index"])
        except Exception as e:
            log.error("Error en auto-bloque: %s", e)


def iniciar_auto_bloque():
    # corre el loop en un thread daemon para no bloquear al proceso anfitrión
    threading.Thread(target=_loop_auto_bloque, daemon=True).start()
