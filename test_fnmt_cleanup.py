"""Pruebas de retirada HKLM sin modificar el Registro real."""
import base64
import json
import queue
import re
import threading
import unittest
from unittest.mock import MagicMock, patch

from fnmt import cleanup_machine_policy, prepare_machine_cleanup, rules_for


class Registry:
    HKEY_LOCAL_MACHINE = 1
    KEY_READ = 2
    REG_SZ = 1

    def __init__(self, entries):
        self.entries = dict(entries)

    def OpenKey(self, *args):
        return MagicMock()

    def QueryInfoKey(self, key):
        return 0, len(self.entries), 0

    def EnumValue(self, key, index):
        name = list(self.entries)[index]
        return name, self.entries[name], self.REG_SZ

    def QueryValueEx(self, key, name):
        if name not in self.entries:
            raise FileNotFoundError(name)
        return self.entries[name], self.REG_SZ


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.cert = {'subject': 'PRUEBA', 'issuer': 'FNMT', 'thumbprint': 'ABC'}
        self.rule = rules_for(self.cert, 'https://auth.example.com')[0]
        self.config = {'fnmt_origins': 'https://auth.example.com', 'fnmt_thumbprint': 'ABC'}
        self.registry = Registry({'1': self.rule, '2': 'regla ajena'})
        with patch.dict('sys.modules', {'winreg': self.registry}), patch('fnmt.personal_certificates', return_value=[self.cert]):
            prepare_machine_cleanup(self.config, 'brave.exe')

    def test_snapshot_contains_only_exact_selected_rule(self):
        self.assertEqual(len(self.config['_fnmt_machine_cleanup']), 1)
        self.assertEqual(self.config['_fnmt_machine_cleanup'][0]['name'], '1')

    def test_removes_and_verifies_without_deleting_other_rules(self):
        def elevated(command, **kwargs):
            encoded = re.search(r"-EncodedCommand','([A-Za-z0-9+/=]+)'", command[-1]).group(1)
            script = base64.b64decode(encoded).decode('utf-16le')
            payload = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", script).group(1)
            self.assertEqual(json.loads(base64.b64decode(payload)), self.config['_fnmt_machine_cleanup'])
            self.assertIn('-ceq', script)
            self.assertIn('GetValueKind', script)
            self.assertNotIn('DeleteSubKey', script)
            del self.registry.entries['1']
            return MagicMock(returncode=0)
        with patch.dict('sys.modules', {'winreg': self.registry}), patch('fnmt.subprocess.run', side_effect=elevated):
            cleanup_machine_policy(self.config, MagicMock())
        self.assertEqual(self.registry.entries, {'2': 'regla ajena'})
        self.assertEqual(self.config['_fnmt_machine_cleanup'], [])

    def test_changed_value_is_preserved_without_uac(self):
        self.registry.entries['1'] = 'otra aplicación modificó el valor'
        with patch.dict('sys.modules', {'winreg': self.registry}), patch('fnmt.subprocess.run') as run:
            cleanup_machine_policy(self.config, MagicMock())
        run.assert_not_called()
        self.assertIn('1', self.registry.entries)

    def test_cancelled_uac_keeps_snapshot_and_reports_failure(self):
        with patch.dict('sys.modules', {'winreg': self.registry}), patch('fnmt.subprocess.run', return_value=MagicMock(returncode=1)):
            with self.assertRaisesRegex(RuntimeError, 'puede seguir instalada'):
                cleanup_machine_policy(self.config, MagicMock())
        self.assertTrue(self.config['_fnmt_machine_cleanup'])

    def test_exit_zero_but_rule_remaining_is_not_success(self):
        with patch.dict('sys.modules', {'winreg': self.registry}), patch('fnmt.subprocess.run', return_value=MagicMock(returncode=0)):
            with self.assertRaisesRegex(RuntimeError, 'conserva la regla'):
                cleanup_machine_policy(self.config, MagicMock())

    def test_already_removed_does_not_request_uac(self):
        del self.registry.entries['1']
        with patch.dict('sys.modules', {'winreg': self.registry}), patch('fnmt.subprocess.run') as run:
            cleanup_machine_policy(self.config, MagicMock())
        run.assert_not_called()

    def test_worker_finally_cleans_on_read_error_and_cancellation(self):
        from app import App
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                app = App.__new__(App)
                app.events = queue.Queue()
                app.stop = threading.Event()
                if cancelled:
                    app.stop.set()
                config = {'sheets_url': 'test'}
                with patch('app.prepare_machine_cleanup'), patch('app.cleanup_machine_policy') as cleanup, patch('app.read_values', side_effect=None if cancelled else RuntimeError('Sheets falla'), return_value=[['DNI']]), patch('app.parse_sheets_values', return_value=[(2, 'DNI', 'EXP', '')]):
                    app.worker(config, 'brave.exe', False)
                cleanup.assert_called_once()
                events = list(app.events.queue)
                self.assertEqual(events[-1][0], 'done')

    def test_successful_worker_cleans_after_browser_is_closed(self):
        from app import App
        from contextlib import nullcontext
        app = App.__new__(App)
        app.events = queue.Queue()
        app.stop = threading.Event()
        config = {'sheets_url': 'test', 'browser_profile': 'test', 'timeout_ms': 1000,
                  'login_url': 'test', 'form_url': 'test', 'selectors': {},
                  'run_output': 'build/test-cleanup-result.xlsx', 'delay_seconds': 0}
        context = MagicMock()
        page = MagicMock()
        context.pages = [page]
        def cleanup(*args):
            context.close.assert_called_once()
        with patch('app.prepare_machine_cleanup'), patch('app.cleanup_machine_policy', side_effect=cleanup) as clean, patch('app.read_values'), patch('app.parse_sheets_values', return_value=[(2, 'DNI', 'EXP', '')]), patch('app.certificate_policy', return_value=nullcontext()), patch('app.sync_playwright') as playwright, patch('app.browser_options', return_value={}), patch('app.automatic_login', return_value=page), patch('app.consult', return_value=('Estado', '', '', '')), patch('app.save_results'):
            playwright.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value = context
            app.worker(config, 'brave.exe', False)
        clean.assert_called_once()
        self.assertFalse(any(kind == 'error' for kind, value in app.events.queue))

    def test_cleanup_error_is_reported_before_done(self):
        from app import App
        app = App.__new__(App)
        app.events = queue.Queue()
        app.stop = threading.Event()
        with patch('app.prepare_machine_cleanup'), patch('app.read_values', side_effect=RuntimeError('Sheets')), patch('app.cleanup_machine_policy', side_effect=RuntimeError('UAC cancelado')):
            app.worker({'sheets_url': 'test'}, 'brave.exe', False)
        self.assertEqual(list(app.events.queue)[-2:], [('error', 'UAC cancelado'), ('done', None)])


if __name__ == '__main__':
    unittest.main()
