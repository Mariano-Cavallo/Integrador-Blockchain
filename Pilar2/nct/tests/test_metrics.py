from app import metrics as m, keys
from app.validation import validar_tx

EMISION = {"type": "emision", "from": "Hoyts_0xA1b2", "to": "Alice",
           "tokens": 10, "motivo": "compra", "pelicula": "Dune",
           "timestamp": "2026-06-10T10:00:00Z"}


def _valores(collector):
    familias = {fam.name: fam for fam in collector.collect()}
    return familias["nct_chain_height"].samples[0].value, familias["nct_pool_size"].samples[0].value


def test_collector_lee_redis_en_vivo_sin_eventos_previos(r, monkeypatch):
    # el collector no depende de que nadie haya llamado antes a un .set() - lee Redis
    # directo en cada collect(), asi que un cambio hecho "por afuera" ya se refleja.
    monkeypatch.setattr("app.redis_client.get_redis", lambda: r)
    collector = m.EstadoCadenaCollector()

    assert _valores(collector) == (0, 0)

    validar_tx(dict(EMISION), r)
    assert _valores(collector) == (0, 1)

    r.set(keys.CHAIN_HEIGHT, 3)
    altura, _ = _valores(collector)
    assert altura == 3

    r.delete(keys.POOL_PENDING)
    _, pool = _valores(collector)
    assert pool == 0
