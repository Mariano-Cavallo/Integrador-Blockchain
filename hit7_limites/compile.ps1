$ccbin = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64"

nvcc limites_gpu.cu -o limites_gpu -ccbin $ccbin -O2

if ($?) {
    Write-Host "Compilado OK. Uso: .\limites_gpu.exe <cadena> <prefijo_hex> <nonce_min> <nonce_max>"
}
