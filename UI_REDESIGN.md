# Interfaz CustomTkinter

La presentación se encuentra en `ui.py`. `app.py` conserva la configuración,
los callbacks, la cola de eventos y los hilos. No se han modificado `bot.py`,
`sheets_api.py`, `auto_login.py` ni `fnmt.py` durante este rediseño.

Cambios del controlador: creación de la ventana CTk; construcción de la UI
mediante Interface; validación visual antes de start; adaptación de progress y
combobox manteniendo los datos existentes; mensajes de estado y error en línea;
progreso indeterminado durante la espera; estado final y acceso a resultados.
Los nombres y parámetros de las funciones existentes se conservan. La selección
automática del único certificado y la configuración persistida siguen iguales.
La validación crea la carpeta de salida si no existe; no ejecuta consultas.

Instalación y ejecución (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Compilación:

```powershell
.\build_exe.ps1
```

El script utiliza `--onedir` y `--collect-data customtkinter`. Distribuir la
carpeta completa `dist\BotSubvenciones_1_5_1`, incluido `_internal`, no solamente
el EXE. Esto sustituye la distribución anterior de un único ejecutable siguiendo
las instrucciones de empaquetado de CustomTkinter:
https://customtkinter.tomschimansky.com/documentation/packaging/

Comando equivalente:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name BotSubvenciones_1_5_1 --distpath dist --workpath build/pyinstaller --specpath build --collect-data customtkinter --collect-all playwright --collect-all googleapiclient --collect-all tzdata --collect-all certifi app.py
```

Tema claro inicial; el interruptor cambia a oscuro durante la sesión. Avanzado
empieza cerrado y se abre al detectar un campo inválido. Los iconos utilizan
caracteres del sistema, sin dependencia de Pillow. El registro conserva el
archivo de diagnóstico original; Limpiar solo borra su presentación en pantalla.

Comprobaciones: creación de widgets, tema oscuro, despliegue de Avanzado,
validación, log y adaptadores con escalados de widgets 1, 1.25 y 1.5. Esto no
sustituye una revisión visual en monitores configurados a esos DPI ni una
consulta real con OAuth/FNMT. No se ha recompilado el EXE con este rediseño.
