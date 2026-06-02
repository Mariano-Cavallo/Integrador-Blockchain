# Cierre Etapa Inicial — Batería de Tests CPU vs GPU

## Setup

| | |
|---|---|
| **GPU** | NVIDIA GTX 1660 Ti — 1536 CUDA cores, Turing sm_75 |
| **CPU** | Python secuencial, `hashlib.md5` (1 hilo) |
| **Programas GPU** | `hit5_bruteforce/bruteforce_gpu.exe`, `hit7_limites/limites_gpu.exe` |
| **Programas CPU** | `hit5_bruteforce/bruteforce_cpu.py`, `hit7_limites/limites_cpu.py` |
| **Kernel GPU** | 512 bloques × 256 threads = 131.072 nonces por tanda |

---

## Grupo 1 — Distintas cadenas, prefijo fijo `000`

Verifica que el algoritmo funciona independientemente de la cadena base.

| Cadena      | CPU Nonce | CPU Hash (primeros 8) | CPU Tiempo | GPU Nonce | GPU Hash (primeros 8) | GPU Tiempo | Hashes iguales |
|:-----------:|:---------:|:---------------------:|:----------:|:---------:|:---------------------:|:----------:|:--------------:|
| `hola`      | 28        | `000e93d6`            | < 0.001 s  | 18010     | `0001896e`            | 0.001 s    | ✓ (distintos nonces, ambos válidos) |
| `bitcoin`   | 18260     | `0007dc53`            | 0.016 s    | 19586     | `00082e08`            | 0.001 s    | ✓ |
| `abc`       | 2196      | `000d69e0`            | 0.002 s    | 2196      | `000d69e0`            | 0.001 s    | ✓ (mismo nonce) |
| `blockchain`| 2521      | `0005f6c1`            | 0.002 s    | 20822     | `000ef677`            | 0.001 s    | ✓ |
| `cuda`      | 7745      | `000a7baf`            | 0.007 s    | 20076     | `0008b272`            | 0.001 s    | ✓ |

> **Nota**: GPU y CPU pueden encontrar nonces distintos porque la CPU busca secuencialmente desde 0 (encuentra el mínimo) mientras la GPU prueba 131.072 en paralelo y devuelve el primero en terminar. Ambos son correctos — el hash empieza con `000` en todos los casos.

---

## Grupo 2 — Cadena fija `hola`, distintas longitudes de prefijo

Verifica la escalabilidad con la dificultad y la correctitud del hash en ambas implementaciones.

| Prefijo    | Long. | CPU Nonce   | GPU Nonce   | CPU MD5                            | GPU MD5                            | CPU Tiempo  | GPU Tiempo | Speedup  |
|:----------:|:-----:|:-----------:|:-----------:|:----------------------------------:|:----------------------------------:|:-----------:|:----------:|:--------:|
| `0`        | 1     | 28          | 2862        | `000e93d6...`                      | `0a689e9d...`                      | < 0.001 s   | 0.001 s    | ~1×      |
| `00`       | 2     | 28          | 2879        | `000e93d6...`                      | `006a5b20...`                      | < 0.001 s   | 0.001 s    | ~1×      |
| `000`      | 3     | 28          | 18010       | `000e93d6...`                      | `0001896e...`                      | < 0.001 s   | 0.001 s    | ~1×      |
| `0000`     | 4     | 66995       | 66995       | `000020ca72aab03d568ae0b678d4302b` | `000020ca72aab03d568ae0b678d4302b` | 0.060 s     | 0.001 s    | **~60×** |
| `00000`    | 5     | 155644      | 155644      | `00000fa637224dfdb1a1adc61894424f` | `00000fa637224dfdb1a1adc61894424f` | 0.144 s     | 0.001 s    | **~144×**|
| `000000`   | 6     | 22700501    | 22700501    | `000000cf143a07bd2f099156cb4b1118` | `000000cf143a07bd2f099156cb4b1118` | 20.889 s    | 0.037 s    | **~565×**|

> Para prefijos de longitud 4 en adelante, CPU y GPU encuentran el **mismo nonce** porque el espacio de búsqueda ya supera una tanda GPU (131.072) y la GPU también empieza desde 0. Los hashes son idénticos bit a bit.

---

## Grupo 3 — Hit #7: búsqueda con rango limitado

Verifica el comportamiento con rango acotado: casos con solución, sin solución, rango exacto.

