"""Prueba de los clics en Brave sobre una sede simulada, sin certificado real."""
import tempfile
import threading
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from auto_login import automatic_login
from bot import browser_options


def main():
    with tempfile.TemporaryDirectory() as profile, sync_playwright() as p:
        context = p.chromium.launch_persistent_context(profile, **browser_options({}), timeout=15000)
        try:
            bodies = {
                '/': '<a role=button href=/ident>Entra</a>',
                '/ident': '<a role=button href=/form target=_blank><span>Acceso DNIe / Certificado electrónico</span></a>',
                '/form': '<input id="titular"><input id="dni"><input id="exp"><button id="buscar">Cerca</button>',
            }
            context.route('https://bot-test.invalid/**', lambda route: route.fulfill(body=bodies.get(urlsplit(route.request.url).path, ''), content_type='text/html'))
            page = context.pages[0] if context.pages else context.new_page()
            page.goto('https://bot-test.invalid/')
            config = {'form_url': 'https://bot-test.invalid/form', 'timeout_ms': 5000,
                      'selectors': {'titular': '#titular', 'dni': '#dni', 'expediente': '#exp', 'buscar': '#buscar'}}
            result = automatic_login(context, config, threading.Event(), print)
            assert result.url.endswith('/form')
            assert len(context.pages) == 2
            stopped = threading.Event()
            stopped.set()
            assert automatic_login(context, config, stopped, print) is None
        finally:
            context.close()
    print('Acceso automático, formulario en pestaña nueva y cancelación: OK. FNMT real no probado.')


if __name__ == '__main__':
    main()
