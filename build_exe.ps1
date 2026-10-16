param([string]$Name = 'BotSubvenciones_1_5_1')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$botRuntime = & .\.venv\Scripts\python.exe -c "import sys; print(sys.base_prefix)"
$env:TCL_LIBRARY = Join-Path $botRuntime 'tcl\tcl8.6'
$env:TK_LIBRARY = Join-Path $botRuntime 'tcl\tk8.6'
& .\.venv\Scripts\python.exe -c "import tkinter; tkinter.Tcl()" 2>$null
if ($LASTEXITCODE -ne 0) {
    $botTclFallback = Join-Path $PSScriptRoot 'build\v1_5_tcl'
    if (Test-Path -LiteralPath (Join-Path $botTclFallback '_tcl_data\init.tcl')) {
        $env:TCL_LIBRARY = Join-Path $botTclFallback '_tcl_data'
        $env:TK_LIBRARY = Join-Path $botTclFallback '_tk_data'
    }
}
& .\.venv\Scripts\python.exe -c "import tkinter; t=tkinter.Tk(); t.withdraw(); t.destroy()"
if ($LASTEXITCODE -ne 0) { throw "La interfaz Tcl/Tk no funciona en este entorno de compilaciÃ³n." }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name $Name --distpath dist --workpath build/pyinstaller --specpath build --collect-data customtkinter --collect-all playwright --collect-all googleapiclient --collect-all tzdata --collect-all certifi app.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
