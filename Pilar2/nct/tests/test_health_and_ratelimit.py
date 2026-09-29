"""
Tests de /health y del rate limiting (Mejora 5). A diferencia del resto de la suite (que usa
fakeredis via la fixture `r`), estos necesitan un Redis REAL: el storage del rate limiter de
slowapi requiere semantica atomica real, no la simula fakeredis. Usan la misma DB 0 que ya
levanta el job de CI (ver .github/workflows/ci.yml, servicio `redis`) - localmente, requieren
un Redis corriendo en localhost:6379 (el del docker-compose, por ejemplo).

Nota sobre `get_redis`: app.config.REDIS_URL se evalua una sola vez, en el primer import de
app.config (que puede disparar cualquier otro archivo de test importado antes que este,
alfabeticamente). Por eso ACA no se intenta cambiar REDIS_URL por variable de entorno (no seria
confiable segun el orden de collection de pytest) - en cambio, se monkeypatchea
`app.main.get_redis` directo, apuntado a una DB aislada (15), sin depender de ese orden.
"""
import pytest
import redis
from fastapi.testclient import TestClient

from app import keys
import app.main as main_module

REDIS_TEST_URL = "redis://localhost:6379/15"


@pytest.fixture
def redis_real():
    r = redis.from_url(REDIS_TEST_URL, decode_responses=True)
    r.flushdb()
    yield r
    r.flushdb()


@pytest.fixture
def client(monkeypatch, redis_real):
    monkeypatch.setattr(main_module, "get_redis", lambda: redis_real)
    return TestClient(main_module.app)


def test_health_reporta_nct_consumer_ok_con_heartbeat_vivo(client, redis_real):
    redis_real.setex(keys.HEALTH_CONSUMER, 30, "1")
    resp = client.get("/health")
    assert resp.json()["nct-consumer"] == "ok"


def test_health_reporta_nct_consumer_down_sin_heartbeat(client):
    resp = client.get("/health")
    assert resp.json()["nct-consumer"] == "down"


def test_block_se_limita_pasado_el_limite_de_requests(client):
    # limite configurado: 10/minute en POST /block (ver main.py). El storage del limiter
    # vive en la DB de REDIS_URL (no en la de `redis_real`/DB 15) - no importa cual sea,
    # solo que haya un Redis real alcanzable ahi (lo hay: mismo host, otra DB).
    for _ in range(10):
        client.post("/block")
    resp = client.post("/block")
    assert resp.status_code == 429
