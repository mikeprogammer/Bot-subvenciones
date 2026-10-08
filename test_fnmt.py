import base64
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ObjectIdentifier
from fnmt import decode_certificate, choose_certificate, rules_for, certificate_policy


class FnmtTests(unittest.TestCase):
    def row(self, oid='1.3.6.1.4.1.5734.3.10.1', expired=False, private=True):
        now = datetime.now(timezone.utc)
        key = ec.generate_private_key(ec.SECP256R1())
        cert = (x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'PERSONA PRUEBA')]))
                .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'AC FNMT Usuarios')]))
                .public_key(key.public_key()).serial_number(123)
                .not_valid_before(now - timedelta(days=10))
                .not_valid_after(now + timedelta(days=-1 if expired else 10))
                .add_extension(x509.CertificatePolicies([x509.PolicyInformation(ObjectIdentifier(oid), None)]), False)
                .sign(key, hashes.SHA256()))
        return {'der': base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode(),
                'private': private, 'thumbprint': 'ABC'}

    def test_only_current_personal_with_private_key(self):
        self.assertEqual(decode_certificate(self.row())['issuer'], 'AC FNMT Usuarios')
        self.assertIsNone(decode_certificate(self.row(oid='1.3.6.1.4.1.5734.3.11.2')))
        self.assertIsNone(decode_certificate(self.row(expired=True)))
        self.assertIsNone(decode_certificate(self.row(private=False)))

    def test_no_silent_choice_between_people_or_renewals(self):
        first = decode_certificate(self.row())
        second = dict(first, thumbprint='DEF', subject='OTRA PERSONA')
        with self.assertRaises(ValueError):
            choose_certificate([first, second])
        self.assertEqual(choose_certificate([first, second], 'D E F'), second)
        with self.assertRaisesRegex(ValueError, 'mismo titular'):
            choose_certificate([first, dict(first, thumbprint='DEF')], 'ABC')
        with self.assertRaises(ValueError):
            choose_certificate([], '')

    def test_rules_match_subject_and_issuer_and_exact_https_origin(self):
        import json
        cert = decode_certificate(self.row())
        rule = json.loads(rules_for(cert, 'https://auth.example.com')[0])
        self.assertEqual(rule['filter']['SUBJECT']['CN'], 'PERSONA PRUEBA')
        self.assertEqual(rule['filter']['ISSUER']['CN'], 'AC FNMT Usuarios')
        for url in ('https://*.example.com', 'http://example.com', 'https://example.com/path', 'https://user@example.com'):
            with self.assertRaises(ValueError):
                rules_for(cert, url)

    def test_policy_restores_after_failed_browser_preserving_existing(self):
        cert = decode_certificate(self.row())
        import winreg
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
        registry.KEY_READ = winreg.KEY_READ
        registry.KEY_WRITE = winreg.KEY_WRITE
        registry.REG_SZ = winreg.REG_SZ
        key = registry.CreateKeyEx.return_value.__enter__.return_value
        registry.QueryInfoKey.return_value = (0, 1, 0)
        registry.EnumValue.return_value = ('1', 'existing rule', winreg.REG_SZ)
        rule = rules_for(cert, 'https://auth.example.com')[0]
        registry.QueryValueEx.return_value = (rule, winreg.REG_SZ)
        with patch.dict('sys.modules', {'winreg': registry}), patch('fnmt.personal_certificates', return_value=[cert]):
            with self.assertRaises(RuntimeError):
                with certificate_policy({'fnmt_origins': 'https://auth.example.com'}, 'brave.exe', lambda msg: None):
                    raise RuntimeError('launch failed')
        registry.SetValueEx.assert_called_once_with(key, '2', 0, winreg.REG_SZ, rule)
        registry.DeleteValue.assert_called_once()
        self.assertEqual(registry.DeleteValue.call_args.args[1], '2')

    def test_manual_mode_does_not_access_windows_store(self):
        with patch('fnmt.personal_certificates') as read:
            with certificate_policy({'auto_fnmt': False}, 'brave.exe', lambda msg: None):
                pass
            read.assert_not_called()
