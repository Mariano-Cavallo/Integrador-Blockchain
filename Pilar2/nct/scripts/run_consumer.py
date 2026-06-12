from app.logging_config import setup_logging
from app.results_consumer import _consumir   # la función que bloquea consumiendo

if __name__ == "__main__":
    setup_logging()
    _consumir()      # corre el consumidor en primer plano (es su único trabajo)
