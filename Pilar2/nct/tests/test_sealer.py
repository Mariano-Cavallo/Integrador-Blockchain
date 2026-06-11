import hashlib
from app.chain import formar_bloque, hash_bloque
from app.validation import validar_tx
from app.sealer import sellar_bloque
from app import keys

EMISION = {"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
           "tokens": 10, "motivo": "compra", "pelicula": "Dune",
           "timestamp": "2026-06-10T10:00:00Z"}


def _minar(r, block_index, difficulty="00"):
    # reproduce lo que hace un worker: encuentra un nonce valido
    bloque = r.hgetall(keys.block_pending(block_index))
    chain = hash_bloque(bloque)
    nonce = 0
    while True:
        h = hashlib.md5((chain + str(nonce)).encode()).hexdigest()
        if h.startswith(difficulty):
            return nonce, h
        nonce += 1


def test_sella_con_nonce_valido(r):
    validar_tx(dict(EMISION), r)
    formar_bloque(r)                       # crea block:pending:1
    nonce, h = _minar(r, 1)
    ok = sellar_bloque({"block_index": 1, "nonce": nonce, "hash": h}, r)

    assert ok is True
    assert int(r.get(keys.CHAIN_HEIGHT)) == 1          # subio la altura
    assert r.exists(keys.block_pending(1)) == 0        # pending eliminado
    assert r.hget(keys.block(1), "nonce") == str(nonce) # sellado con el nonce


def test_nonce_invalido_se_rechaza(r):
    validar_tx(dict(EMISION), r)
    formar_bloque(r)
    # nonce que NO produce un hash con prefijo "00"
    ok = sellar_bloque({"block_index": 1, "nonce": 999999, "hash": "quierounpaty"}, r)
    assert ok is False
    assert int(r.get(keys.CHAIN_HEIGHT)) == 0          # NO sello
    assert r.exists(keys.block_pending(1)) == 1        # sigue pending


def test_duplicado_se_ignora(r):
    validar_tx(dict(EMISION), r)
    formar_bloque(r)
    nonce, h = _minar(r, 1)
    ok1 = sellar_bloque({"block_index": 1, "nonce": nonce, "hash": h}, r)
    ok2 = sellar_bloque({"block_index": 1, "nonce": nonce, "hash": h}, r)  # de nuevo
    assert ok1 is True
    assert ok2 is False        # ya no hay pending -> se ignora
