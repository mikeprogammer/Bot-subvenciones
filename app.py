"""Interfaz portable para consultar subvenciones."""
import hashlib
import json
import os
import queue
import sys
import threading
import traceback
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from ui import Interface, create_root

from bot import browser_options, consult, find_form, form_diagnostic, header_row, new_output_path, parse_sheets_values, save_results
from sheets_api import read_values, sheet_identity
from playwright.sync_api import sync_playwright
from fnmt import AUTH_ORIGINS, certificate_policy, personal_certificates, install_machine_policy, prepare_machine_cleanup, cleanup_machine_policy
from auto_login import automatic_login


def friendly_error(exc):
    if type(exc).__name__ == 'TargetClosedError' or 'has been closed' in str(exc):
        return ('La conexión con Brave se ha cerrado. Mantén abierta la ventana del bot durante '
                'todas las consultas. Si Brave desaparece solo, vuelve a ejecutar y consulta '
                'el diagnóstico guardado junto al Excel.')
    return type(exc).__name__ + ': ' + str(exc).splitlines()[0][:500]

STATE = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'BotSubvenciones_1_5'
DEFAULTS = {
    'sheets_url': '', 'oauth_credentials': '', 'browser_executable': '',
    'output_dir': str(Path.home() / 'Documents' / 'ConsultasSubvenciones'),
    'dni_column': 'DNI', 'expediente_column': 'Nº EXPEDIENTE',
    'header_row': 1,
    'login_url': 'https://intranet.caib.es/subvenfront/',
    'form_url': 'https://intranet.caib.es/subvenfront/consulta-estado-expediente-subvencion',
    'timeout_ms': 30000, 'delay_seconds': 2,
    'auto_fnmt': True, 'fnmt_thumbprint': '', 'fnmt_origins': AUTH_ORIGINS,
    'selectors': {
        'titular': "input:is(#titularExpediente, [name='titularExpediente'])",
        'dni': "input:is(#titularDocumentoNumero, [name='titularDocumentoNumero'])",
        'expediente': "input:is(#numeroExpedienteCompleto, [name='numeroExpedienteCompleto'])",
        'buscar': "button.p-button-success:has-text('Cerca')",
        'resultado': '.resultado-error, .mt-3',
    },
}


