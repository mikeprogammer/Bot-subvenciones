param([string]$Name = 'BotSubvenciones')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$botRuntime = & .\.venv\Scripts\python.exe -c "import sys; print(sys.base_prefix)"
$env:TCL_LIBRARY = Join-Path $botRuntime 'tcl\tcl8.6'
$env:TK_LIBRARY = Join-Path $botRuntime 'tcl\tk8.6'
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name $Name --collect-all playwright --collect-all googleapiclient --collect-all tzdata --collect-all certifi app.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
