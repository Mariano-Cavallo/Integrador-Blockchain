from prometheus_client import Counter, REGISTRY
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

tx_total = Counter(
    "nct_transactions_total",
    "Total de transacciones procesadas",
    ["tipo", "resultado"],
)
blocks_formed = Counter("nct_blocks_formed_total", "Bloques formados por el NCT")
blocks_sealed = Counter("nct_blocks_sealed_total", "Bloques sellados exitosamente")


class EstadoCadenaCollector(Collector):
    """Calcula chain_height/pool_size en vivo contra Redis en cada scrape, en vez de
    depender de que algun proceso los haya seteado antes con .set() - con 2+ replicas de
    nct-api/nct-consumer, cada una tiene su propia copia en memoria de un Gauge normal, y
    quedan desincronizadas entre si (la que nunca sella nunca se entera de que la altura
    subio). Consultando Redis directo en el momento del scrape, todas reportan lo mismo:
    el valor real."""

    def collect(self):
        from app.redis_client import get_redis
        from app import keys

        r = get_redis()
        yield GaugeMetricFamily("nct_chain_height", "Altura actual de la cadena",
                                 value=int(r.get(keys.CHAIN_HEIGHT) or 0))
        yield GaugeMetricFamily("nct_pool_size", "Transacciones pendientes en el pool",
                                 value=r.llen(keys.POOL_PENDING))

    def describe(self):
        # REGISTRY.register() llama a describe() (si existe) en vez de collect() para
        # descubrir los nombres de las metricas - sin esto, register() ejecutaria collect()
        # una vez de entrada, y necesitaria Redis ya disponible en el momento del import.
        return [
            GaugeMetricFamily("nct_chain_height", "Altura actual de la cadena"),
            GaugeMetricFamily("nct_pool_size", "Transacciones pendientes en el pool"),
        ]


def registrar_collector_estado():
    REGISTRY.register(EstadoCadenaCollector())
