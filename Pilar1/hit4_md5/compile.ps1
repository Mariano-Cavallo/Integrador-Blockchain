$ccbin = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64"

nvcc md5_gpu.cu -o md5_gpu -ccbin $ccbin

if ($?) {
    Write-Host "Compilado OK. Ejecuta con: .\md5_gpu.exe <string>"
}
