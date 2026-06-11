from app.validation import validar_tx

EMISION = {"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
           "tokens": 10, "motivo": "compra", "pelicula": "Dune",
           "timestamp": "2026-06-10T10:00:00Z"}


def test_emisor_autorizado_se_acepta(r):
    ok, _ = validar_tx(dict(EMISION), r)
    assert ok is True


def test_emisor_no_autorizado_se_rechaza(r):
    tx = dict(EMISION, **{"from": "PirataSA"})   # no esta en el genesis
    ok, motivo = validar_tx(tx, r)
    assert ok is False
    assert "no autorizado" in motivo


def test_tx_duplicada_se_rechaza(r):
    ok1, _ = validar_tx(dict(EMISION), r)
    ok2, motivo = validar_tx(dict(EMISION), r)   # misma tx exacta
    assert ok1 is True
    assert ok2 is False
    assert "duplicada" in motivo


def test_tx_distinto_timestamp_no_es_duplicada(r):
    ok1, _ = validar_tx(dict(EMISION), r)
    tx2 = dict(EMISION, **{"timestamp": "2026-06-10T11:00:00Z"})
    ok2, _ = validar_tx(tx2, r)
    assert ok1 is True and ok2 is True   # distinto timestamp -> otra tx
