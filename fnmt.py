"""Selección temporal de certificados personales FNMT del almacén Windows."""
import base64
import json
import subprocess
import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.utils import CryptographyDeprecationWarning

PERSONAL_OIDS = {'1.3.6.1.4.1.5734.3.10.1', '1.3.6.1.4.1.5734.3.5'}
AUTH_ORIGINS = 'https://pasarela-ident.clave.gob.es'


def decode_certificate(row):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', CryptographyDeprecationWarning)
            cert = x509.load_der_x509_certificate(base64.b64decode(row['der']))
    except ValueError:
        return None
    now = datetime.now(timezone.utc)
    if not row['private'] or not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
        return None
    try:
        policies = cert.extensions.get_extension_for_oid(ExtensionOID.CERTIFICATE_POLICIES).value
    except x509.ExtensionNotFound:
        return None
    if not PERSONAL_OIDS.intersection(p.policy_identifier.dotted_string for p in policies):
        return None
    issuer = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
    subject = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if not issuer or not subject or 'FNMT' not in cert.issuer.rfc4514_string().upper():
        return None
    return {'thumbprint': row['thumbprint'].upper(), 'issuer': issuer[0].value,
            'subject': subject[0].value, 'expires': cert.not_valid_after_utc.date().isoformat()}


def personal_certificates():
    # RawData contiene únicamente el certificado público, nunca la clave privada.
    script = """$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new();
    $items=@(foreach($location in @('CurrentUser','LocalMachine')) {
      $store=[Security.Cryptography.X509Certificates.X509Store]::new('My',$location)
      try {
        $store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
        foreach($cert in $store.Certificates) {
          @{der=[Convert]::ToBase64String($cert.RawData);private=$cert.HasPrivateKey;thumbprint=$cert.Thumbprint}
        }
      } finally { $store.Close() }
    }); ConvertTo-Json -InputObject $items -Compress"""
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, encoding='utf-8-sig', timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    unique = {}
    for row in json.loads(result.stdout or '[]'):
        item = decode_certificate(row)
        if item:
            unique[item['thumbprint']] = item
    return list(unique.values())


def choose_certificate(items, thumbprint=''):
    selected = [c for c in items if c['thumbprint'] == thumbprint.replace(' ', '').upper()] if thumbprint else items
    if len(selected) != 1:
        if not items:
            raise ValueError('No hay un certificado FNMT de persona física vigente con clave privada en Windows. Instálalo en el almacén Personal del usuario que ejecuta el bot, con su clave privada.')
        choices = '\n'.join(f"{c['subject']} (hasta {c['expires']}): {c['thumbprint']}" for c in items)
        raise ValueError('Indica la huella del certificado FNMT que deseas usar en el campo de la interfaz:\n' + choices)
    cert = selected[0]
    if sum(c['subject'] == cert['subject'] and c['issuer'] == cert['issuer'] for c in items) != 1:
        raise ValueError('Hay varios certificados vigentes con el mismo titular y emisor. El navegador no puede distinguirlos por huella; retira del almacén el duplicado que no deba utilizarse antes de automatizar.')
    return cert


def rules_for(cert, origins):
    rules = []
    for value in origins.split(','):
        url = urlsplit(value.strip())
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/') or '*' in url.netloc:
            raise ValueError('Los dominios FNMT deben ser orígenes HTTPS exactos separados por comas, sin rutas ni comodines.')
        rules.append(json.dumps({'pattern': 'https://' + url.netloc,
                                'filter': {'ISSUER': {'CN': cert['issuer']}, 'SUBJECT': {'CN': cert['subject']}}}))
    return rules


