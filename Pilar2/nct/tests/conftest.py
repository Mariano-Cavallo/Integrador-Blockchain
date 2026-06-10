import json
import pytest
import fakeredis
from app import keys


@pytest.fixture
def r():
    cliente = fakeredis.FakeStrictRedis(decode_responses=True)
    # sembrar genesis minimo (como seed_genesis pero en el fake)
    cliente.hset(keys.GENESIS, mapping={
        "type": "genesis",
        "previous_hash": "0" * 16,
        "emisores_autorizados": json.dumps(["Hoyts_0xA1b2"]),
        "quorum_requerido": 1,
        "tokens_por_entrada": 10,
        "timestamp": "2026-01-01T00:00:00Z",
    })
    cliente.set(keys.CHAIN_HEIGHT, 0)
    return cliente
