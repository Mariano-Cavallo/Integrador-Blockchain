import logging
import os

LOG_FILE = os.getenv("LOG_FILE", "nct.log")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE),
        ],
    )
    logging.getLogger("pika").setLevel(logging.WARNING)   