@contextmanager
def certificate_policy(config, executable, log):
    if not config.get('auto_fnmt', True):
        yield
        return
    import winreg
    name = Path(executable).name.lower()
    roots = {'brave.exe': r'Software\Policies\BraveSoftware\Brave',
             'chrome.exe': r'Software\Policies\Google\Chrome',
             'msedge.exe': r'Software\Policies\Microsoft\Edge'}
    if name not in roots:
        raise ValueError('La selección automática FNMT admite Brave, Chrome y Edge.')
    cert = choose_certificate(personal_certificates(), config.get('fnmt_thumbprint', ''))
    rules = rules_for(cert, config.get('fnmt_origins', AUTH_ORIGINS))
    path = roots[name] + r'\AutoSelectCertificateForUrls'
    if machine_policy_ready(path, rules):
        log('Selección automática FNMT configurada por el administrador.')
        yield
        return
    added = []
    try:
        try:
            policy_key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | winreg.KEY_WRITE)
        except PermissionError:
            raise PermissionError('Windows no permite configurar la selección automática en este usuario. No se iniciará el lote. Pulsa Configurar FNMT (administrador) una vez y acepta el aviso de Windows.') from None
        with policy_key as key:
            existing = {}
            for i in range(winreg.QueryInfoKey(key)[1]):
                entry, value, _ = winreg.EnumValue(key, i)
                existing[entry] = value
            for rule in rules:
                if rule in existing.values():
                    continue
                index = 1
                while str(index) in existing:
                    index += 1
                entry = str(index)
                winreg.SetValueEx(key, entry, 0, winreg.REG_SZ, rule)
                added.append((entry, rule))
                existing[entry] = rule
        log('Selección automática FNMT preparada para el certificado personal vigente. El bot abrirá el acceso y elegirá el certificado. Windows puede solicitar un PIN si la clave lo exige.')
        yield
    finally:
        if added:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                    for entry, rule in added:
                        try:
                            if winreg.QueryValueEx(key, entry)[0] == rule:
                                winreg.DeleteValue(key, entry)
                        except FileNotFoundError:
                            pass
            except OSError as exc:
                log('No se pudo retirar la regla temporal FNMT: ' + str(exc))


def machine_policy_ready(path, rules):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ) as key:
            values = [winreg.EnumValue(key, i)[1] for i in range(winreg.QueryInfoKey(key)[1])]
        return all(rule in values for rule in rules)
    except OSError:
        return False


def install_machine_policy(config, executable):
    """Eleva solo la instalación de reglas públicas; nunca abre el navegador elevado."""
    name = Path(executable).name.lower()
    roots = {'brave.exe': r'Software\Policies\BraveSoftware\Brave',
             'chrome.exe': r'Software\Policies\Google\Chrome',
             'msedge.exe': r'Software\Policies\Microsoft\Edge'}
    if name not in roots:
        raise ValueError('Selecciona Brave, Chrome o Edge.')
    cert = choose_certificate(personal_certificates(), config.get('fnmt_thumbprint', ''))
    rules = rules_for(cert, config.get('fnmt_origins', AUTH_ORIGINS))
    path = roots[name] + r'\AutoSelectCertificateForUrls'
    if machine_policy_ready(path, rules):
        return
    # JSON codificado: no se interpolan nombres de titulares en comandos PowerShell.
    payload = base64.b64encode(json.dumps({'path': path, 'rules': rules}).encode('utf-8')).decode('ascii')
    script = """$ErrorActionPreference='Stop'
$data = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('PAYLOAD')) | ConvertFrom-Json
$key = [Microsoft.Win32.Registry]::LocalMachine.CreateSubKey($data.path)
try {
 foreach ($rule in $data.rules) {
  $names = @($key.GetValueNames())
  $exists = @($names | Where-Object { $key.GetValue($_) -eq $rule }).Count -gt 0
  if (-not $exists) {
   $index = 1
   while ($names -contains [string]$index) { $index++ }
   $key.SetValue([string]$index, [string]$rule, [Microsoft.Win32.RegistryValueKind]::String)
  }
 }
} finally { $key.Dispose() }
""".replace('PAYLOAD', payload)
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    launcher = "$ErrorActionPreference='Stop'; $p=Start-Process -FilePath powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList @('-NoProfile','-NonInteractive','-EncodedCommand','" + encoded + "') -Wait -PassThru; exit $p.ExitCode"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', launcher],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode != 0 or not machine_policy_ready(path, rules):
        raise RuntimeError('No se pudo instalar la regla FNMT. El administrador debe autorizar el aviso de Windows y permitir cambios en las políticas del navegador.')
