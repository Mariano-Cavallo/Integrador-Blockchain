# --- Etapa 1: compilar el minero CUDA para Linux ---
FROM nvidia/cuda:12.2.2-devel-ubuntu22.04 AS builder
WORKDIR /build
COPY gpu/limites_gpu.cu .
RUN nvcc -O3 -arch=sm_61 -o limites_gpu limites_gpu.cu

# --- Etapa 2: imagen final (runtime CUDA + Python) ---
FROM nvidia/cuda:12.2.2-runtime-ubuntu22.04
WORKDIR /app

RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# binario compilado de la etapa anterior
COPY --from=builder /build/limites_gpu /app/limites_gpu

# logica del worker
COPY common/ ./common/
COPY gpu/ ./gpu/

CMD ["python3", "-m", "gpu.miner"]
