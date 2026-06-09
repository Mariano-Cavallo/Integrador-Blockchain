param(
    [Parameter(Mandatory=$true)]
    [string]$file
)

$ccbin = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64"
$output = [System.IO.Path]::GetFileNameWithoutExtension($file)

nvcc $file -o $output -ccbin $ccbin

if ($?) {
    & ".\$output.exe"
}
