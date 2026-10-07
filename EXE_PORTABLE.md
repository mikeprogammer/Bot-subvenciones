# Ejecutable de Windows

El archivo de distribución es `dist/BotSubvenciones.exe`. Contiene Python, la interfaz gráfica y las dependencias. No requiere instalar Python ni copiar el código del proyecto. Está dirigido a Windows de 64 bits; no es un ejecutable para macOS o Linux.

En cada PC se necesita Brave instalado, conexión a Internet, un certificado FNMT disponible en Windows/Brave y acceso a la hoja de Google. El archivo externo que se selecciona es **credentials.json**, un cliente OAuth de escritorio; no credentials.exe.

## Primera ejecución

1. Copia el EXE a una carpeta del equipo y ábrelo.
2. Selecciona el JSON OAuth descargado de Google Cloud. No se incluye dentro del EXE.
3. Pega la URL completa de Sheets con su pestaña `gid`.
4. Deja Brave vacío para detección automática o selecciona `brave.exe`.
5. Selecciona la carpeta donde guardar los resultados y comprueba los nombres de columnas.
6. Pulsa **Probar lectura de Sheets** y autoriza Google en el Brave habitual.
7. Pulsa **Consultar y crear Excel**. Completa FNMT en la ventana automatizada y pulsa **Ya veo el formulario FNMT** cuando esté el formulario de consulta.

Cada ejecución genera un Excel distinto. El botón **Abrir último Excel** abre el resultado. Si hay un error por fila, conserva lo procesado y detiene el lote para revisarlo. **Detener** espera a que finalice la operación actual; la autorización OAuth puede tardar hasta cinco minutos.

## Datos que se guardan en el equipo

La aplicación guarda opciones, tokens OAuth y el perfil propio de Brave en `%LOCALAPPDATA%\BotSubvenciones`. No necesita escribir junto al EXE. Los Excel se guardan en la carpeta que elijas. No almacena contraseñas de Google ni exporta la clave privada FNMT.

Al enviar el EXE a otra persona no se envían tus opciones ni tus tokens. Esa persona necesita seleccionar sus credenciales OAuth o un cliente compartido de forma autorizada, y autorizar su cuenta. Si la app OAuth está en Testing, añade esa cuenta como usuario de prueba; también debe tener acceso a la hoja. Consulta [GOOGLE_API.md](GOOGLE_API.md).

Por tanto, el programa es un único EXE portable, pero no incluye por sí mismo el acceso a Google ni el certificado del nuevo ordenador. No copies tu perfil de navegador o token para evitar la autorización del otro equipo.

## Compilar de nuevo

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build_exe.ps1
```

Se empaquetan únicamente el programa y dependencias. `credentials.json`, `config.json`, perfiles, tokens y resultados no se añaden como recursos del ejecutable.

## Validación de esta entrega

El EXE se compiló y se copió a una carpeta separada sin el código ni el entorno virtual. Su comprobación de arranque terminó con código 0 y verificó interfaz Tk, controlador Playwright, bibliotecas de Google y zona horaria Europe/Madrid. También se comprobó que no incluye archivos de credenciales, tokens ni perfiles.

El lote de cinco consultas se había validado con el programa Python y Brave. La interfaz empaquetada aún requiere una prueba de usuario con OAuth/FNMT, y no se ha probado en un segundo PC. El EXE no está firmado digitalmente.

## Actualización por cierre de Brave

Si la primera fila registra `TargetClosedError`, la conexión con la pestaña o navegador terminó antes de obtener una respuesta. El Excel por sí solo no identifica si cerró el proceso de Brave o su controlador.

La versión `BotSubvenciones_1_1.exe` conserva la pestaña autenticada y usa Neteja para limpiar el resultado entre filas. Muestra el motivo de error en la interfaz y guarda un archivo `.diagnostico.txt` junto al Excel cuando falla una consulta. El diagnóstico puede contener rutas y detalles de sesión; revísalo antes de compartirlo. Mantén abierta la ventana automatizada durante todo el lote.

La compilación final 1.1 pasó una prueba de cinco consultas contra un formulario local en Brave, ejecutada desde una carpeta separada. El proceso terminó con código 0 y mantuvo la pestaña abierta durante las consultas. Las 17 pruebas locales pasan. Esta comprobación no usa FNMT ni la intranet y no determina todavía por qué Brave se cerró solo en el caso comunicado.
