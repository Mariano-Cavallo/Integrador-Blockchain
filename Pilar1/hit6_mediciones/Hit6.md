# Hit #6 — Longitudes de prefijo en CUDA HASH

## Setup

- **GPU**: NVIDIA GTX 1660 Ti (1536 CUDA cores, arquitectura Turing sm_75)
- **Cadena base**: `hola`
- **Programa**: `hit5_bruteforce/bruteforce_gpu.exe`
- **Configuración del kernel**: 512 bloques × 256 threads = 131.072 nonces por tanda

---

## Resultados

| Longitud prefijo | Prefijo    | Nonce encontrado | Input          | MD5 resultado                      | Tiempo (s) | Tandas | Nonces probados |
|:----------------:|:----------:|:----------------:|:--------------:|:----------------------------------:|:----------:|:------:|:---------------:|
| 1                | `0`        | 2.862            | hola2862       | `0a689e9d...`                      | 0.001      | 1      | ~3K             |
| 2                | `00`       | 2.879            | hola2879       | `006a5b20...`                      | 0.001      | 1      | ~3K             |
| 3                | `000`      | 18.010           | hola18010      | `0001896e...`                      | 0.001      | 1      | ~18K            |
| 4                | `0000`     | 66.995           | hola66995      | `000020ca...`                      | 0.001      | 1      | ~67K            |
| 5                | `00000`    | 155.644          | hola155644     | `00000fa6...`                      | 0.001      | 2      | ~156K           |
| 6                | `000000`   | 22.700.501       | hola22700501   | `000000cf...`                      | 0.036      | 174    | ~22.7M          |
| 7                | `0000000`  | 107.863.415      | hola107863415  | `00000006...`                      | 0.179      | 823    | ~107.9M         |
| 8                | `00000000` | 1.259.646.227    | hola1259646227 | `00000000662231cbf09e2c2d316e4c31` | 1.866      | 9.611  | ~1.260M         |
| 9                | `000000000`| 113.948.418.761  | hola113948418761 | `000000000c56a96be68963e0135f2c58` | 166.842  | 869.358 | ~113.948M      |

---

## Prefijo más largo encontrado

**9 ceros** (`000000000`) en **166.84 segundos** (~2 minutos 47 segundos), probando ~113.948 millones de nonces.

Se detuvo ahí porque 10 ceros requeriría del orden de 44 minutos (proyección basada en la relación ×16 por cada dígito adicional).

---

## Relación entre longitud del prefijo y tiempo

Cada dígito hexadecimal adicional en el prefijo multiplica el espacio de búsqueda por **16** (hay 16 posibles valores por nibble: 0–f). Por lo tanto, el tiempo esperado crece **exponencialmente**:

```
T(n) ≈ T(1) × 16^(n-1)
```

### Datos medidos vs esperado teórico (factor ×16 por nivel)

| Longitud | Tiempo medido (s) | Factor real respecto al anterior |
|:--------:|:-----------------:|:--------------------------------:|
| 1–5      | ~0.001            | < 16× (todos en la misma tanda)  |
| 6        | 0.036             | >>16× (salto desde tanda única)  |
| 7        | 0.179             | ~5×                              |
| 8        | 1.866             | ~10×                             |
| 9        | 166.842           | ~89×                             |

> Los niveles 1–5 aparecen con el mismo tiempo (0.001 s) porque todos caben en 1–2 tandas de 131.072 nonces — la GPU los resuelve antes de que el timer tenga resolución visible. A partir del nivel 6 el crecimiento se vuelve claramente exponencial.

### Proyección para prefijos más largos

| Longitud | Tiempo estimado         |
|:--------:|:-----------------------:|
| 10       | ~44 minutos             |
| 11       | ~12 horas               |
| 12       | ~8 días                 |
| 13       | ~130 días               |

---

## Comparativa CPU vs GPU

- **CPU**: Python secuencial con `hashlib.md5` (un solo hilo)
- **GPU**: GTX 1660 Ti, 512 bloques × 256 threads = 131.072 nonces por tanda

| Longitud prefijo | Nonce       | Tiempo CPU (s) | Tiempo GPU (s) | Speedup GPU/CPU |
|:----------------:|:-----------:|:--------------:|:--------------:|:---------------:|
| 1                | 28          | < 0.001        | 0.001          | ~1×             |
| 2                | 28          | < 0.001        | 0.001          | ~1×             |
| 3                | 28          | < 0.001        | 0.001          | ~1×             |
| 4                | 66.995      | 0.061          | 0.001          | ~61×            |
| 5                | 155.644     | 0.143          | 0.001          | ~143×           |
| 6                | 22.700.501  | 20.973         | 0.036          | **~582×**       |

> Prefijos 1–3: la CPU encuentra nonce=28 (el mínimo, búsqueda secuencial) mientras la GPU encuentra nonces más grandes porque prueba rangos en paralelo en orden no determinístico. Ambos resultados son válidos.

> Para prefijo 6, la CPU tardó **21 segundos** vs **0.036 segundos** de la GPU — casi 600× más rápida. La ventaja de la GPU crece con la dificultad porque tiene más threads explorando el espacio en paralelo.

---

## Conclusión

La relación entre la longitud del prefijo y el tiempo de búsqueda es **exponencial base 16**: cada carácter hex adicional multiplica el tiempo esperado por ~16. Esto es el fundamento del ajuste de dificultad en blockchains reales (Bitcoin ajusta la dificultad cada 2016 bloques para mantener un tiempo de bloque de ~10 minutos). A mayor prefijo requerido, exponencialmente más difícil minar un bloque válido.

La GPU permite explorar millones de nonces por segundo (la GTX 1660 Ti procesó ~683 millones de hashes/segundo en la prueba de 9 ceros), lo que la hace órdenes de magnitud más eficiente que una CPU para esta tarea.
