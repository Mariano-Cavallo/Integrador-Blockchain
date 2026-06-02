#include <stdio.h>

__global__ void helloKernel() {
    printf("Hola desde GPU! Bloque %d, Hilo %d\n", blockIdx.x, threadIdx.x);
}

int main() {
    helloKernel<<<2, 4>>>();  // 2 bloques, 4 hilos cada uno = 8 threads en total
    cudaDeviceSynchronize();
    printf("Hola desde CPU!\n");
    return 0;
}
