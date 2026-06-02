# Hit 3 — NVIDIA CCCL: qué es y cómo se relaciona con Thrust

## ¿Qué es CCCL?

CCCL (CUDA Core Compute Libraries) es un repositorio unificado que consolida varias bibliotecas fundamentales de CUDA C++ en una única plataforma de desarrollo cohesiva. Reúne Thrust, CUB y libcudacxx, que en conjunto proveen abstracciones de alto nivel, primitivas de bajo nivel optimizadas, y una biblioteca estándar compatible con CUDA para programación en GPU.

El objetivo de CCCL es proveer a los desarrolladores de CUDA C++ bloques de construcción que faciliten escribir código seguro y eficiente. La idea surgió orgánicamente de los proyectos Thrust, CUB y libcudacxx, desarrollados de forma independiente a lo largo de los años con un objetivo similar, hasta que se volvió evidente que la comunidad se beneficiaría más de unificarlos en un único repositorio.

Las tres bibliotecas que lo componen tienen roles distintos y complementarios:

- **Thrust** — algoritmos paralelos de alto nivel (`sort`, `reduce`, `transform`). Es la capa más amigable para el programador.
- **CUB** — primitivas optimizadas a nivel de device/block/warp. Es la capa de bajo nivel que Thrust usa internamente.
- **libcudacxx** — implementación de la biblioteca estándar de C++ (`std::`) compatible con código CUDA, para usar en kernels.

## ¿Cuándo fue la última actualización?

La última versión del paquete Python `cuda-cccl` fue la **0.4.2**, publicada el **9 de diciembre de 2025**.

En cuanto a la versión C++, **CCCL 3.0** es la primera versión mayor desde la unificación, e incluye más de un año de trabajo enfocado en limpieza, consolidación y modernización del código. Requiere **C++17 o superior** y **CUDA Toolkit 12.0** como mínimo.

> El repositorio original `github.com/nvidia/thrust` fue archivado el **21 de marzo de 2024** y es ahora de solo lectura. Thrust pasó a formar parte del repositorio unificado `github.com/nvidia/cccl`.

## Thrust dentro de CCCL

Thrust es la biblioteca de algoritmos paralelos en C++ que inspiró la introducción de algoritmos paralelos en la biblioteca estándar de C++. Su interfaz de alto nivel mejora significativamente la productividad del programador y permite portabilidad de rendimiento entre GPUs y CPUs multicore, construyendo sobre frameworks establecidos como CUDA, TBB y OpenMP.

Al estar ahora dentro de CCCL, Thrust comparte infraestructura con CUB y libcudacxx, lo que elimina redundancias y permite que las tres bibliotecas evolucionen de forma coordinada.

## CUDA puro vs Thrust — diferencias clave

| Aspecto | CUDA puro | Thrust / CCCL |
|---|---|---|
| Nivel de abstracción | Bajo — kernels, threads, bloques | Alto — algoritmos como `sort`, `reduce` |
| Gestión de memoria | Manual (`cudaMalloc`, `cudaFree`) | Automática con `device_vector` |
| Curva de aprendizaje | Pronunciada | Muy similar a STL de C++ |
| Control del hardware | Total | Limitado (Thrust decide la implementación) |
| Portabilidad CPU/GPU | No — solo GPU | Sí — mismo código corre en CPU y GPU |
| Cuándo usarlo | Kernels customizados, máxima optimización | Operaciones estándar, prototipado rápido |

La diferencia práctica más importante para este proyecto: con CUDA puro se escribe el kernel de hashing manualmente, pero se puede usar Thrust para las partes auxiliares como manejar vectores de nonces o ordenar resultados, sin perder rendimiento.

## ¿Hace falta instalar algo adicional para usar Thrust?

No. Thrust está incluido en el NVIDIA HPC SDK y en el CUDA Toolkit. Si se tiene uno de esos SDKs instalados, no se necesitan instalaciones adicionales ni flags de compilador especiales. En Google Colab con GPU T4 también viene preinstalado.

Para incluirlo manualmente desde el repositorio:

```bash
git clone https://github.com/NVIDIA/cccl.git
nvcc -Icccl/thrust -Icccl/libcudacxx/include -Icccl/cub main.cu -o main
```

## Ejemplo básico con Thrust (sección Vectors)

```cpp
#include <thrust/host_vector.h>
#include <thrust/device_vector.h>
#include <thrust/generate.h>
#include <thrust/sort.h>
#include <thrust/copy.h>
#include <thrust/random.h>
#include <cstdio>


int main() {
    // Generar números aleatorios en CPU
    thrust::default_random_engine rng(1337);
    thrust::uniform_int_distribution<int> dist;
    thrust::host_vector<int> h_vec(32 << 20);
    thrust::generate(h_vec.begin(), h_vec.end(), [&] { return dist(rng); });

    // Transferir a GPU y ordenar
    thrust::device_vector<int> d_vec = h_vec;
    thrust::sort(d_vec.begin(), d_vec.end());

    // Transferir de vuelta a CPU
    thrust::copy(d_vec.begin(), d_vec.end(), h_vec.begin());

    printf("Ordenamiento completado. Primeros 5: %d %d %d %d %d\n",
        h_vec[0], h_vec[1], h_vec[2], h_vec[3], h_vec[4]);
}
```

Este ejemplo muestra la filosofía central de Thrust: el código es casi idéntico a usar `std::sort` de la STL, pero la ejecución ocurre en la GPU de forma transparente.
Modifique un poco el ejemplo para que imprima por pantalla el resultado.

## Referencias

- Repositorio CCCL: https://github.com/NVIDIA/cccl
- Repositorio Thrust archivado: https://github.com/NVIDIA/thrust
- Documentación Thrust dentro de CCCL: https://github.com/NVIDIA/cccl/blob/main/thrust/README.md
- Anuncio de unificación: https://github.com/NVIDIA/cccl/discussions/520
