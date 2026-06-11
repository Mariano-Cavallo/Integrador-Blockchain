import os


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

