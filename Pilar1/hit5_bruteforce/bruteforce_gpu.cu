#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <cuda_runtime.h>

// ─── MD5 (RFC 1321) ──────────────────────────────────────────────────────────

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

__constant__ uint32_t S[64] = {
    7,12,17,22, 7,12,17,22, 7,12,17,22, 7,12,17,22,
    5, 9,14,20, 5, 9,14,20, 5, 9,14,20, 5, 9,14,20,
    4,11,16,23, 4,11,16,23, 4,11,16,23, 4,11,16,23,
    6,10,15,21, 6,10,15,21, 6,10,15,21, 6,10,15,21
};

__device__ uint32_t leftrotate(uint32_t x, uint32_t n) {
    return (x << n) | (x >> (32 - n));
}

__device__ void md5_block(uint32_t M[16], uint32_t out[4]) {
    uint32_t a = 0x67452301, b = 0xefcdab89,
             c = 0x98badcfe, d = 0x10325476;
    for (int i = 0; i < 64; i++) {
        uint32_t F, g;
        if      (i < 16) { F = (b & c) | (~b & d); g = i; }
        else if (i < 32) { F = (d & b) | (~d & c); g = (5*i+1) % 16; }
        else if (i < 48) { F = b ^ c ^ d;           g = (3*i+5) % 16; }
        else             { F = c ^ (b | ~d);         g = (7*i)   % 16; }
        F = F + a + K[i] + M[g];
        a = d; d = c; c = b;
        b = b + leftrotate(F, S[i]);
    }
    out[0] = 0x67452301 + a;
    out[1] = 0xefcdab89 + b;
    out[2] = 0x98badcfe + c;
    out[3] = 0x10325476 + d;
}

// ─── Utilidades de device ─────────────────────────────────────────────────────

__device__ int uint_to_str(uint64_t n, char* buf) {
    if (n == 0) { buf[0] = '0'; buf[1] = '\0'; return 1; }
    char tmp[21]; int len = 0;
    while (n > 0) { tmp[len++] = '0' + (int)(n % 10); n /= 10; }
    for (int i = 0; i < len; i++) buf[i] = tmp[len - 1 - i];
    buf[len] = '\0';
    return len;
}

// ─── Kernel ───────────────────────────────────────────────────────────────────

__global__ void bruteforce_kernel(
    const uint8_t* base,
    uint32_t       base_len,
    const uint8_t* prefix_nib,
    int            prefix_len,
    uint64_t       start_nonce,
    int*           found_flag,
    uint64_t*      found_nonce,
    uint32_t*      found_digest
) {
    uint64_t nonce = start_nonce
                   + (uint64_t)blockIdx.x * blockDim.x
                   + threadIdx.x;

    if (*found_flag != 0) return;

    // Convertir nonce a string
    char nonce_str[21];
    int  nonce_len = uint_to_str(nonce, nonce_str);
    uint32_t total = base_len + (uint32_t)nonce_len;
    if (total > 55) return;

    // Armar bloque MD5 directamente (64 bytes con padding)
    uint8_t block[64];
    for (int i = 0; i < 64; i++) block[i] = 0;
    for (uint32_t i = 0; i < base_len; i++) block[i] = base[i];
    for (int i = 0; i < nonce_len; i++) block[base_len + i] = (uint8_t)nonce_str[i];
    block[total] = 0x80;
    uint64_t bit_len = (uint64_t)total * 8;
    for (int i = 0; i < 8; i++) block[56 + i] = (uint8_t)((bit_len >> (8 * i)) & 0xff);

    // Parsear bloque a 16 words little-endian
    uint32_t M[16];
    for (int i = 0; i < 16; i++)
        M[i] = (uint32_t)block[i*4]
             | ((uint32_t)block[i*4+1] << 8)
             | ((uint32_t)block[i*4+2] << 16)
             | ((uint32_t)block[i*4+3] << 24);

    // Calcular MD5
    uint32_t digest[4];
    md5_block(M, digest);

    // Serializar digest a bytes para comparar nibbles
    uint8_t bytes[16];
    for (int w = 0; w < 4; w++) {
        bytes[w*4+0] =  digest[w]        & 0xff;
        bytes[w*4+1] = (digest[w] >>  8) & 0xff;
        bytes[w*4+2] = (digest[w] >> 16) & 0xff;
        bytes[w*4+3] = (digest[w] >> 24) & 0xff;
    }

    // Comparar nibbles con el prefijo
    bool match = true;
    for (int i = 0; i < prefix_len; i++) {
        uint8_t nibble = (i % 2 == 0) ? (bytes[i/2] >> 4) : (bytes[i/2] & 0xf);
        if (nibble != prefix_nib[i]) { match = false; break; }
    }

    if (match) {
        if (atomicCAS(found_flag, 0, 1) == 0) {
            *found_nonce    = nonce;
            found_digest[0] = digest[0];
            found_digest[1] = digest[1];
            found_digest[2] = digest[2];
            found_digest[3] = digest[3];
        }
    }
}

