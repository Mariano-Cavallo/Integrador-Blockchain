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


def test_sellar_no_borra_tx_que_llego_despues_de_formar_el_bloque(r):
    # reproduce el hallazgo de la Mejora 7 (chaos): una tx nueva que entra al pool DESPUES
    # de la foto que toma formar_bloque() no debe perderse cuando el bloque se sella - antes
    # del fix, sellar_bloque hacia un DELETE completo de pool:pending y se la llevaba puesta.
    validar_tx(dict(EMISION), r)
    formar_bloque(r)  # foto de pool:pending -> block:pending:1 (solo EMISION)

    # tx nueva, llega DESPUES de la foto, mientras el bloque 1 todavia se esta minando
    tx_tardia = {**EMISION, "to": "Bob"}
    validar_tx(dict(tx_tardia), r)

    nonce, h = _minar(r, 1)
    ok = sellar_bloque({"block_index": 1, "nonce": nonce, "hash": h}, r)

    assert ok is True
    assert int(r.get(keys.CHAIN_HEIGHT)) == 1
    # la tx tardia no estaba en el bloque sellado -> tiene que seguir en el pool, no perderse
    restante = [tx for tx in r.lrange(keys.POOL_PENDING, 0, -1)]
    assert len(restante) == 1
    assert '"to": "Bob"' in restante[0] or '"to":"Bob"' in restante[0]
