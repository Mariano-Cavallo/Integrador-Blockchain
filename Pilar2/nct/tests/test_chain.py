from app.chain import formar_bloque, hash_bloque
from app.validation import validar_tx
from app.balances import calcular_saldo
from app import keys


def test_pool_vacio_no_forma_bloque(r):
    # sin txs pendientes, no hay nada que minar
    assert formar_bloque(r) is None


def test_formar_bloque_crea_pending_y_publica_tarea(r):
    validar_tx({"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
                "tokens": 10, "motivo": "compra", "pelicula": "Dune",
                "timestamp": "2026-06-10T10:00:00Z"}, r)
    tarea = formar_bloque(r)

    assert tarea is not None
    assert tarea["block_index"] == 1
    assert "chain" in tarea and "prefix" in tarea
    # el bloque quedo en pending, NO sellado todavia
    assert r.exists(keys.block_pending(1)) == 1
    assert int(r.get(keys.CHAIN_HEIGHT)) == 0          # NO subio (sella el sealer)
    # el pool NO se vacia al formar (se vacia al sellar)
    assert r.lrange(keys.POOL_PENDING, 0, -1) != []


def test_saldo_se_mantiene_tras_formar_bloque(r):
    validar_tx({"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
                "tokens": 10, "motivo": "compra", "pelicula": "Dune",
                "timestamp": "2026-06-10T10:00:00Z"}, r)
    assert calcular_saldo("Alice", r) == 10   # en el pool
    formar_bloque(r)
    assert calcular_saldo("Alice", r) == 10   # ahora en el bloque, mismo saldo


def test_primer_bloque_encadena_al_genesis(r):
    validar_tx({"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
                "tokens": 10, "motivo": "compra", "pelicula": "Dune",
                "timestamp": "2026-06-10T10:00:00Z"}, r)
    formar_bloque(r)
    # el previous_hash vive en el bloque pending, no en la tarea
    bloque = r.hgetall(keys.block_pending(1))
    genesis = r.hgetall(keys.GENESIS)
    assert bloque["previous_hash"] == hash_bloque(genesis)