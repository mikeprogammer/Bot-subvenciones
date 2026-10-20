"""Reintento manual desde la interfaz; no modifica el Registro real."""
import queue
import unittest
from unittest.mock import MagicMock, patch
from app import App


class ManualCleanupTests(unittest.TestCase):
    def make_app(self):
        app = App.__new__(App)
        app.running = False
        app.fnmt_busy = False
        app.pending_cleanup = []
        app.events = queue.Queue()
        app.variables = {k: MagicMock() for k in ('fnmt_origins', 'browser_executable')}
        app.variables['fnmt_origins'].get.return_value = 'https://auth.example.com'
        app.variables['browser_executable'].get.return_value = 'brave.exe'
        app.settings = {}
        app.certificates = {'Titular': 'ABC'}
        app.certificate_label = MagicMock()
        app.certificate_label.get.return_value = 'Titular'
        app.status = MagicMock()
        app.fields = [MagicMock()]
        app.check = MagicMock()
        app.run = MagicMock()
        app.certificate_picker = MagicMock()
        app.root = MagicMock()
        return app

    def test_pending_snapshot_is_used_even_if_selection_changes(self):
        app = self.make_app()
        entry = {'path': 'original browser', 'name': '1', 'value': 'original value'}
        app.pending_cleanup = [entry]
        app.certificates = {'Otro titular': 'DEF'}
        with patch('app.threading.Thread') as thread, patch('app.browser_options') as browser, patch('app.prepare_machine_cleanup') as prepare, patch('app.cleanup_machine_policy') as cleanup:
            app.remove_certificate_policy()
            self.assertTrue(app.fnmt_busy)
            thread.call_args.kwargs['target']()
            cleanup.assert_called_once()
            self.assertEqual(cleanup.call_args.args[0]['_fnmt_machine_cleanup'], [entry])
        prepare.assert_not_called()
        browser.assert_not_called()
        app.poll()
        self.assertEqual(app.pending_cleanup, [])
        self.assertFalse(app.fnmt_busy)

    def test_cancelled_manual_uac_preserves_pending_and_reenables(self):
        app = self.make_app()
        entry = {'path': 'browser', 'name': '1', 'value': 'rule'}
        app.pending_cleanup = [entry]
        with patch('app.threading.Thread') as thread, patch('app.cleanup_machine_policy', side_effect=RuntimeError('UAC cancelado')):
            app.remove_certificate_policy()
            thread.call_args.kwargs['target']()
        app.ui = MagicMock()
        app.log_path = None
        app.poll()
        self.assertEqual(app.pending_cleanup, [entry])
        self.assertFalse(app.fnmt_busy)
        app.status.set.assert_called_with('Error: UAC cancelado')

    def test_without_pending_uses_selection_without_sheets_config(self):
        app = self.make_app()
        with patch('app.threading.Thread') as thread, patch('app.browser_options', return_value={'executable_path': 'brave.exe'}), patch('app.prepare_machine_cleanup') as prepare, patch.object(app, 'config') as sheets_config, patch('app.cleanup_machine_policy') as cleanup:
            app.remove_certificate_policy()
            thread.call_args.kwargs['target']()
        prepare.assert_called_once()
        sheets_config.assert_not_called()
        cleanup.assert_not_called()
        self.assertIn(('log', 'No hay reglas permanentes coincidentes con el certificado y dominios seleccionados.'), list(app.events.queue))

    def test_no_manual_cleanup_during_run_or_other_fnmt_operation(self):
        for running, busy in [(True, False), (False, True)]:
            app = self.make_app()
            app.running, app.fnmt_busy = running, busy
            with patch('app.threading.Thread') as thread:
                app.remove_certificate_policy()
            thread.assert_not_called()


if __name__ == '__main__':
    unittest.main()
