# Bot de consulta de subvenciones

Para utilizar la interfaz sin instalar Python, consulta [EXE_PORTABLE.md](EXE_PORTABLE.md). El ejecutable permite seleccionar el JSON OAuth, la hoja de Sheets, Brave, las columnas y la carpeta de resultados.

Primera versión para Windows, Python 3.10+ y Brave instalado. Lee una pestaña de Google Sheets o un Excel local `.xlsx`, consulta las filas en la intranet y guarda DNI, expediente, estado, anomalías y documentos referenciados en un Excel local. Conserva el texto original y añade columnas para errores técnicos y fila de origen. Guarda después de cada consulta.

## Preparación

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item config.example.json config.json
```

El certificado FNMT debe estar disponible en Windows/Brave. El bot abre un perfil propio en `.brave-bot-profile`. Pulsa **Entra**, autentícate y selecciona el certificado manualmente. No requiere exportar la clave privada ni escribir su contraseña en el código. La compatibilidad con el diálogo FNMT está pendiente de verificar en tu equipo.

## Adaptación a la página real

La dirección de entrada verificada es https://intranet.caib.es/subvenfront/. Los campos facilitados están configurados por `id` o `name`: `titularExpediente`, `titularDocumentoNumero` y `numeroExpedienteCompleto`. El botón se localiza por `button.p-button-success:has-text('Cerca')`, y el resultado por `.mt-3`. Estos dos nombres se interpretan como clases CSS. Si hay varios bloques visibles con contenido `mt-3`, el programa pide afinar el selector mediante un error de consulta. No elige un bloque arbitrario. `config.json` ya contiene la hoja de prueba facilitada y estos selectores.

```powershell
.\.venv\Scripts\python.exe bot.py --inspect
```

Selecciona en la consola la pestaña del formulario. El programa muestra los controles sin sus valores y abre el inspector de Playwright. Puedes usar **Pick locator** para identificar cada elemento y copiar el selector a `config.json`.

- `titular`: checkbox «Soc titular».
- `dni`, `expediente`: los dos campos.
- `buscar`: botón «Cerca» con clase `p-button-success`.
- `resultado`: bloque `.mt-3` cuyo contenido cambia tras la consulta; debe identificar exclusivamente el resultado.

El estado se obtiene de `Estat:` o `Estado:` si existe esa etiqueta; en caso contrario se guarda «No indicado en el texto». Un párrafo que anuncia anomalías no se interpreta como estado administrativo. Las anomalías se separan por guiones de viñeta después de los dos puntos, manteniendo guiones internos como `DOC-123` o `informe-final.pdf`. Se numeran para relacionarlas con la columna de documentos. Se decodifican entidades HTML como `&#x20;` para el análisis, conservando el texto recibido en Texto original.

Las referencias a documentos se extraen primero de encabezados como `Document normalitzat 1: Sol·licitud:` o `Document 2: memòria resum de l'actuació:`. En estos casos se guarda el número y título del documento, manteniendo el motivo completo en Anomalias. También se reconocen menciones explícitas a documento/document, nombres de archivo o enlaces cuyo texto aparece en la anomalía. No se deduce un documento a partir del motivo de la anomalía. Si no se puede identificar, se indica «Sin documento identificable en el texto». No se descargan documentos. Si el documento se identifica por una tabla o código situado fuera de `.mt-3`, hará falta adaptar esa relación con un ejemplo real del formato.

Una sección de anomalías vacía se trata como error. Si la sección no aparece, se indica esa ausencia; no se afirma que el expediente carece de anomalías. El texto original permite revisar la extracción. La interpretación del formato sigue pendiente de comprobar con un ejemplo de la página autenticada.

La prueba con las cinco filas ficticias de Sheets se realizó mediante el navegador integrado, con la sesión FNMT autenticada. Las cinco devolvieron `No s'ha trobat cap expedient amb aquestes dades`. Ese mensaje está en `.resultado-error` y se configura junto con `.mt-3`. Se exporta «Expediente no encontrado» como resultado de búsqueda y «No disponibles: expediente no encontrado» en anomalías; no representa un estado administrativo. El flujo completo Python con Sheets API y Brave/FNMT se verificó el 7 de octubre de 2026: cinco filas procesadas sin errores técnicos y un Excel nuevo. Los resultados de expedientes existentes siguen pendientes de validar.

No copies expresiones Python como `page.get_by_role(...)` en la configuración; usa selectores Playwright, por ejemplo `#identificador-real`. Si el formulario está dentro de un iframe, la consulta abre otra pestaña, requiere un botón para volver o presenta resultados progresivos, hay que adaptar `consult()` al comportamiento real. Esta versión exige formulario y resultados en la misma pestaña y un formulario accesible por URL.

Las columnas configuradas son `DNI` y `Nº EXPEDIENTE`. La fila 1 debe contener encabezados únicos. Guarda DNI y expediente como texto para conservar ceros iniciales. Para Excel local, `sheet` selecciona la hoja (o `null` para la activa). Puedes configurar `form_url` para el formulario de la intranet.

## Google Sheets

La entrada usa ahora Google Sheets API con OAuth de solo lectura. Sigue la guía completa [GOOGLE_API.md](GOOGLE_API.md): configuración de app, público y contacto, cliente de escritorio, autorización en Brave, pruebas y solución de errores. No se inicia sesión en Google desde el Brave automatizado.

Prueba la lectura con .\.venv\Scripts\python.exe bot.py --check-sheets. Después ejecuta .\ejecutar_brave.ps1 para consultar los expedientes. No necesitas dejar Sheets abierto.

## Ejecución

Alternativa con Excel local:

```powershell
.\.venv\Scripts\python.exe bot.py --input entrada.xlsx --output resultados.xlsx
```

Cada fila carga de nuevo el formulario, desmarca «Soc titular», introduce los identificadores y consulta. Los errores no se presentan como estados administrativos ni como anomalías. Ante un fallo, el programa guarda lo obtenido y permite detenerse para revisar la sesión. No sobrescribe archivos existentes ni el original. No implementa todavía reanudación automática.

La integración real está pendiente de una prueba con acceso autenticado y una fila conocida. Comprueba primero esa fila antes de ejecutar el lote.


## Ejecutar con Brave y conservar el historial

Ejecuta .\ejecutar_brave.ps1 desde PowerShell. Abre Brave instalado en el PC usando un perfil propio persistente (.brave-bot-profile). Autoriza Sheets con OAuth en el navegador habitual y completa FNMT en la ventana automatizada. No utiliza el perfil de Brave que ya tengas abierto ni el navegador integrado de Codex.

Sin --output, cada ejecución guarda un nuevo Excel en outputs/consultas con un nombre consulta_FECHA_HORA_IDENTIFICADOR.xlsx. Una ejecución consulta todas las filas y guarda un único archivo que se actualiza después de cada fila; la siguiente ejecución crea otro. Un --output explícito nunca sobrescribe archivos de consultas previas.

Puedes configurar browser_executable, browser_profile y output_dir en config.json. No uses como browser_profile el perfil habitual de Brave mientras esté abierto; el bot necesita un perfil propio disponible.

