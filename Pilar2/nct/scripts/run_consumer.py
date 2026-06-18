from app.logging_config import setup_logging
from app.auto_block import iniciar_auto_bloque
from app.results_consumer import _consumir   # la función que bloquea consumiendo

if __name__ == "__main__":
    setup_logging()
    iniciar_auto_bloque()   # thread daemon: forma bloques cada 30s (con lock distribuido)
    _consumir()             # corre el consumidor en primer plano (bloquea)
