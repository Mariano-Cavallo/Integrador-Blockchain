#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <cuda_runtime.h>

// Constantes MD5 (RFC 1321, tabla T derivada de sin)
__constant__ uint32_t K[64] = {
    0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee,
    0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
    0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be,
    0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
    0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa,
    0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
    0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed,
    0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
    0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c,
    0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
    0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05,
    0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
    0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039,
    0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
    0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1,
    0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391
};

// Desplazamientos por ronda (RFC 1321)
__constant__ uint32_t S[64] = {
    7,12,17,22, 7,12,17,22, 7,12,17,22, 7,12,17,22,
    5, 9,14,20, 5, 9,14,20, 5, 9,14,20, 5, 9,14,20,
    4,11,16,23, 4,11,16,23, 4,11,16,23, 4,11,16,23,
    6,10,15,21, 6,10,15,21, 6,10,15,21, 6,10,15,21
};

__device__ uint32_t leftrotate(uint32_t x, uint32_t n) {
    return (x << n) | (x >> (32 - n));
}

// Calcula MD5 de un mensaje de hasta 55 bytes (un solo bloque de 512 bits)
__device__ void md5(const uint8_t* msg, uint32_t len, uint8_t* digest) {
    uint8_t block[64] = {0};

    for (uint32_t i = 0; i < len; i++)
        block[i] = msg[i];

    // Padding: bit 1 seguido de ceros y longitud en bits al final
    block[len] = 0x80;
    uint64_t bit_len = (uint64_t)len * 8;
    for (int i = 0; i < 8; i++)
        block[56 + i] = (bit_len >> (8 * i)) & 0xff;

    // Interpretar bloque como 16 words de 32 bits (little-endian)
    uint32_t M[16];
    for (int i = 0; i < 16; i++) {
        M[i] = ((uint32_t)block[i*4])
             | ((uint32_t)block[i*4+1] << 8)
             | ((uint32_t)block[i*4+2] << 16)
             | ((uint32_t)block[i*4+3] << 24);
    }

    // Valores iniciales del digest (RFC 1321)
    uint32_t a = 0x67452301;
    uint32_t b = 0xefcdab89;
    uint32_t c = 0x98badcfe;
    uint32_t d = 0x10325476;

    for (int i = 0; i < 64; i++) {
        uint32_t F, g;
        if (i < 16) {
            F = (b & c) | (~b & d);
            g = i;
        } else if (i < 32) {
            F = (d & b) | (~d & c);
            g = (5*i + 1) % 16;
        } else if (i < 48) {
            F = b ^ c ^ d;
            g = (3*i + 5) % 16;
        } else {
            F = c ^ (b | ~d);
            g = (7*i) % 16;
        }
        F = F + a + K[i] + M[g];
        a = d;
        d = c;
        c = b;
        b = b + leftrotate(F, S[i]);
    }

    uint32_t h[4] = {
        0x67452301 + a,
        0xefcdab89 + b,
        0x98badcfe + c,
        0x10325476 + d
    };

    // Serializar en little-endian
    for (int i = 0; i < 4; i++) {
        digest[i*4+0] = (h[i])       & 0xff;
        digest[i*4+1] = (h[i] >> 8)  & 0xff;
        digest[i*4+2] = (h[i] >> 16) & 0xff;
        digest[i*4+3] = (h[i] >> 24) & 0xff;
    }
}

__global__ void md5_kernel(const uint8_t* input, uint32_t len, uint8_t* output) {
    // Un solo thread calcula el hash (el input es un único string)
    if (threadIdx.x == 0 && blockIdx.x == 0) {
        md5(input, len, output);
    }
}

int main(int argc, char* argv[]) {
    if (argc != 2) {
        printf("Uso: %s <string>\n", argv[0]);
        return 1;
    }

    const char* input = argv[1];
    uint32_t len = (uint32_t)strlen(input);

    if (len > 55) {
        printf("Error: este programa soporta strings de hasta 55 caracteres (un bloque MD5).\n");
        return 1;
    }

    uint8_t* d_input;
    uint8_t* d_output;
    uint8_t h_output[16];

    cudaMalloc(&d_input,  len);
    cudaMalloc(&d_output, 16);
    cudaMemcpy(d_input, input, len, cudaMemcpyHostToDevice);

    md5_kernel<<<1, 1>>>(d_input, len, d_output);
    cudaDeviceSynchronize();

    cudaMemcpy(h_output, d_output, 16, cudaMemcpyDeviceToHost);

    cudaFree(d_input);
    cudaFree(d_output);

    printf("Input : %s\n", input);
    printf("MD5   : ");
    for (int i = 0; i < 16; i++)
        printf("%02x", h_output[i]);
    printf("\n");

    return 0;
}
