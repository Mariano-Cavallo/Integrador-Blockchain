# --- Etapa 1: compilar el minero CUDA para Linux ---
FROM nvidia/cuda:12.2.2-devel-ubuntu22.04 AS builder
# arquitectura de destino: sm_61 = GPU del profe (default, no rompe el build de siempre).
# Overridable con --build-arg CUDA_ARCH=sm_XX para compilar contra otra placa (ver
# nvidia-smi --query-gpu=compute_cap --format=csv, ej. "8.9" -> sm_89).
ARG CUDA_ARCH=sm_61
WORKDIR /build
COPY gpu/limites_gpu.cu .
RUN nvcc -O3 -arch=${CUDA_ARCH} -DCUDA_ARCH_STR=\"${CUDA_ARCH}\" -o limites_gpu limites_gpu.cu

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

# saca la serie "*_created" que prometheus_client agrega sola a cada Counter.
ENV PROMETHEUS_DISABLE_CREATED_SERIES=True

CMD ["python3", "-m", "gpu.miner"]
