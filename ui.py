"""Presentación CustomTkinter; las operaciones permanecen en app.App."""
import os
import tkinter as tk
from pathlib import Path
import customtkinter as ctk

COLORS = {
    'accent': '#2563EB', 'background': ('#F3F4F6', '#111827'),
    'card': ('#FFFFFF', '#1F2937'), 'border': ('#E5E7EB', '#374151'),
    'text': ('#111827', '#F9FAFB'), 'secondary': ('#6B7280', '#9CA3AF'),
    'success': '#16A34A', 'error': '#DC2626', 'warning': '#D97706',
    'hover': ('#EFF6FF', '#334155'), 'log': ('#F9FAFB', '#111827'),
}


def create_root():
    ctk.set_appearance_mode('light')
    return ctk.CTk()


class Progress(ctk.CTkProgressBar):
    """Conserva la escala 0–100 usada por el controlador."""
    def __setitem__(self, key, value):
        if key != 'value':
            raise KeyError(key)
        self.stop()
        self.configure(mode='determinate')
        self.set(value / 100)


class CertificatePicker(ctk.CTkComboBox):
    def __setitem__(self, key, value):
        if key != 'values':
            raise KeyError(key)
        self.configure(values=value or ['Automático: único FNMT personal vigente'])


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.window, self.timer = widget, text, None, None
        widget.bind('<Enter>', self.schedule, add='+')
        widget.bind('<Leave>', self.hide, add='+')
        widget.bind('<FocusOut>', self.hide, add='+')

    def schedule(self, event=None):
        self.hide()
        self.timer = self.widget.after(600, self.show)

    def show(self):
        self.timer = None
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.geometry(f'+{self.widget.winfo_rootx()+12}+{self.widget.winfo_rooty()+35}')
        tk.Label(self.window, text=self.text, background='#111827', foreground='white', padx=10, pady=6, font=('Segoe UI', 10)).pack()

    def hide(self, event=None):
        if self.timer:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.window:
            self.window.destroy()
            self.window = None


