"""Lectura de Google Sheets con OAuth para aplicaciones de escritorio."""
import json
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import re

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def sheet_identity(url):
    parsed = urlparse(url)
    match = re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]+)(?:/.*)?', parsed.path)
    if parsed.scheme != 'https' or parsed.netloc != 'docs.google.com' or not match:
        raise ValueError('URL de Google Sheets inválida')
    gid = parse_qs(parsed.fragment).get('gid', parse_qs(parsed.query).get('gid', []))
    if len(gid) != 1 or not gid[0].isdigit():
        raise ValueError('La URL debe incluir gid para identificar la pestaña exacta')
    return match[1], int(gid[0])


def sheet_range(metadata, gid):
    for item in metadata.get('sheets', []):
        properties = item['properties']
        if properties['sheetId'] == gid:
            return "'" + properties['title'].replace("'", "''") + "'"
    raise ValueError(f'La pestaña gid={gid} no existe en el documento')


def authorize(config, brave_executable):
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_path = Path(config.get('oauth_credentials', 'credentials.json'))
    token_path = Path(config.get('oauth_token', '.google-auth/token.json'))
    credentials = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if not credentials.has_scopes(SCOPES):
            credentials = None
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except RefreshError:
            credentials = None
    if not credentials or not credentials.valid:
        if not client_path.is_file():
            raise FileNotFoundError(
                f'Falta {client_path}. Descarga un cliente OAuth de tipo aplicación de escritorio '
                'desde Google Cloud con Google Sheets API habilitada. Consulta README.md.'
            )
        client = json.loads(client_path.read_text(encoding='utf-8-sig'))
        if 'installed' not in client:
            raise ValueError('credentials.json debe corresponder a un cliente OAuth de escritorio')
        webbrowser.register('brave-oauth', None, webbrowser.BackgroundBrowser(brave_executable))
        flow = InstalledAppFlow.from_client_config(client, SCOPES)
        print('Autoriza el acceso de solo lectura a Sheets en tu Brave habitual.')
        credentials = flow.run_local_server(
            port=0, browser='brave-oauth', timeout_seconds=300,
            authorization_prompt_message='Abre esta URL si Brave no se abre: {url}',
            success_message='Autorización completada. Puedes cerrar esta pestaña y volver al bot.',
        )
    token_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = token_path.with_suffix('.tmp')
    temporary.write_text(credentials.to_json(), encoding='utf-8')
    temporary.replace(token_path)
    return credentials


def fetch_values(service, url):
    spreadsheet_id, gid = sheet_identity(url)
    metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields='sheets.properties(sheetId,title)'
    ).execute()
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=sheet_range(metadata, gid),
        valueRenderOption='FORMATTED_VALUE', majorDimension='ROWS',
    ).execute()
    return result.get('values', [])


def read_values(url, config, brave_executable):
    sheet_identity(url)
    credentials = authorize(config, brave_executable)
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
    try:
        return fetch_values(service, url)
    except HttpError as exc:
        raise RuntimeError(
            f'Sheets API: HTTP {exc.resp.status}. Revisa que la API esté habilitada '
            'y que la cuenta autorizada tenga acceso al documento.'
        ) from None
    finally:
        service.close()
