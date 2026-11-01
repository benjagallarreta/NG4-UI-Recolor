# Rollback del mod de color de UI: restaura los archivos originales y verifica sus SHA256.
# Uso: pwsh -File "C:\Users\Administrator\Desktop\NG4_UI_Color\backup\restore.ps1" [-Game "E:\Juegos\NINJA GAIDEN 4"]
param([string]$Game = 'E:\Juegos\NINJA GAIDEN 4')
$ErrorActionPreference = 'Stop'
$backup = Join-Path $PSScriptRoot 'original'
$assets = Join-Path $Game 'Assets'
if (-not (Test-Path -LiteralPath (Join-Path $assets '@patch_image0.csv'))) { throw "No se encontro el juego en: $Game" }
$manifest = Get-Content (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json

foreach ($f in $manifest) {
    $src = Join-Path $backup $f.Name
    if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -ne $f.SHA256) { throw "Backup corrupto: $($f.Name)" }
}
foreach ($f in $manifest) {
    Copy-Item -LiteralPath (Join-Path $backup $f.Name) -Destination (Join-Path $assets $f.Name) -Force
    $h = (Get-FileHash -LiteralPath (Join-Path $assets $f.Name) -Algorithm SHA256).Hash
    if ($h -ne $f.SHA256) { throw "Fallo al restaurar $($f.Name)" }
    Write-Host "Restaurado OK: $($f.Name)"
}
Write-Host "Rollback completo."
