import unittest
from unittest.mock import MagicMock
from sheets_api import fetch_values, sheet_identity, sheet_range
from bot import parse_sheets_values


class ApiTests(unittest.TestCase):
    def test_gid_and_quoted_title(self):
        url = 'https://docs.google.com/spreadsheets/d/abc/edit#gid=42'
        self.assertEqual(sheet_identity(url), ('abc', 42))
        metadata = {'sheets': [{'properties': {'sheetId': 42, 'title': "Dades d'avui"}}]}
        self.assertEqual(sheet_range(metadata, 42), "'Dades d''avui'")
        with self.assertRaises(ValueError):
            sheet_range(metadata, 0)

    def test_reads_exact_tab_with_formatted_identifiers(self):
        service = MagicMock()
        service.spreadsheets().get().execute.return_value = {'sheets': [{'properties': {'sheetId': 0, 'title': 'Hoja 1'}}]}
        service.spreadsheets().values().get().execute.return_value = {'values': [['DNI', 'Nº EXPEDIENTE'], ['00123456A', '0001'], ['12345678Z']]}
        values = fetch_values(service, 'https://docs.google.com/spreadsheets/d/abc/edit#gid=0')
        service.spreadsheets().values().get.assert_called_with(spreadsheetId='abc', range="'Hoja 1'", valueRenderOption='FORMATTED_VALUE', majorDimension='ROWS')
        rows = parse_sheets_values(values, {'dni_column': 'DNI', 'expediente_column': 'Nº EXPEDIENTE'})
        self.assertEqual(rows[0][1:3], ('00123456A', '0001'))
        self.assertTrue(rows[1][3])
