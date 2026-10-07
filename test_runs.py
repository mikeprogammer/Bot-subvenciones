import tempfile
import unittest
from pathlib import Path
from bot import new_output_path, browser_options


class RunTests(unittest.TestCase):
    def test_each_run_has_its_own_workbook(self):
        first = new_output_path('outputs/consultas')
        second = new_output_path('outputs/consultas')
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, Path('outputs/consultas'))
        self.assertEqual(first.suffix, '.xlsx')

    def test_configured_executable_and_no_silent_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'brave.exe'
            with self.assertRaises(FileNotFoundError):
                browser_options({'browser_executable': str(executable)})
            executable.touch()
            options = browser_options({'browser_executable': str(executable)})
            self.assertEqual(options['executable_path'], str(executable.resolve()))
            self.assertFalse(options['headless'])
