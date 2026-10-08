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

## Selección automática FNMT — versión 1.2

La opción **Seleccionar automáticamente FNMT de persona física** está activada por defecto. Busca certificados del usuario actual y del equipo en Windows, con clave privada, dentro de sus fechas de vigencia y con la política FNMT personal `1.3.6.1.4.1.5734.3.10.1` (o la antigua Clase 2 `1.3.6.1.4.1.5734.3.5`). Excluye los certificados de representante y los caducados. No comprueba revocación; el servicio y el navegador validan el certificado durante el acceso.

Si solo hay uno, lo detecta automáticamente. Si hay varios, muestra sus nombres, fechas y huellas: copia la huella elegida al campo **Huella FNMT**. Si dos certificados vigentes tienen el mismo titular y emisor, la política del navegador no puede distinguirlos; usa la selección manual desmarcando la opción.

Antes de abrir Brave o Chrome, añade reglas `AutoSelectCertificateForUrls` al registro del usuario actual, filtradas por el nombre exacto del titular y del emisor. Usa los orígenes HTTPS de acceso Cl@ve indicados en la interfaz, sin comodines. Los valores iniciales son `https://se-pasarela-ident.clave.gob.es` y `https://se-pasarela-identclave.gob.es`; si el selector de certificados muestra otro dominio, sustituye estos valores por el origen exacto mostrado y vuelve a ejecutar. No está verificado qué origen usa actualmente el acceso CAIB en la sesión del usuario.

Pulsa **Entra** y el acceso con certificado como antes. La selección del certificado se hará automáticamente si el navegador admite y aplica la regla. Un PIN o una confirmación de uso de la clave privada pueden seguir requiriendo intervención. Pulsa **Ya veo el formulario FNMT** cuando aparezca el formulario.

La regla afecta a los perfiles de ese navegador del usuario mientras se ejecuta el lote; el programa retira únicamente sus entradas al terminar, incluso si falla el lanzamiento. No modifica las reglas existentes ni exporta claves privadas. Un cierre forzado del proceso o del equipo puede impedir la retirada: en ese caso revisa `HKCU\Software\Policies\BraveSoftware\Brave\AutoSelectCertificateForUrls` (o `Google\Chrome`). Las políticas administradas del equipo pueden prevalecer; se pueden revisar en `brave://policy` o `chrome://policy`.

Para otro ordenador sigue siendo necesario tener instalado allí el certificado personal con su clave privada. El EXE no lo transporta.

Referencias: [políticas de Brave](https://support.brave.app/hc/en-us/articles/360039248271-Group-Policy), [definición oficial de Chromium](https://raw.githubusercontent.com/chromium/chromium/main/components/policy/resources/templates/policy_definitions/ContentSettings/AutoSelectCertificateForUrls.yaml), [tipos de certificados FNMT por OID](https://www.sede.fnmt.gob.es/en/preguntas-frecuentes/-/asset_publisher/5a9kmeLaGgXw/content/1669-que-es-eso-de-los-oids-).

Validación: 22 pruebas locales, incluidas exclusión de representantes y caducados, rechazo de selección ambigua, filtros por titular/emisor y retirada de reglas sin borrar las existentes. En la sesión de Windows del usuario se detectaron dos certificados personales vigentes, con titulares/emisores distintos; será necesario elegir una huella una vez. La autenticación FNMT real de la versión 1.2 queda pendiente de probar.

El EXE 1.2 pasó la comprobación de arranque con código 0: interfaz, Playwright, Google API, zona horaria y lectura del almacén Windows. El detector empaquetado también encontró los dos certificados personales.
