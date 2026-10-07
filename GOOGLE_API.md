# Guía de Google Sheets API y OAuth para el bot

Actualizada: 7 de octubre de 2026. Esta guía documenta la implementación del proyecto y no contiene credenciales reales.

La entrada actual usa Google Sheets API con permiso de solo lectura. Brave automatizado solo consulta subvenciones; Google se autoriza en tu Brave habitual mediante OAuth. No necesita contraseña en el código ni una hoja abierta.

Sigue la [guía oficial de Google para Python](https://developers.google.com/workspace/sheets/api/quickstart/python):

1. Abre [Google Cloud Console](https://console.cloud.google.com/) y selecciona o crea un proyecto.
2. Habilita **Google Sheets API**.
3. Configura **Google Auth Platform**, nombre de la aplicación y correo de contacto. Para una cuenta personal configura audiencia externa y añade tu cuenta como usuario de prueba si está en modo Testing.
4. Crea un cliente **OAuth 2.0 de tipo aplicación de escritorio**.
5. Descarga su JSON como `C:\Projects\Bot-subvenciones\credentials.json`. No pongas tu contraseña ahí; usa el archivo descargado.

Prueba solo la entrada:

```powershell
.\.venv\Scripts\python.exe bot.py --check-sheets
```

La primera vez abre tu Brave habitual para iniciar sesión y revisar/autorizar el acceso. La respuesta OAuth vuelve a un servidor local temporal. Si Google bloquea la app, revisa el proyecto, cliente y usuario de prueba; no desactives las protecciones.

Se pide `spreadsheets.readonly`. Ese permiso se aplica a las hojas accesibles a la cuenta, no se limita al documento configurado. El programa solo lee el documento y la pestaña seleccionados en `sheets_url`, mediante su `gid`.

El token se conserva en `.google-auth/token.json` y se renueva cuando sea posible. No compartas este directorio ni `credentials.json`; ambos están excluidos de Git. La autorización puede repetirse cuando el token expire o se revoque. No se solicitan permisos de escritura ni se modifica Sheets.

Cuando la lectura funcione:

```powershell
.\ejecutar_brave.ps1
```

Lee Sheets por API, abre el perfil propio de Brave para FNMT y consulta las filas. Completa el certificado manualmente y pulsa Intro en la consola cuando veas el formulario. Cada ejecución crea un Excel nuevo en `outputs/consultas`.

Las dependencias están en `requirements.txt`. La prueba autenticada requiere el cliente OAuth real y la aprobación de Google; las pruebas de lectura simulada no demuestran acceso a la cuenta.

## Motivo del cambio a la API

Google rechazó el inicio de sesión desde Brave automatizado con un aviso de navegador posiblemente no seguro. Por eso Google se autoriza ahora en el Brave habitual y Python lee las filas por API. El Brave automatizado se dedica a FNMT y subvenciones. No necesitas dejar abierta una pestaña de Sheets ni exportar manualmente los datos.

## Qué rellenar en Google Auth Platform

Para una cuenta personal Gmail y esta prueba:

| Apartado | Valor |
|---|---|
| Nombre de la aplicación | `Bot de subvenciones` |
| Correo de asistencia al usuario | Tu correo de Google |
| Público / Audiencia | **Externo** |
| Información de contacto | Un correo tuyo para recibir avisos del proyecto |
| Estado de publicación | **Prueba / Testing** |
| Usuarios de prueba | La cuenta que autorizará el bot y tiene acceso a la hoja |

En **Público → Usuarios de prueba → Añadir usuarios**, añade esa cuenta y guarda. «Externo» no publica la hoja; permite autorizar cuentas fuera de una organización Workspace. Revisa las condiciones que muestre Google antes de aceptarlas. En **Acceso a los datos**, configura el alcance `https://www.googleapis.com/auth/spreadsheets.readonly`, que coincide con el código.

Referencia: [configuración del consentimiento OAuth](https://developers.google.com/workspace/guides/configure-oauth-consent).

## Cliente y archivo de credenciales

En el mismo proyecto con Sheets API habilitada, abre **Google Auth Platform → Clientes → Crear cliente**. Selecciona **Aplicación de escritorio**, escribe `Bot subvenciones PC` y descarga el JSON.

Renombra el archivo descargado como `credentials.json` y guárdalo en la raíz del proyecto. Comprueba que no se llame `credentials.json.json` o `credentials.json.txt`. No uses un cliente web, una clave API ni una cuenta de servicio para esta implementación. El retorno OAuth utiliza un puerto local temporal.

Referencia: [guía de Python y cliente de escritorio](https://developers.google.com/workspace/sheets/api/quickstart/python).

## Configuración de la hoja

Estas claves se editan dentro del `config.json` completo; conserva las opciones de Brave y los selectores:

```json
{
  "sheets_url": "https://docs.google.com/spreadsheets/d/ID_DOCUMENTO/edit#gid=0",
  "dni_column": "DNI",
  "expediente_column": "Nº EXPEDIENTE",
  "oauth_credentials": "credentials.json",
  "oauth_token": ".google-auth/token.json"
}
```

Usa la URL real de tu documento. El `gid` identifica la pestaña dentro de Sheets. Los encabezados deben estar en la fila 1 y ser únicos. El bot omite filas completamente vacías y registra filas sin DNI o expediente. Lee el texto mostrado, así que conserva los ceros iniciales en la hoja original.

## Preparar Python y autorizar por primera vez

En PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Projects\Bot-subvenciones'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe bot.py --check-sheets
```

En otro PC sin entorno virtual, créalo antes con `py -m venv .venv`. En este PC ya se han instalado las dependencias.

La autorización sigue estos pasos:

1. Python abre la página oficial de Google en el Brave habitual.
2. Elige la cuenta de prueba con acceso a la hoja y completa la verificación en dos pasos si aparece.
3. Revisa y autoriza el permiso de lectura para la aplicación.
4. Google vuelve al servidor local y muestra que la autorización se ha completado.
5. Python guarda el token y lee las filas de la pestaña configurada.

Mantén la consola abierta durante el proceso; la espera es de cinco minutos. Si Brave no se abre, usa la URL de autorización que muestra la consola. `--check-sheets` solo comprueba la lectura: no consulta subvenciones ni crea Excel. Para nuestra hoja ficticia se esperan cinco filas, salvo que se modifique.

## Ejecución completa y registro de consultas

Una vez comprobada la entrada, ejecuta `./ejecutar_brave.ps1` desde PowerShell en el proyecto. Primero lee una instantánea de Sheets y después abre Brave con `.brave-bot-profile` para FNMT. Completa el acceso manualmente; cuando aparezca el formulario, pulsa Intro en la consola y selecciona su pestaña por número.

Se genera `outputs/consultas/consulta_FECHA_HORA_IDENTIFICADOR.xlsx`, con hora de Europe/Madrid. Cada fila actualiza ese archivo; la siguiente ejecución crea otro. No se modifica Sheets. El perfil automatizado y la autorización OAuth son independientes.

El Excel conserva DNI, expediente, estado, anomalías, documentos referenciados, texto original, errores y fila de origen. «Expediente no encontrado» es un resultado de búsqueda; las anomalías se marcan como no disponibles, sin afirmar que el expediente carece de ellas.

## Renovar autorización o cambiar de cuenta

`credentials.json` identifica la aplicación; `.google-auth/token.json` contiene la autorización de la cuenta. El código intenta renovar el acceso y vuelve a pedir autorización si la renovación es rechazada. No necesita guardar la contraseña de Google.

En una aplicación externa en modo Testing, los tokens de actualización para permisos como Sheets pueden expirar a los siete días. La autorización de prueba no debe considerarse permanente. [Caducidad de tokens de Google](https://developers.google.com/identity/protocols/oauth2/web-server#expiration).

Para cambiar de cuenta, detén el bot y retira o renombra `.google-auth/token.json`; después autoriza de nuevo. La nueva cuenta también necesita figurar como usuario de prueba y tener acceso a la hoja. Puedes revocar el acceso desde las conexiones con terceros de tu cuenta de Google. No compartas tokens, credenciales ni el perfil de Brave; están excluidos de Git.

## Problemas frecuentes

| Mensaje o síntoma | Qué revisar |
|---|---|
| Falta `credentials.json` | Nombre, extensión y ubicación del JSON descargado |
| JSON no válido para escritorio | Tipo de cliente OAuth: Aplicación de escritorio |
| `access_denied` | Cuenta añadida como usuario de prueba; autorización aceptada |
| HTTP 403 | Sheets API habilitada en el proyecto correcto y permisos de la cuenta |
| HTTP 404 | Documento correcto y cuenta con acceso |
| `gid` inexistente | URL copiada de la pestaña exacta de datos |
| Columnas ausentes o duplicadas | Encabezados DNI y Nº EXPEDIENTE en la primera fila |
| Brave no se abre | Ruta `browser_executable`; abre la URL que muestra la consola |
| Retorno local sin completar | Consola abierta y autorización dentro de cinco minutos |
| Google bloquea la aplicación | Cliente, público y usuario de prueba; no desactives protecciones |
| Solicita autorización días después | Caducidad, revocación o renovación rechazada del token |

## Estado de las pruebas

La prueba anterior en el navegador integrado leyó cinco filas y todas devolvieron expediente no encontrado. Brave se abrió desde Python, pero su inicio de sesión automatizado en Google fue rechazado. La implementación actual usa OAuth y API.

Las 14 pruebas locales verifican lectura API simulada, pestaña por `gid`, títulos con apóstrofos, identificadores, encabezados, anomalías/documentos, exportación y archivos distintos por ejecución. La lectura OAuth real está pendiente de guardar `credentials.json` y autorizarla. El lote completo API → Brave/FNMT → Excel queda por verificar.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```
