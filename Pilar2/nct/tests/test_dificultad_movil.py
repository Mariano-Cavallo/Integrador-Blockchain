import hashlib
import datetime
from app.chain import formar_bloque, hash_bloque
from app.validation import validar_tx
from app.sealer import sellar_bloque
from app import keys, config

EMISION = {"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
           "tokens": 10, "motivo": "compra", "pelicula": "Dune",
           "timestamp": "2026-06-10T10:00:00Z"}


def _minar(r, block_index, difficulty="00"):
    bloque = r.hgetall(keys.block_pending(block_index))
    chain = hash_bloque(bloque)
    nonce = 0
    while True:
        h = hashlib.md5((chain + str(nonce)).encode()).hexdigest()
        if h.startswith(difficulty):
            return nonce, h
        nonce += 1


def _formar_atrasado(r, segundos):
    # simula que el bloque se formo hace `segundos`, para forzar un sellado "lento"
    pasado = (datetime.datetime.now() - datetime.timedelta(seconds=segundos)).isoformat()
    r.hset(keys.block_pending(1), "timestamp", pasado)


def test_sellado_rapido_sube_dificultad(r):
    validar_tx(dict(EMISION), r)
    formar_bloque(r)                       # timestamp = ahora -> sellado casi instantaneo
    nonce, h = _minar(r, 1)
    ok = sellar_bloque({"block_index": 1, "nonce": nonce, "hash": h}, r)

    assert ok is True
    assert r.get(keys.CHAIN_DIFFICULTY) == "000"   # "00" -> "000"


def test_sellado_lento_baja_dificultad(r):
    validar_tx(dict(EMISION), r)
    formar_bloque(r)
    _formar_atrasado(r, config.DIFFICULTY_TARGET_SEGUNDOS * 3)
    nonce, h = _minar(r, 1)
    ok = sellar_bloque({"block_index": 1, "nonce": nonce, "hash": h}, r)

    assert ok is True
    assert r.get(keys.CHAIN_DIFFICULTY) == "0"   # "00" -> "0"


def test_no_supera_el_tope_maximo(r):
    tope = "0" * config.DIFFICULTY_MAX_LEN
    r.set(keys.CHAIN_DIFFICULTY, tope)
    validar_tx(dict(EMISION), r)
    formar_bloque(r)
    nonce, h = _minar(r, 1, difficulty=tope)
    sellar_bloque({"block_index": 1, "nonce": nonce, "hash": h}, r)

    assert r.get(keys.CHAIN_DIFFICULTY) == tope


def test_no_baja_del_tope_minimo(r):
    tope = "0" * config.DIFFICULTY_MIN_LEN
    r.set(keys.CHAIN_DIFFICULTY, tope)
    validar_tx(dict(EMISION), r)
    formar_bloque(r)
    _formar_atrasado(r, config.DIFFICULTY_TARGET_SEGUNDOS * 3)
    nonce, h = _minar(r, 1, difficulty=tope)
    sellar_bloque({"block_index": 1, "nonce": nonce, "hash": h}, r)

    assert r.get(keys.CHAIN_DIFFICULTY) == tope


def test_el_genesis_nunca_se_modifica(r):
    # invariante clave: el genesis queda fijo para siempre despues de sembrado. Solo
    # keys.CHAIN_DIFFICULTY (una key aparte) se ajusta con el tiempo - nunca genesis.difficulty.
    genesis_original = dict(r.hgetall(keys.GENESIS))

    validar_tx(dict(EMISION), r)
    formar_bloque(r)                       # sellado rapido -> sube CHAIN_DIFFICULTY
    nonce, h = _minar(r, 1)
    sellar_bloque({"block_index": 1, "nonce": nonce, "hash": h}, r)

    assert r.get(keys.CHAIN_DIFFICULTY) != genesis_original["difficulty"]  # esta si cambio
    assert dict(r.hgetall(keys.GENESIS)) == genesis_original                # el genesis, no
