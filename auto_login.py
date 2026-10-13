"""Acceso FNMT mediante certificado TLS, sin manipular diálogos Windows."""
import re
import time
from bot import find_form
from playwright.sync_api import Error as BrowserError


def automatic_login(context, config, stop, log):
    deadline = time.monotonic() + 120
    clicked = set()
    patterns = [re.compile(r'^\s*(Entra|Entrar)\s*$', re.I),
                re.compile(r'certifica(?:do|t)|DNI\s*(?:electr[oó]nico|e\b)', re.I)]
    while time.monotonic() < deadline:
        if stop.is_set():
            return None
        form = find_form(context, config['form_url'], config['selectors'])
        if form is not None:
            log('Autenticación completada. Formulario detectado; iniciando consultas.')
            return form
        if not context.pages:
            raise RuntimeError('El navegador se ha cerrado durante el acceso.')
        action_taken = False
        for page in list(context.pages):
            if page.is_closed():
                continue
            for frame in page.frames:
                for step, pattern in enumerate(patterns):
                    token = (id(page), frame.url, step)
                    if token in clicked:
                        continue
                    candidates = frame.get_by_role('button', name=pattern).or_(frame.get_by_role('link', name=pattern))
                    try:
                        visible = [candidates.nth(i) for i in range(candidates.count()) if candidates.nth(i).is_visible()]
                        if not visible and step == 0:
                            candidates = frame.get_by_text(pattern)
                            visible = [candidates.nth(i) for i in range(candidates.count()) if candidates.nth(i).is_visible()]
                    except BrowserError as exc:
                        if any(word in str(exc).lower() for word in ('destroyed', 'detached', 'navigation')):
                            continue
                        raise
                    if len(visible) > 1:
                        raise RuntimeError('Hay varios botones de acceso coincidentes. Debe ajustarse el selector antes de continuar.')
                    if len(visible) == 1:
                        visible[0].click(timeout=config['timeout_ms'])
                        clicked.add(token)
                        log('Pulsado Entra.' if step == 0 else 'Elegido acceso mediante certificado.')
                        action_taken = True
                        break
                if action_taken:
                    break
            if action_taken:
                break
        if context.pages:
            context.pages[0].wait_for_timeout(300)
    raise RuntimeError('No se ha detectado el formulario en 120 segundos. Revisa los dominios FNMT y los botones de acceso. No se han realizado consultas.')
