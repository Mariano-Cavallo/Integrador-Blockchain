FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY static/ ./static/
ENV REDIS_URL=redis://redis:6379/0
ENV RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
ENV LOG_FILE=/var/log/nct.log
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888"]
