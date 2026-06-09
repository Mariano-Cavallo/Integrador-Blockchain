# PopToken
**Propuesta de caso de uso — sistema de fidelidad sobre blockchain**

**Trabajo Práctico Integrador · Blockchain Distribuida y CUDA**

| | |
|---|---|
| **Alumnos** | Mariano Cavallo Sassi · Valentino Aimale · Lautaro Marino |
| **Fecha** | Junio 2026 |

---

## 01 — Descripción General

### ¿Qué es PopToken?

**PopToken** es un sistema de fidelidad basado en blockchain donde un cine emite tokens digitales a sus clientes como recompensa por la compra de entradas. Estos tokens pueden transferirse libremente entre usuarios y canjearse por entradas gratuitas o productos del cine.

El sistema modela el concepto central de una blockchain: un registro distribuido, inmutable y descentralizado de transferencias de valor entre partes que no necesitan confiar entre sí ni depender de un intermediario central.

---

## 02 — Justificación

### ¿Por qué blockchain?

Los programas de puntos tradicionales son sistemas **centralizados**: el emisor puede modificar o cancelar los puntos unilateralmente, y el usuario no puede transferirlos sin pasar por la plataforma del emisor. Blockchain resuelve esto de forma estructural:

- **Inmutabilidad** — Una vez acreditados, los tokens no pueden ser borrados ni alterados por el cine ni por ningún tercero.
- **Transferibilidad sin intermediarios** — Un usuario puede enviar tokens a otro directamente, sin que el cine intervenga ni autorice la operación.
- **Transparencia** — Cualquier participante puede verificar el saldo de cualquier billetera consultando la cadena.
- **Descentralización real** — No existe una base de datos central que pueda ser hackeada, caída o manipulada.

Esto contrasta con casos como trazabilidad de medicamentos, donde ANMAT actúa como árbitro central confiable y una base de datos centralizada es suficiente. En PopToken **no existe ni se necesita un árbitro central**: la blockchain cumple ese rol.

---

## 03 — Actores

### Actores del Sistema

| Actor | Rol |
|---|---|
| `Cine (emisor)` | Genera y acredita tokens al usuario cuando compra una entrada |
| `Usuario` | Acumula tokens, los transfiere a otros usuarios o los canjea por beneficios |
| `Minero (CUDA / CPU)` | Valida e incorpora bloques de transacciones a la cadena mediante Proof of Work |
| `Nodo Coordinador (NCT)` | Organiza transacciones pendientes, forma bloques y distribuye tareas de minado |

---

## 04 — Modelo de Datos

### Tipos de Transacción

El sistema contempla cuatro tipos de transacción. Las tres primeras representan operaciones económicas del día a día; la cuarta gestiona la gobernanza de la red.

#### 4.1 Emisión

El cine acredita tokens a un usuario tras la compra de una entrada.

```json
{
  "tipo":      "emision",
  "from":      "Cine_Hoyts_Abasto",
  "to":        "usuario_0x4F3a",
  "tokens":    10,
  "motivo":    "compra_entrada",
  "pelicula":  "Obsesión",
  "timestamp": "2026-06-08T20:15:00Z"
}
```

#### 4.2 Transferencia

Un usuario transfiere tokens a otro directamente, sin intervención del cine.

```json
{
  "tipo":      "transferencia",
  "from":      "usuario_0x4F3a",
  "to":        "usuario_0x9B1c",
  "tokens":    10,
  "timestamp": "2026-06-08T21:00:00Z"
}
```

#### 4.3 Canje

Un usuario gasta tokens para obtener un beneficio (entrada gratis o producto del cine).

```json
{
  "tipo":      "canje",
  "from":      "usuario_0x9B1c",
  "to":        "Cine_Hoyts_Abasto",
  "tokens":    50,
  "beneficio": "entrada_gratis",
  "timestamp": "2026-06-09T18:30:00Z"
}
```

#### 4.4 Autorizar Emisor

Incorpora un nuevo cine a la red como emisor autorizado. Requiere aprobación de la mayoría de los emisores ya existentes.

```json
{
  "tipo":         "autorizar_emisor",
  "solicitante":  "CinePolka_0xF7a1",
  "aprobado_por": ["Hoyts_0xA1b2", "Cinemark_0xC3d4"],
  "timestamp":    "2026-06-08T09:00:00Z"
}
```

---

## 05 — Gobernanza

### Bloque Génesis y Emisores Autorizados

El **bloque génesis** es el primer bloque de la cadena, el único que no tiene predecesor. En PopToken cumple un rol especial: define qué billeteras tienen permiso para emitir tokens. Ninguna otra billetera puede firmar una transacción de tipo `emision`.

| Campo del Génesis | Descripción |
|---|---|
| `previous_hash` | `"0000...0000"` — no tiene bloque anterior por definición |
| `emisores_autorizados` | Lista de billeteras de cines fundadores con permiso de emisión |
| `quorum_requerido` | Cantidad mínima de firmas necesarias para autorizar un nuevo emisor |
| `tokens_por_entrada` | Cantidad de tokens que se acreditan por cada compra de entrada |

```json
{
  "tipo":                "genesis",
  "previous_hash":       "0000000000000000",
  "emisores_autorizados": ["Hoyts_0xA1b2", "Cinemark_0xC3d4"],
  "quorum_requerido":    2,
  "tokens_por_entrada":  10,
  "timestamp":           "2026-01-01T00:00:00Z"
}
```

> Para agregar un nuevo cine a la red una vez que está en funcionamiento, se utiliza la transacción **autorizar_emisor** (sección 4.4). El NCT valida que la cantidad de firmas de aprobación alcance el quórum definido en el génesis. Si se cumple, el nuevo cine queda habilitado a partir del bloque siguiente.

---

## 06 — Estructura

### Estructura de un Bloque

Cada bloque agrupa un conjunto de transacciones pendientes y las ancla a la cadena mediante Proof of Work.

| Campo | Descripción |
|---|---|
| `previous_hash` | Hash del bloque anterior — garantiza el encadenamiento e inmutabilidad |
| `nonce` | Valor encontrado por el minero que resuelve el desafío PoW |
| `timestamp` | Fecha y hora de creación del bloque |
| `transactions` | Lista de transacciones incluidas en el bloque |
| `block_hash` | Hash del bloque actual, calculado sobre todos los campos anteriores |

---

## 07 — Regla de Negocio

### Validación de Saldo

El Nodo Coordinador debe rechazar cualquier transacción de tipo **transferencia** o **canje** donde el usuario no disponga de saldo suficiente.

> El saldo se calcula recorriendo la cadena completa: se suman todas las emisiones y transferencias recibidas, y se restan las transferencias enviadas y los canjes realizados. Esta lógica es equivalente al modelo **UTXO de Bitcoin**.

---

*PopToken · Blockchain Distribuida y CUDA · Junio 2026*