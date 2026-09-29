from prometheus_client import start_http_server
from app import metrics as m
from app.logging_config import setup_logging
from app.auto_block import iniciar_auto_bloque
from app.results_consumer import _consumir   # la función que bloquea consumiendo

if __name__ == "__main__":
    setup_logging()
    m.registrar_collector_estado()    # chain_height/pool_size en vivo contra Redis
    start_http_server(8889)           # expone /metrics del consumer en puerto 8889
    iniciar_auto_bloque()             # thread daemon: forma bloques cada 30s
    _consumir()                       # bloquea consumiendo mining_results