class LogStream:
    def __init__(self, events):
        self.events = events

    def write(self, text):
        if text.strip():
            # La URL OAuth puede incluir parámetros de sesión; no se vuelca al registro.
            if 'accounts.google.com/o/oauth2/auth?' in text:
                text = 'Autoriza Google en la pestaña de Brave que se ha abierto.'
            self.events.put(('log', text.strip()))

    def flush(self):
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.resume = threading.Event()
        self.running = False
        self.fnmt_busy = False
        self.pending_cleanup = []
        self.last_output = None
        self.log_path = None
        self.settings = dict(DEFAULTS)
        if (STATE / 'settings.json').exists():
            try:
                self.settings.update(json.loads((STATE / 'settings.json').read_text(encoding='utf-8')))
            except (OSError, ValueError):
                pass
        if self.settings.get('fnmt_origins') == 'https://se-pasarela-ident.clave.gob.es,https://se-pasarela-identclave.gob.es':
            self.settings['fnmt_origins'] = AUTH_ORIGINS
        root.title('Bot de subvenciones 1.5.1')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.ui = Interface(self)
        root.after(100, self.poll)
        root.after(200, self.detect_certificates)

    def setup_certificate_policy(self):
        if self.running or self.fnmt_busy:
            return
        if not messagebox.askyesno('Configurar FNMT', 'Se instalará una regla para el certificado y los dominios indicados en este navegador, para todos los usuarios del equipo. Al terminar el lote se solicitará UAC de nuevo para retirarla, incluidas las reglas idénticas configuradas anteriormente. Acepta ambos avisos. No se exporta la clave privada ni se borran otras reglas. ¿Continuar?'):
            return
        config = {'fnmt_origins': self.variables['fnmt_origins'].get(),
                  'fnmt_thumbprint': self.certificates.get(self.certificate_label.get(), self.settings.get('fnmt_thumbprint', ''))}
        try:
            executable = browser_options({'browser_executable': self.variables['browser_executable'].get()})['executable_path']
        except Exception as exc:
            messagebox.showerror('Configurar FNMT', str(exc))
            return
        self.set_fnmt_busy(True)
        def install():
            try:
                install_machine_policy(config, executable)
                self.events.put(('log', 'FNMT configurado. Cierra las ventanas de este navegador antes del lote. Al terminar, acepta UAC para retirar la regla.'))
            except Exception as exc:
                self.events.put(('error', str(exc)))
            finally:
                self.events.put(('fnmt_idle', None))
        threading.Thread(target=install, daemon=True).start()

    def set_fnmt_busy(self, busy):
        """Solo se llama desde el hilo de interfaz."""
        self.fnmt_busy = busy
        for field in [*self.fields, self.check, self.run]:
            field.configure(state='disabled' if busy else 'normal')
        self.certificate_picker.configure(state='disabled' if busy else 'readonly')

    def remove_certificate_policy(self):
        if self.running or self.fnmt_busy:
            return
        # Conserva la captura del lote fallido aunque se cambie la selección.
        pending = [dict(entry) for entry in self.pending_cleanup]
        config = {'fnmt_origins': self.variables['fnmt_origins'].get(),
                  'fnmt_thumbprint': self.certificates.get(self.certificate_label.get(), self.settings.get('fnmt_thumbprint', '')),
                  '_fnmt_machine_cleanup': pending}
        try:
            executable = None if pending else browser_options({'browser_executable': self.variables['browser_executable'].get()})['executable_path']
        except Exception as exc:
            self.status.set('Error: ' + str(exc))
            return
        self.set_fnmt_busy(True)
        self.status.set('Comprobando la regla FNMT para su retirada…')
        def remove():
            snapshot = pending
            try:
                if not pending:
                    prepare_machine_cleanup(config, executable)
                    snapshot = list(config.get('_fnmt_machine_cleanup', []))
                if snapshot:
                    cleanup_machine_policy(config, lambda msg: self.events.put(('log', msg)))
                    self.events.put(('cleanup_resolved', snapshot))
                else:
                    self.events.put(('log', 'No hay reglas permanentes coincidentes con el certificado y dominios seleccionados.'))
            except Exception as exc:
                self.events.put(('cleanup_pending', snapshot))
                self.events.put(('error', str(exc)))
            finally:
                self.events.put(('fnmt_idle', None))
        threading.Thread(target=remove, daemon=True).start()

    def detect_certificates(self):
        def read():
            try:
                items = personal_certificates()
                self.events.put(('certificates', items))
                self.events.put(('log', f'FNMT personales vigentes detectados: {len(items)}.'))
            except Exception:
                self.events.put(('log', 'No se pudo leer el almacén Windows. Se volverá a comprobar al consultar.'))
        threading.Thread(target=read, daemon=True).start()

    def browse(self, key, kind):
        path = filedialog.askdirectory() if kind == 'dir' else filedialog.askopenfilename(
            filetypes=[('Archivo ' + kind.upper(), '*.' + kind)])
        if path:
            self.variables[key].set(path)

    def config(self):
        config = dict(self.settings)
        config.update({k: v.get().strip() for k, v in self.variables.items()})
        config['header_row'] = header_row(config)
        config['auto_fnmt'] = True
        config['fnmt_thumbprint'] = self.certificates.get(self.certificate_label.get(), self.settings.get('fnmt_thumbprint', ''))
        sheet_identity(config['sheets_url'])
        client = Path(config['oauth_credentials'])
        if not client.is_file():
            raise ValueError('Selecciona el credentials.json descargado de Google Cloud.')
        data = json.loads(client.read_text(encoding='utf-8-sig'))
        if 'installed' not in data:
            raise ValueError('Las credenciales deben ser de una aplicación de escritorio.')
        if not config['output_dir'] or not config['dni_column'] or not config['expediente_column']:
            raise ValueError('Indica la carpeta de salida y ambas columnas.')
        executable = browser_options(config)['executable_path']
        identity = hashlib.sha256(data['installed']['client_id'].encode()).hexdigest()[:16]
        config['oauth_token'] = str(STATE / 'oauth' / identity / 'token.json')
        config['browser_profile'] = str(STATE / 'brave-profile')
        STATE.mkdir(parents=True, exist_ok=True)
        saved = {k: config[k] for k in DEFAULTS}
        (STATE / 'settings.json').write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
        return config, executable

    def start(self, check_only):
        if self.running or self.fnmt_busy:
            return
        if not self.ui.validate():
            return
        try:
            config, executable = self.config()
        except Exception as exc:
            self.ui.show_error('oauth_credentials' if 'credencial' in str(exc).lower() or 'json' in str(exc).lower() else 'browser_executable', str(exc))
            self.status.set('Error: ' + str(exc))
            return
        self.running = True
        self.ui.failed = False
        self.certificate_picker.configure(state='disabled')
        self.log_path = None
        if not check_only:
            config['run_output'] = str(new_output_path(config['output_dir']))
            self.log_path = Path(config['run_output']).with_suffix('.log')
        self.stop.clear()
        self.resume.clear()
        for field in [*self.fields, self.check, self.run]:
            field.configure(state='disabled')
        self.cancel.configure(state='normal')
        self.progress['value'] = 0
        self.progress.configure(mode='indeterminate')
        self.progress.start()
        self.status.set('Leyendo Sheets. Autoriza Google en Brave si se solicita.')
        threading.Thread(target=self.worker, args=(config, executable, check_only), daemon=True).start()

    def worker(self, config, executable, check_only):
        try:
            if not check_only:
                prepare_machine_cleanup(config, executable)
            records = parse_sheets_values(read_values(config['sheets_url'], config, executable), config)
            if not records:
                raise ValueError('La pestaña está vacía.')
            self.events.put(('log', f'Sheets API: {len(records)} filas leídas.'))
            if check_only or self.stop.is_set():
                return
            with certificate_policy(config, executable, lambda msg: self.events.put(('log', msg))), sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(config['browser_profile'], **browser_options(config))
                try:
                    context.set_default_timeout(config['timeout_ms'])
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto(config['login_url'], wait_until='domcontentloaded')
                    page = automatic_login(context, config, self.stop, lambda msg: self.events.put(('log', msg)))
                    if page is None:
                        return
                    output = Path(config['run_output']) if config.get('run_output') else new_output_path(config['output_dir'])
                    results = []
                    diagnostic = None
                    for index, (number, dni, expediente, error) in enumerate(records, 1):
                        if self.stop.is_set():
                            break
                        input_error = bool(error)
                        state = anomalies = documents = original = ''
                        if not error:
                            try:
                                state, anomalies, documents, original = consult(page, config['form_url'], config['selectors'], dni, expediente, config['timeout_ms'])
                            except Exception as exc:
                                error = friendly_error(exc)
                                diagnostic = output.with_suffix('.diagnostico.txt')
                                diagnostic.parent.mkdir(parents=True, exist_ok=True)
                                diagnostic.write_text(traceback.format_exc(), encoding='utf-8')
                        results.append((dni, expediente, state, anomalies, documents, original, error, number))
                        save_results(output, results)
                        self.events.put(('progress', (index, len(records))))
                        self.events.put(('log', f'Fila {number}: {"ERROR" if error else state}'))
                        if error:
                            self.events.put(('log', 'Motivo: ' + error))
                            if input_error:
                                self.events.put(('log', f'Fila {number} omitida por datos incompletos en Sheets; continúo con la siguiente.'))
                                continue
                            if diagnostic:
                                self.events.put(('log', 'Diagnóstico técnico: ' + str(diagnostic)))
                            self.events.put(('log', 'Lote detenido por error; el Excel conserva las filas procesadas.'))
                            break
                        if self.stop.wait(config['delay_seconds']):
                            break
                    if results:
                        self.events.put(('output', str(output.resolve())))
                finally:
                    try:
                        context.close()
                    except Exception:
                        # El navegador puede haber terminado antes del cierre final.
                        pass
        except Exception as exc:
            self.events.put(('error', str(exc)))
        finally:
            if not check_only:
                snapshot = list(config.get('_fnmt_machine_cleanup', []))
                try:
                    cleanup_machine_policy(config, lambda msg: self.events.put(('log', msg)))
                    self.events.put(('cleanup_resolved', snapshot))
                except Exception as exc:
                    self.events.put(('cleanup_pending', snapshot))
                    self.events.put(('error', str(exc)))
            self.events.put(('done', None))

    def poll(self):
        while not self.events.empty():
            kind, value = self.events.get()
            if kind in ('log', 'login', 'error', 'output'):
                if self.log_path:
                    try:
                        self.log_path.parent.mkdir(parents=True, exist_ok=True)
                        with self.log_path.open('a', encoding='utf-8') as logfile:
                            logfile.write(str(value) + '\n')
                    except OSError:
                        # El registro en pantalla sigue disponible si falla la carpeta.
                        pass
                self.ui.append_log(value)
                if kind != 'log' or not str(value).startswith('FNMT personales vigentes detectados:'):
                    self.status.set(str(value))
            if kind == 'cleanup_pending':
                for entry in value:
                    if entry not in self.pending_cleanup:
                        self.pending_cleanup.append(entry)
            elif kind == 'cleanup_resolved':
                self.pending_cleanup = [entry for entry in self.pending_cleanup if entry not in value]
            elif kind == 'fnmt_idle':
                self.set_fnmt_busy(False)
            elif kind == 'login':
                self.continue_button.configure(state='normal')
            elif kind == 'progress':
                self.continue_button.configure(state='disabled')
                self.progress['value'] = value[0] * 100 / value[1]
                self.status.set(f'Consultadas {value[0]} de {value[1]} filas.')
            elif kind == 'output':
                self.last_output = value
                self.open_result.configure(state='normal')
                self.ui.open_folder.configure(state='normal')
            elif kind == 'error':
                self.ui.failed = True
                self.status.set('Error: ' + str(value))
            elif kind == 'certificates':
                self.certificates = {f"{c['subject']} — hasta {c['expires']} [{c['thumbprint'][-8:]}]": c['thumbprint'] for c in value}
                self.certificate_picker['values'] = list(self.certificates)
                if not self.running:
                    self.status.set(f'{len(value)} certificados FNMT detectados')
                chosen = next((label for label, fingerprint in self.certificates.items() if fingerprint == self.settings.get('fnmt_thumbprint')), None)
                if chosen or len(self.certificates) == 1:
                    self.certificate_label.set(chosen or next(iter(self.certificates)))
                elif self.certificates:
                    self.certificate_label.set('Selecciona el titular que debe usar el bot')
            elif kind == 'done':
                self.progress.stop()
                self.progress.configure(mode='determinate')
                self.certificate_picker.configure(state='readonly')
                self.running = False
                for field in [*self.fields, self.check, self.run]:
                    field.configure(state='normal')
                self.cancel.configure(state='disabled')
                self.continue_button.configure(state='disabled')
                if self.ui.failed:
                    pass  # Conserva el error visible aunque se haya pedido detener.
                elif self.stop.is_set():
                    self.status.set('Ejecución detenida.')
                elif not self.ui.failed:
                    self.progress.set(1)
                    self.status.set('Ejecución completada.')
        self.root.after(100, self.poll)

    def cancel_run(self):
        self.stop.set()
        self.resume.set()
        self.status.set('Deteniendo al terminar la operación actual…')

    def open_output(self):
        if self.last_output:
            os.startfile(self.last_output)

    def close(self):
        if self.fnmt_busy:
            messagebox.showinfo('Operación FNMT en curso', 'Espera a que termine la configuración o retirada de la regla FNMT antes de cerrar.')
            return
        if self.running:
            messagebox.showinfo('Operación en curso', 'Pulsa Detener y espera antes de cerrar. La autorización OAuth puede tardar hasta cinco minutos.')
            return
        self.root.destroy()


