import hashlib
from common.consumer import run_worker

def minar(cadena, prefijo, nonce_min, nonce_max):
    for nonce in range(nonce_min, nonce_max + 1):
        h = hashlib.md5((cadena + str(nonce)).encode()).hexdigest()
        if h.startswith(prefijo):
            return nonce, h
    return None, None   # sin solucion en el rango

if __name__ == "__main__":
    run_worker(minar)
