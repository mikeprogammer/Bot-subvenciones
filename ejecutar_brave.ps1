$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$botPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $botPython)) {
    throw 'Falta instalar el entorno .venv. Consulta README.md.'
}
& $botPython bot.py @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
