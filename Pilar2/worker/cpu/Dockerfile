# Worker CPU — mina tareas de PoW consumiendo de RabbitMQ.
# Build context esperado: Pilar2/worker/
#   docker build -f cpu/Dockerfile -t poptoken-worker-cpu .

FROM python:3.12-slim

WORKDIR /app

# Dependencias primero (mejor cache: solo se reinstala si cambia requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código: la lógica compartida y la implementación CPU
COPY common/ ./common/
COPY cpu/ ./cpu/

# La URL de RabbitMQ se inyecta por entorno (default apunta al servicio 'rabbitmq').
ENV RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/

# Arranca el worker como módulo (igual que en local: python -m cpu.miner)
CMD ["python", "-m", "cpu.miner"]
