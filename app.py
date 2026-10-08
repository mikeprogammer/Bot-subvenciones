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
from tkinter import filedialog, messagebox, ttk

from bot import browser_options, consult, find_form, form_diagnostic, new_output_path, parse_sheets_values, save_results
from sheets_api import read_values, sheet_identity
from playwright.sync_api import sync_playwright
from fnmt import AUTH_ORIGINS, certificate_policy


def friendly_error(exc):
    if type(exc).__name__ == 'TargetClosedError' or 'has been closed' in str(exc):
        return ('La conexión con Brave se ha cerrado. Mantén abierta la ventana del bot durante '
                'todas las consultas. Si Brave desaparece solo, vuelve a ejecutar y consulta '
                'el diagnóstico guardado junto al Excel.')
    return type(exc).__name__ + ': ' + str(exc).splitlines()[0][:500]

STATE = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'BotSubvenciones'
DEFAULTS = {
    'sheets_url': '', 'oauth_credentials': '', 'browser_executable': '',
    'output_dir': str(Path.home() / 'Documents' / 'ConsultasSubvenciones'),
    'dni_column': 'DNI', 'expediente_column': 'Nº EXPEDIENTE',
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
        self.last_output = None
        self.log_path = None
        self.settings = dict(DEFAULTS)
        if (STATE / 'settings.json').exists():
            try:
                self.settings.update(json.loads((STATE / 'settings.json').read_text(encoding='utf-8')))
            except (OSError, ValueError):
                pass
        root.title('Bot de subvenciones 1.3')
        root.geometry('940x870')
        root.minsize(880, 800)
        root.protocol('WM_DELETE_WINDOW', self.close)
        frame = ttk.Frame(root, padding=22)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Consulta de expedientes', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Google Sheets → Brave / FNMT → Excel nuevo por ejecución').pack(anchor='w', pady=(4, 16))
        self.variables = {}
        self.fields = []
        for key, label, browse in (
            ('oauth_credentials', 'Credenciales OAuth de Google (.json)', 'json'),
            ('sheets_url', 'URL de Google Sheets, incluida la pestaña gid', None),
            ('browser_executable', 'Brave (.exe): vacío para detectar automáticamente', 'exe'),
            ('output_dir', 'Carpeta de resultados', 'dir'),
            ('dni_column', 'Columna DNI', None),
            ('expediente_column', 'Columna de expediente', None),
            ('fnmt_thumbprint', 'Huella FNMT: dejar vacía para detectar el único certificado personal vigente', None),
            ('fnmt_origins', 'Dominios del acceso con certificado (HTTPS, separados por comas)', None),
        ):
            ttk.Label(frame, text=label).pack(anchor='w', pady=(5, 2))
            line = ttk.Frame(frame)
            line.pack(fill='x')
            var = tk.StringVar(value=self.settings[key])
            self.variables[key] = var
            field = ttk.Entry(line, textvariable=var)
            field.pack(side='left', fill='x', expand=True)
            self.fields.append(field)
            if browse:
                button = ttk.Button(line, text='Examinar…', command=lambda k=key, b=browse: self.browse(k, b))
                button.pack(side='right', padx=(6, 0))
                self.fields.append(button)
        self.auto_fnmt = tk.BooleanVar(value=self.settings['auto_fnmt'])
        cert_option = ttk.Checkbutton(frame, text='Seleccionar automáticamente FNMT de persona física', variable=self.auto_fnmt)
        cert_option.pack(anchor='w', pady=(8, 0))
        self.fields.append(cert_option)
        ttk.Label(frame, text='Regla temporal para este usuario de Windows: afecta a este navegador durante el lote. No exporta la clave privada.', wraplength=880).pack(anchor='w')
        actions = ttk.Frame(frame)
        actions.pack(fill='x', pady=15)
        self.check = ttk.Button(actions, text='Probar lectura de Sheets', command=lambda: self.start(True))
        self.check.pack(side='left')
        self.run = ttk.Button(actions, text='Consultar y crear Excel', command=lambda: self.start(False))
        self.run.pack(side='left', padx=8)
        self.continue_button = ttk.Button(actions, text='Ya veo el formulario FNMT', command=self.resume.set, state='disabled')
        self.continue_button.pack(side='left')
        self.cancel = ttk.Button(actions, text='Detener', command=self.cancel_run, state='disabled')
        self.cancel.pack(side='right')
        self.status = tk.StringVar(value='Selecciona el JSON de escritorio y la hoja para empezar.')
        ttk.Label(frame, textvariable=self.status, wraplength=800).pack(anchor='w', pady=(0, 6))
        self.progress = ttk.Progressbar(frame, mode='determinate')
        self.progress.pack(fill='x', pady=(0, 8))
        self.log = tk.Text(frame, height=9, state='disabled', wrap='word', font=('Segoe UI', 10))
        self.log.pack(fill='both', expand=True)
        self.open_result = ttk.Button(frame, text='Abrir último Excel', command=self.open_output, state='disabled')
        self.open_result.pack(anchor='e', pady=(8, 0))
        root.after(100, self.poll)

    def browse(self, key, kind):
        path = filedialog.askdirectory() if kind == 'dir' else filedialog.askopenfilename(
            filetypes=[('Archivo ' + kind.upper(), '*.' + kind)])
        if path:
            self.variables[key].set(path)

    def config(self):
        config = dict(self.settings)
        config.update({k: v.get().strip() for k, v in self.variables.items()})
        config['auto_fnmt'] = self.auto_fnmt.get()
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
        try:
            config, executable = self.config()
        except Exception as exc:
            messagebox.showerror('Revisa la configuración', str(exc))
            return
        self.running = True
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
        self.status.set('Leyendo Sheets. Autoriza Google en Brave si se solicita.')
        threading.Thread(target=self.worker, args=(config, executable, check_only), daemon=True).start()

    def worker(self, config, executable, check_only):
        try:
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
                    self.events.put(('login', 'En Brave pulsa Entra y completa FNMT. Mantén Brave abierto; después pulsa «Ya veo el formulario FNMT».'))
                    while True:
                        while not self.resume.wait(0.2):
                            if self.stop.is_set():
                                return
                            # Atiende las redirecciones y pestañas nuevas de Playwright.
                            if context.pages:
                                context.pages[0].wait_for_timeout(100)
                        self.resume.clear()
                        if self.stop.is_set():
                            return
                        deadline = time.monotonic() + 10
                        page = None
                        while time.monotonic() < deadline and not self.stop.is_set():
                            page = find_form(context, config['form_url'], config['selectors'])
                            if page is not None:
                                break
                            if context.pages:
                                context.pages[0].wait_for_timeout(200)
                            else:
                                raise RuntimeError('El navegador se ha cerrado. Vuelve a ejecutar el lote.')
                        if self.stop.is_set():
                            return
                        if page is not None:
                            break
                        self.events.put(('log', form_diagnostic(context, config['selectors'])))
                        self.events.put(('login', 'Todavía no detecto los campos de consulta en la ventana abierta por el bot. Mantengo Brave abierto: termina el acceso en esa ventana y vuelve a pulsar «Ya veo el formulario FNMT».'))
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
                self.log.configure(state='normal')
                self.log.insert('end', str(value) + '\n')
                self.log.see('end')
                self.log.configure(state='disabled')
                self.status.set(str(value))
            if kind == 'login':
                self.continue_button.configure(state='normal')
            elif kind == 'progress':
                self.continue_button.configure(state='disabled')
                self.progress['value'] = value[0] * 100 / value[1]
                self.status.set(f'Consultadas {value[0]} de {value[1]} filas.')
            elif kind == 'output':
                self.last_output = value
                self.open_result.configure(state='normal')
            elif kind == 'error':
                messagebox.showerror('No se pudo completar', value)
            elif kind == 'done':
                self.running = False
                for field in [*self.fields, self.check, self.run]:
                    field.configure(state='normal')
                self.cancel.configure(state='disabled')
                self.continue_button.configure(state='disabled')
                if self.stop.is_set():
                    self.status.set('Ejecución detenida.')
        self.root.after(100, self.poll)

    def cancel_run(self):
        self.stop.set()
        self.resume.set()
        self.status.set('Deteniendo al terminar la operación actual…')

    def open_output(self):
        if self.last_output:
            os.startfile(self.last_output)

    def close(self):
        if self.running:
            messagebox.showinfo('Operación en curso', 'Pulsa Detener y espera antes de cerrar. La autorización OAuth puede tardar hasta cinco minutos.')
            return
        self.root.destroy()


def main():
    root = tk.Tk()
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
