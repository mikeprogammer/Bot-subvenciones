"""Pruebas sin acceso a Google ni a la intranet."""
import unittest

from bot import parse_sheets_csv, parse_sheets_values, sheets_export_url


class SheetsInputTests(unittest.TestCase):
    config = {"dni_column": "DNI", "expediente_column": "Nº EXPEDIENTE"}

    def test_missing_input_identifies_column_without_copying_previous_person(self):
        rows = parse_sheets_values([['DNI', 'Nº EXPEDIENTE'], ['001A', 'EXP1'],
                                   ['', 'EXP2'], ['002B'], ['003C', 'EXP3']], self.config)
        self.assertEqual(rows[1], (3, '', 'EXP2', 'Falta DNI'))
        self.assertEqual(rows[2], (4, '002B', '', 'Falta número de expediente'))
        self.assertEqual(rows[3], (5, '003C', 'EXP3', ''))

    def test_tab_url(self):
        url = "https://docs.google.com/spreadsheets/d/abc_123/edit#gid=42"
        self.assertEqual(sheets_export_url(url),
                         "https://docs.google.com/spreadsheets/d/abc_123/export?format=csv&gid=42")

    def test_reject_wrong_host_or_missing_tab(self):
        for url in ("https://example.com/spreadsheets/d/abc/edit#gid=0",
                    "https://docs.google.com/spreadsheets/d/abc/edit",
                    "https://docs.google.com/spreadsheets/d/abc/edit#gid=abc"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                sheets_export_url(url)

    def test_identifiers_blanks_and_original_row_numbers(self):
        rows = parse_sheets_csv('\ufeffDNI,Nº EXPEDIENTE,Nota\r\n00123456A,"0001,2026",x\r\n,,\r\n,0002,x\r\n12345678Z\r\n', self.config)
        self.assertEqual(rows[0], (2, "00123456A", "0001,2026", ""))
        self.assertEqual(rows[1][0], 4)
        self.assertTrue(rows[1][3])
        self.assertTrue(rows[2][3])

    def test_missing_and_duplicate_headers(self):
        for text in ("DNI,Otro\n", "DNI,DNI,Nº EXPEDIENTE\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_sheets_csv(text, self.config)


if __name__ == "__main__":
    unittest.main()
