from prometheus_client import start_http_server
from app import keys, metrics as m
from app.logging_config import setup_logging
from app.auto_block import iniciar_auto_bloque
from app.redis_client import get_redis
from app.results_consumer import _consumir   # la función que bloquea consumiendo

if __name__ == "__main__":
    setup_logging()
    # inicializar gauge de altura desde Redis al arrancar
    r = get_redis()
    m.chain_height.set(int(r.get(keys.CHAIN_HEIGHT) or 0))
    m.pool_size.set(r.llen(keys.POOL_PENDING))
    start_http_server(8889)           # expone /metrics del consumer en puerto 8889
    iniciar_auto_bloque()             # thread daemon: forma bloques cada 30s
    _consumir()                       # bloquea consumiendo mining_results