| Cadena    | Prefijo | Rango            | CPU resultado              | GPU resultado              | CPU Tiempo | GPU Tiempo | Coinciden |
|:---------:|:-------:|:----------------:|:--------------------------:|:--------------------------:|:----------:|:----------:|:---------:|
| `hola`    | `0000`  | [0, 100000]      | Nonce 66995 `000020ca...`  | Nonce 66995 `000020ca...`  | 0.075 s    | 0.001 s    | ✓ |
| `hola`    | `0000`  | [0, 1000]        | **No encontrado**          | **No encontrado**          | 0.001 s    | 0.001 s    | ✓ |
| `hola`    | `0000`  | [67000, 200000]  | Nonce 94397 `0000b972...`  | Nonce 94397 `0000b972...`  | 0.028 s    | 0.001 s    | ✓ |
| `hola`    | `0000`  | [66995, 66995]   | Nonce 66995 `000020ca...`  | Nonce 66995 `000020ca...`  | < 0.001 s  | 0.001 s    | ✓ |
| `bitcoin` | `000`   | [0, 50000]       | Nonce 18260 `0007dc53...`  | Nonce 19586 `00082e08...`  | 0.018 s    | 0.001 s    | ✓ (nonces distintos, ambos válidos) |
| `bitcoin` | `000`   | [0, 5000]        | **No encontrado**          | **No encontrado**          | 0.005 s    | 0.001 s    | ✓ |

---

## Grupo 4 — Prefijos no-cero

Verifica que el algoritmo no está hardcodeado para buscar solo ceros.

| Prefijo | CPU Nonce | GPU Nonce | MD5 (GPU)                          | CPU Tiempo | GPU Tiempo | Speedup  |
|:-------:|:---------:|:---------:|:----------------------------------:|:----------:|:----------:|:--------:|
| `aaa`   | 343       | 14206     | `aaa019ed14007c751615ec89fbd79d22` | < 0.001 s  | 0.001 s    | ~1×      |
| `fff`   | 1255      | 1255      | `fff6f6e1a077f2bad0c8844904cc5847` | 0.001 s    | 0.001 s    | ~1×      |
| `abc`   | 368       | 22228     | `abcbbc2473b20b502b83553fcbf3bb6b` | < 0.001 s  | 0.001 s    | ~1×      |
| `1234`  | 161689    | 161689    | `1234067fffd3b18d82c598f965cfe37f` | 0.150 s    | 0.001 s    | **~150×**|
| `dead`  | 122086    | 122086    | `dead2c685300f56e8dad13deabf6a60e` | 0.109 s    | 0.001 s    | **~109×**|

---

## Resumen comparativo

| Métrica                        | CPU (Python)          | GPU (CUDA GTX 1660 Ti)     |
|:------------------------------:|:---------------------:|:--------------------------:|
| Throughput estimado            | ~1M hashes/s          | ~683M hashes/s             |
| Speedup promedio (prefijo ≥4)  | 1×                    | **100×–600×**              |
| Correctitud                    | ✓ Siempre el nonce mínimo | ✓ Nonce válido (no mínimo) |
| Detección "sin solución"       | ✓                     | ✓                          |
| Prefijos no-cero               | ✓                     | ✓                          |
| Determinismo                   | ✓ Siempre el mismo resultado | ✗ Varía según scheduling de warps |

### Speedup vs longitud de prefijo

```
Prefijo  Speedup GPU/CPU
───────────────────────
1-3      ~1×   (ambos instantáneos, overhead de CUDA domina)
4        ~60×
5        ~144×
6        ~565×
7+       >1000× (proyectado)
```

El speedup crece con la dificultad porque la GPU escala horizontalmente
(más nonces en paralelo) mientras la CPU siempre evalúa uno por vez.

---

## Conclusiones

1. **Correctitud garantizada**: en todos los tests, los hashes producidos por GPU y CPU son MD5 válidos que respetan el prefijo pedido. Cuando el nonce coincide, el hash es idéntico bit a bit.

2. **No determinismo de la GPU**: para prefijos cortos (1–3), la CPU encuentra el nonce mínimo mientras la GPU encuentra uno mayor porque sus threads no terminan en orden. Esto es normal y esperado en minería paralela — lo importante es que el resultado sea válido, no que sea el mínimo.

3. **Escalabilidad exponencial del problema**: cada carácter adicional en el prefijo multiplica el espacio de búsqueda por 16. La GPU absorbe este crecimiento mejor que la CPU gracias al paralelismo masivo.

4. **Caso sin solución**: ambas implementaciones detectan correctamente cuando el rango no contiene ningún nonce válido y lo informan sin colgar.

5. **Aplicación a blockchain**: estos tests simulan exactamente el trabajo de un nodo minero. El Hit #7 en particular modela el escenario de pool de minería donde el coordinador asigna rangos de nonces a distintos workers — cada worker prueba su rango y reporta si encontró o no.