def main():
    root = create_root()
    app = App(root)
    sys.stdout = LogStream(app.events)
    sys.stderr = LogStream(app.events)
    if '--browser-self-test' in sys.argv:
        root.withdraw()
        import tempfile
        target = Path(sys.argv[sys.argv.index('--browser-self-test') + 1])
        try:
            with tempfile.TemporaryDirectory() as profile, sync_playwright() as p:
                context = p.chromium.launch_persistent_context(profile, **browser_options({}))
                page = context.pages[0]
                page.set_content('''<input type="checkbox" id="titular" checked>
                    <input id="dni"><input id="exp">
                    <button id="buscar" onclick="document.getElementById('result').textContent='No s'+String.fromCharCode(39)+'ha trobat cap expedient amb aquestes dades';document.getElementById('reset').hidden=false">Cerca</button>
                    <button id="reset" hidden onclick="document.getElementById('result').textContent='';this.hidden=true;document.getElementById('titular').checked=true">Neteja</button>
                    <div id="result"></div>''')
                selectors = {'titular': '#titular', 'dni': '#dni', 'expediente': '#exp', 'buscar': '#buscar', 'resultado': '#result'}
                for i in range(5):
                    result = consult(page, 'about:blank', selectors, f'TEST{i}', f'EXP{i}')
                    assert result[0] == 'Expediente no encontrado'
                    assert not page.is_closed()
                context.close()
            target.write_text(json.dumps({'brave': 'ok', 'queries': 5, 'auth': 'not tested'}), encoding='utf-8')
        except Exception:
            target.write_text(traceback.format_exc(), encoding='utf-8')
        root.destroy()
        return
    if '--self-test' in sys.argv:
        root.withdraw()
        import certifi
        import googleapiclient.discovery
        from fnmt import personal_certificates
        from zoneinfo import ZoneInfo
        assert Path(certifi.where()).exists()
        assert ZoneInfo('Europe/Madrid')
        certificates = personal_certificates()
        with sync_playwright() as p:
            assert p.chromium
        root.update()
        target = Path(sys.argv[sys.argv.index('--self-test') + 1])
        target.write_text(json.dumps({'gui': 'ok', 'playwright': 'ok', 'google_api': 'ok', 'timezone': 'ok', 'fnmt_store': 'ok', 'personal_certificates': len(certificates)}), encoding='utf-8')
        root.destroy()
        return
    root.mainloop()


if __name__ == '__main__':
    main()
