FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY static/ ./static/
ENV REDIS_URL=redis://redis:6379/0
ENV RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
# saca la serie "*_created" que prometheus_client agrega sola a cada Counter (solo el
# timestamp de creacion del proceso, no un dato util - ver Mejora 4).
ENV PROMETHEUS_DISABLE_CREATED_SERIES=True
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888"]
