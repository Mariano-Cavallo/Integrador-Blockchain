# CUDA - Setup y configuración

## Entorno utilizado

- **Sistema operativo:** Windows 11 Pro
- **IDE:** Visual Studio 2022 Community
- **Compilador CUDA:** NVCC (CUDA Toolkit 12.6)
- **Compilador C++:** MSVC (cl.exe) — Visual Studio 2022, v14.44.35207
- **Shell:** PowerShell

## Hardware

- **GPU:** NVIDIA GeForce GTX 1660 Ti (6 GB VRAM)
- **Driver NVIDIA:** 591.86
- **CUDA Version (driver):** 13.1

## Setup

### Herramientas instaladas

1. **Visual Studio 2022 Community** con el workload *Desktop development with C++*
2. **CUDA Toolkit 12.6** — descargado desde el sitio oficial de NVIDIA

### Integración CUDA con Visual Studio

Los archivos de integración de MSBuild no se copian automáticamente durante la instalación del CUDA Toolkit. Se copiaron manualmente ejecutando (como Administrador):

```powershell
Copy-Item "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\extras\visual_studio_integration\MSBuildExtensions\*" `
    "C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Microsoft\VC\v170\BuildCustomizations\" -Force
```

### Compilación desde línea de comandos

Debido a un problema con la resolución del compilador host (detallado abajo), es necesario especificar el path de `cl.exe` explícitamente. Se provee el script `compile.ps1` para simplificar esto:

```powershell
.\compile.ps1 .\archivo.cu
```

### Compilación desde Visual Studio 2022

1. Crear un nuevo proyecto: *Empty Project (C++)*
2. Agregar el archivo `.cu`: clic derecho en *Source Files → Add → Existing Item*
3. Activar la integración CUDA: clic derecho en el proyecto → *Build Dependencies → Build Customizations → tildar CUDA 12.6*
4. Configurar el tipo del archivo `.cu`: clic derecho en el archivo → *Properties → Item Type → CUDA C/C++*
5. Compilar y ejecutar: `Ctrl+F5`

## Problemas encontrados y soluciones

### 1. Plantilla "CUDA Runtime Project" no aparece en Visual Studio

**Problema:** Al crear un nuevo proyecto en Visual Studio, la plantilla *CUDA Runtime Project* no estaba disponible.

**Causa:** CUDA Toolkit 12.6 (y versiones recientes) ya no instala las plantillas de proyecto para Visual Studio. Los archivos de integración de MSBuild tampoco se copian automáticamente.

**Solución:** Copiar manualmente los archivos de MSBuild desde el directorio del CUDA Toolkit al directorio de BuildCustomizations de Visual Studio (ver sección Setup). El proyecto se configura manualmente con un *Empty Project* de C++.

---

### 2. `cudafe++` crashea con ACCESS_VIOLATION (0xC0000005)

**Problema:** Al compilar con `nvcc` desde la terminal, el proceso `cudafe++` (frontend de CUDA) terminaba con un error de acceso a memoria:

```
nvcc error   : 'cudafe++' died with status 0xC0000005 (ACCESS_VIOLATION)
```

**Causa:** `nvcc` no resolvía correctamente el path del compilador host `cl.exe`, incluso cuando estaba disponible en el PATH de la terminal. Esto provocaba un comportamiento inesperado en `cudafe++`.

**Solución:** Especificar el path del compilador host explícitamente mediante el flag `-ccbin`:

```powershell
nvcc archivo.cu -o output -ccbin "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64"
```

El script `compile.ps1` incluido en este repositorio automatiza esto.