// ─── Helpers CPU ─────────────────────────────────────────────────────────────

bool parse_prefix(const char* hex, uint8_t* nibbles, int* len) {
    *len = (int)strlen(hex);
    if (*len > 32) { fprintf(stderr, "Prefijo demasiado largo (max 32 chars hex)\n"); return false; }
    for (int i = 0; i < *len; i++) {
        char c = hex[i];
        if      (c >= '0' && c <= '9') nibbles[i] = (uint8_t)(c - '0');
        else if (c >= 'a' && c <= 'f') nibbles[i] = (uint8_t)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') nibbles[i] = (uint8_t)(c - 'A' + 10);
        else { fprintf(stderr, "Caracter invalido en prefijo: '%c'\n", c); return false; }
    }
    return true;
}

// ─── Main ─────────────────────────────────────────────────────────────────────

int main(int argc, char* argv[]) {
    if (argc != 3) {
        printf("Uso: %s <cadena> <prefijo_hex>\n", argv[0]);
        printf("Ejemplo: %s hola 0000\n", argv[0]);
        return 1;
    }

    const char* cadena  = argv[1];
    const char* prefijo = argv[2];

    uint8_t prefix_nib[32];
    int     prefix_len = 0;
    if (!parse_prefix(prefijo, prefix_nib, &prefix_len)) return 1;

    uint32_t base_len = (uint32_t)strlen(cadena);
    if (base_len > 45) {
        fprintf(stderr, "Cadena demasiado larga (max 45 chars)\n");
        return 1;
    }

    printf("Buscando nonce para MD5(%s + nonce) que empiece con '%s'...\n",
           cadena, prefijo);
    fflush(stdout);

    uint8_t*  d_base;
    uint8_t*  d_prefix;
    int*      d_flag;
    uint64_t* d_nonce;
    uint32_t* d_digest;

    cudaMalloc((void**)&d_base,   base_len);
    cudaMalloc((void**)&d_prefix, (size_t)prefix_len);
    cudaMalloc((void**)&d_flag,   sizeof(int));
    cudaMalloc((void**)&d_nonce,  sizeof(uint64_t));
    cudaMalloc((void**)&d_digest, 4 * sizeof(uint32_t));

    cudaMemcpy(d_base,   cadena,     base_len,   cudaMemcpyHostToDevice);
    cudaMemcpy(d_prefix, prefix_nib, prefix_len, cudaMemcpyHostToDevice);
    cudaMemset(d_flag,   0, sizeof(int));

    const int      THREADS = 256;
    const int      BLOCKS  = 512;
    const uint64_t BATCH   = (uint64_t)THREADS * BLOCKS;

    cudaEvent_t t_start, t_stop;
    cudaEventCreate(&t_start);
    cudaEventCreate(&t_stop);
    cudaEventRecord(t_start);

    int      h_flag  = 0;
    uint64_t h_nonce = 0;
    uint32_t h_digest[4] = {0};
    uint64_t start   = 0;

    while (h_flag == 0) {
        bruteforce_kernel<<<BLOCKS, THREADS>>>(
            d_base, base_len,
            d_prefix, prefix_len,
            start,
            d_flag, d_nonce, d_digest
        );
        cudaDeviceSynchronize();
        cudaMemcpy(&h_flag, d_flag, sizeof(int), cudaMemcpyDeviceToHost);
        start += BATCH;
    }

    cudaEventRecord(t_stop);
    cudaEventSynchronize(t_stop);
    float ms = 0.0f;
    cudaEventElapsedTime(&ms, t_start, t_stop);

    cudaMemcpy(&h_nonce, d_nonce,  sizeof(uint64_t),     cudaMemcpyDeviceToHost);
    cudaMemcpy(h_digest, d_digest, 4 * sizeof(uint32_t), cudaMemcpyDeviceToHost);

    uint8_t hash_bytes[16];
    for (int w = 0; w < 4; w++) {
        hash_bytes[w*4+0] =  h_digest[w]        & 0xff;
        hash_bytes[w*4+1] = (h_digest[w] >>  8) & 0xff;
        hash_bytes[w*4+2] = (h_digest[w] >> 16) & 0xff;
        hash_bytes[w*4+3] = (h_digest[w] >> 24) & 0xff;
    }

    printf("Nonce  : %llu\n",   (unsigned long long)h_nonce);
    printf("Input  : %s%llu\n", cadena, (unsigned long long)h_nonce);
    printf("MD5    : ");
    for (int i = 0; i < 16; i++) printf("%02x", hash_bytes[i]);
    printf("\n");
    printf("Tiempo : %.3f s\n", ms / 1000.0f);
    printf("Tandas : %llu  (~%.2fM nonces probados)\n",
           (unsigned long long)(start / BATCH),
           (double)h_nonce / 1e6);

    cudaFree(d_base); cudaFree(d_prefix);
    cudaFree(d_flag); cudaFree(d_nonce); cudaFree(d_digest);
    cudaEventDestroy(t_start); cudaEventDestroy(t_stop);
    return 0;
}