class Interface:
    def __init__(self, app):
        self.app = app
        self.errors = {}
        self.entries = {}
        self.failed = False
        root = app.root
        root.configure(fg_color=COLORS['background'])
        root.geometry('1000x820')
        root.minsize(900, 720)
        page = ctk.CTkScrollableFrame(root, fg_color=COLORS['background'], corner_radius=0)
        page.pack(fill='both', expand=True)
        page.grid_columnconfigure(0, weight=1)
        self.page = page
        header = ctk.CTkFrame(page, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=24, pady=(20, 16))
        header.grid_columnconfigure(0, weight=1)
        self.label(header, 'Consulta de expedientes', 22, True).grid(row=0, column=0, sticky='w')
        self.label(header, 'Google Sheets → Brave / FNMT → Excel nuevo por ejecución', 13, muted=True).grid(row=1, column=0, sticky='w', pady=(4, 0))
        ctk.CTkSwitch(header, text='Tema oscuro', font=('Segoe UI', 12), progress_color=COLORS['accent'], command=lambda: ctk.set_appearance_mode('dark' if theme.get() else 'light'), variable=(theme := tk.IntVar())).grid(row=0, column=1, padx=(16, 0))
        app.variables, app.fields = {}, []
        card = self.card(1, 'Origen y resultados')
        self.field(card, 0, 'sheets_url', 'URL de Google Sheets', placeholder='https://docs.google.com/spreadsheets/d/…')
        self.field(card, 1, 'output_dir', 'Carpeta de resultados', 'dir')
        cert = self.card(2, 'Certificado FNMT')
        app.certificates = {}
        app.certificate_label = tk.StringVar(value='Automático: único FNMT personal vigente')
        app.certificate_picker = CertificatePicker(cert, variable=app.certificate_label, values=[app.certificate_label.get()], state='readonly', font=('Segoe UI', 13), dropdown_font=('Segoe UI', 13), fg_color=COLORS['card'], border_color=COLORS['border'], button_color=COLORS['border'], button_hover_color=COLORS['hover'], text_color=COLORS['text'], corner_radius=8, height=36)
        app.certificate_picker.grid(row=1, column=0, sticky='ew', padx=(0, 12))
        self.errors['certificate'] = self.label(cert, '', 12)
        self.errors['certificate'].grid(row=2, column=0, sticky='w')
        detect = self.button(cert, '↻  Detectar certificados', app.detect_certificates)
        detect.grid(row=1, column=1, sticky='ew')
        setup = self.button(cert, 'Configurar FNMT (administrador)', app.setup_certificate_policy)
        setup.grid(row=3, column=0, sticky='w', pady=(8, 0))
        app.fields.extend([detect, setup])
        self.label(cert, 'Sin PFX ni contraseña. La selección del titular se recuerda entre ejecuciones.', 12, muted=True).grid(row=4, column=0, columnspan=2, sticky='w', pady=(8, 0))
        advanced_card = self.card(3)
        self.advanced_button = self.button(advanced_card, '▸  Avanzado', self.toggle_advanced)
        self.advanced_button.grid(row=0, column=0, sticky='w')
        self.advanced = ctk.CTkFrame(advanced_card, fg_color='transparent')
        self.advanced.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(12, 0))
        self.advanced.grid_columnconfigure((0, 1), weight=1, uniform='advanced')
        for index, (key, label, browse, hint) in enumerate([
            ('oauth_credentials', 'Credenciales OAuth (.json)', 'json', 'JSON de una aplicación de escritorio de Google Cloud.'),
            ('browser_executable', 'Ruta del navegador', 'exe', 'Introduce la ruta completa del ejecutable del navegador.'),
            ('dni_column', 'Columna DNI', None, 'Nombre exacto de la columna en Sheets.'),
            ('expediente_column', 'Columna de expediente', None, 'Nombre exacto de la columna en Sheets.'),
            ('header_row', 'Fila de encabezados', None, 'Número de fila que contiene los nombres de las columnas.'),
            ('fnmt_origins', 'Dominios con certificado (HTTPS, separados por comas)', None, 'Orígenes HTTPS del acceso con certificado, separados por comas.'),
        ]):
            self.field(self.advanced, index, key, label, browse, hint=hint)
        self.advanced.grid_remove()
        activity = self.card(4, 'Actividad')
        toolbar = ctk.CTkFrame(activity, fg_color='transparent')
        toolbar.grid(row=1, column=0, columnspan=2, sticky='ew')
        app.check = self.button(toolbar, 'Probar lectura de Sheets', lambda: app.start(True))
        app.check.pack(side='left')
        app.run = self.button(toolbar, '▶  Consultar y crear Excel', lambda: app.start(False), primary=True)
        app.run.pack(side='left', padx=10)
        app.cancel = self.button(toolbar, '■  Detener', app.cancel_run, danger=True)
        app.cancel.pack(side='right')
        app.cancel.configure(state='disabled')
        app.continue_button = self.button(toolbar, 'Ya veo el formulario FNMT', app.resume.set)
        app.continue_button.configure(state='disabled')
        app.status = tk.StringVar(value='Listo')
        state_line = ctk.CTkFrame(activity, fg_color='transparent')
        state_line.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(16, 8))
        self.dot = self.label(state_line, '●', 13)
        self.dot.pack(side='left', padx=(0, 8))
        self.label(state_line, '', 13, variable=app.status).pack(side='left')
        app.progress = Progress(activity, height=7, corner_radius=4, progress_color=COLORS['accent'], fg_color=COLORS['border'])
        app.progress.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(0, 12))
        app.progress.set(0)
        app.log = ctk.CTkTextbox(activity, height=150, font=('Consolas', 12), fg_color=COLORS['log'], text_color=COLORS['text'], border_width=1, border_color=COLORS['border'], corner_radius=8, wrap='word', state='disabled')
        app.log.grid(row=4, column=0, columnspan=2, sticky='ew')
        for level, color in [('success', COLORS['success']), ('warning', COLORS['warning']), ('error', COLORS['error'])]:
            app.log.tag_config(level, foreground=color)
        footer = ctk.CTkFrame(activity, fg_color='transparent')
        footer.grid(row=5, column=0, columnspan=2, sticky='ew', pady=(12, 0))
        self.button(footer, 'Copiar log', self.copy_log).pack(side='left')
        self.button(footer, 'Limpiar', self.clear_log).pack(side='left', padx=8)
        app.open_result = self.button(footer, 'Abrir Excel generado', app.open_output)
        app.open_result.pack(side='right')
        app.open_result.configure(state='disabled')
        self.open_folder = self.button(footer, 'Abrir carpeta de resultados', self.open_results)
        self.open_folder.pack(side='right', padx=8)
        self.open_folder.configure(state='disabled')
        app.status.trace_add('write', self.update_status)

    def label(self, parent, text, size=13, bold=False, muted=False, variable=None):
        return ctk.CTkLabel(parent, text=text, textvariable=variable, font=('Segoe UI', size, 'bold' if bold else 'normal'), text_color=COLORS['secondary'] if muted else COLORS['text'], anchor='w')

    def card(self, row, title=None):
        outer = ctk.CTkFrame(self.page, corner_radius=12, fg_color=COLORS['card'], border_width=1, border_color=COLORS['border'])
        outer.grid(row=row, column=0, sticky='ew', padx=24, pady=(0, 16))
        inner = ctk.CTkFrame(outer, fg_color='transparent')
        inner.pack(fill='both', expand=True, padx=22, pady=20)
        inner.grid_columnconfigure((0, 1), weight=1, uniform='card')
        if title:
            self.label(inner, title, 15, True).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 12))
        return inner

    def button(self, parent, text, command, primary=False, danger=False):
        return ctk.CTkButton(parent, text=text, command=command, font=('Segoe UI', 13), height=36, corner_radius=8, border_width=0 if primary else 1, border_color=COLORS['border'], fg_color=COLORS['accent'] if primary else (('#FEF2F2', '#44232B') if danger else COLORS['card']), hover_color='#1D4ED8' if primary else COLORS['hover'], text_color='white' if primary else (COLORS['error'] if danger else COLORS['text']))

    def field(self, parent, index, key, label, browse=None, placeholder=None, hint=None):
        group = ctk.CTkFrame(parent, fg_color='transparent')
        group.grid(row=1 + index // 2, column=index % 2, sticky='ew', padx=(0, 8) if index % 2 == 0 else (8, 0), pady=(0, 8))
        group.grid_columnconfigure(0, weight=1)
        self.label(group, label, 12 if key == 'fnmt_origins' else 13).grid(row=0, column=0, columnspan=2, sticky='w')
        variable = tk.StringVar(value=self.app.settings[key])
        self.app.variables[key] = variable
        entry = ctk.CTkEntry(group, textvariable=variable, placeholder_text=placeholder, height=36, corner_radius=8, border_width=1, border_color=COLORS['border'], fg_color=COLORS['card'], text_color=COLORS['text'], font=('Segoe UI', 13))
        entry.grid(row=1, column=0, sticky='ew')
        entry.bind('<FocusIn>', lambda e: entry.configure(border_color=COLORS['accent']), add='+')
        entry.bind('<FocusOut>', lambda e: entry.configure(border_color=COLORS['error'] if self.errors[key].cget('text') else COLORS['border']), add='+')
        self.app.fields.append(entry)
        self.entries[key] = entry
        error = self.label(group, '', 12)
        error.configure(text_color=COLORS['error'])
        error.grid(row=2, column=0, columnspan=2, sticky='w')
        self.errors[key] = error
        if browse:
            button = self.button(group, '📁  Examinar…', lambda: self.app.browse(key, browse))
            button.grid(row=1, column=1, padx=(8, 0))
            self.app.fields.append(button)
        if hint:
            Tooltip(entry, hint)

    def toggle_advanced(self):
        if self.advanced.winfo_manager():
            self.advanced.grid_remove()
            self.advanced_button.configure(text='▸  Avanzado')
        else:
            self.advanced.grid()
            self.advanced_button.configure(text='▾  Avanzado')

    def show_error(self, key, text):
        self.errors[key].configure(text=text, text_color=COLORS['error'])
        if key in self.entries:
            self.entries[key].configure(border_color=COLORS['error'])
        if key not in ('sheets_url', 'output_dir', 'certificate') and not self.advanced.winfo_manager():
            self.toggle_advanced()

    def validate(self):
        from sheets_api import sheet_identity
        for key, label in self.errors.items():
            label.configure(text='')
        for entry in self.entries.values():
            entry.configure(border_color=COLORS['border'])
        values = {k: v.get().strip() for k, v in self.app.variables.items()}
        try:
            sheet_identity(values['sheets_url'])
        except ValueError:
            self.show_error('sheets_url', 'Indica una URL válida de Google Sheets.')
        try:
            if not values['oauth_credentials'] or not Path(values['oauth_credentials']).is_file():
                self.show_error('oauth_credentials', 'Selecciona un archivo JSON existente.')
        except OSError:
            self.show_error('oauth_credentials', 'No se puede acceder al archivo.')
        try:
            if int(values['header_row']) < 1:
                raise ValueError()
        except ValueError:
            self.show_error('header_row', 'Introduce un número entero mayor que cero.')
        for key in ('dni_column', 'expediente_column'):
            if not values[key]:
                self.show_error(key, 'Indica el nombre de la columna.')
        try:
            if not values['output_dir']:
                raise ValueError()
            Path(values['output_dir']).mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError):
            self.show_error('output_dir', 'Selecciona una carpeta existente o creable.')
        if self.app.certificates and self.app.certificate_label.get() not in self.app.certificates:
            self.show_error('certificate', 'Selecciona el certificado del titular.')
        valid = not any(label.cget('text') for label in self.errors.values())
        if not valid:
            self.app.status.set('Error: revisa los campos indicados.')
        return valid

    def update_status(self, *args):
        text = self.app.status.get().lower()
        color = COLORS['error'] if text.startswith('error') else COLORS['warning'] if self.app.running else COLORS['success'] if ('completada' in text or 'detectados' in text) else COLORS['secondary']
        self.dot.configure(text_color=color)

    def append_log(self, value):
        text = str(value)
        lower = text.lower()
        level = 'error' if any(s in lower for s in ('error', 'no se pudo')) else 'warning' if any(s in lower for s in ('aviso', 'advertencia', 'deten')) else 'success' if any(s in lower for s in ('guardado', 'creado', 'detectados', 'autorizado')) else None
        self.app.log.configure(state='normal')
        self.app.log.insert('end', text + '\n', (level,) if level else ())
        self.app.log.see('end')
        self.app.log.configure(state='disabled')

    def copy_log(self):
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(self.app.log.get('1.0', 'end-1c'))

    def clear_log(self):
        self.app.log.configure(state='normal')
        self.app.log.delete('1.0', 'end')
        self.app.log.configure(state='disabled')

    def open_results(self):
        folder = Path(self.app.last_output).parent if self.app.last_output else Path(self.app.variables['output_dir'].get())
        os.startfile(str(folder))
