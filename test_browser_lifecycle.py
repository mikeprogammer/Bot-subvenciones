import unittest
from unittest.mock import MagicMock, patch
import bot
from app import friendly_error


class BrowserLifecycleTests(unittest.TestCase):
    def test_closed_tab_stops_before_navigation(self):
        page = MagicMock()
        page.is_closed.return_value = True
        with self.assertRaisesRegex(RuntimeError, 'se ha cerrado'):
            bot.consult(page, 'https://example.com/form', {}, 'DNI', 'EXP')
        page.goto.assert_not_called()

    def test_authenticated_form_uses_clear_and_keeps_current_tab(self):
        page = MagicMock()
        page.is_closed.return_value = False
        page.url = 'https://example.com/form'
        reset = page.get_by_role.return_value
        reset.count.return_value = 1
        reset.is_visible.return_value = True
        selectors = {k: k for k in ('titular', 'dni', 'expediente', 'buscar', 'resultado')}
        blocks = [{'text': "No s'ha trobat cap expedient amb aquestes dades", 'links': []}]
        with patch('bot.visible_result_blocks', side_effect=[[], blocks]):
            result = bot.consult(page, page.url, selectors, '123', 'EXP')
        reset.click.assert_called_once()
        page.goto.assert_not_called()
        self.assertEqual(result[0], 'Expediente no encontrado')

    def test_target_closed_error_is_understandable(self):
        error = RuntimeError('Target page, context or browser has been closed')
        self.assertIn('Mantén abierta', friendly_error(error))
