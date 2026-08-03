from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sign_apk import (
    DevelopmentSigningError,
    check_development_key,
    development_signer_certificate,
    sign_development_apk,
)
from verify_apk import CERTIFICATE_RE


class DevelopmentSigningTests(unittest.TestCase):
    def test_verifier_reads_current_apksigner_certificate_format(self):
        output = (
            "V3.0 Signer: certificate DN: C=US, O=Android, CN=Android Debug\n"
            "V3.0 Signer: certificate SHA-256 digest: "
            "fa4a28469cfc207988510dfeb5609fd097c3c3360ae46363287bd0ba7ce8c1e4\n"
        )

        match = CERTIFICATE_RE.search(output)

        self.assertIsNotNone(match)
        self.assertEqual(
            "fa4a28469cfc207988510dfeb5609fd097c3c3360ae46363287bd0ba7ce8c1e4",
            match.group("digest") if match else None,
        )

    def test_toolchain_declares_existing_development_signer(self):
        self.assertEqual(
            "fa4a28469cfc207988510dfeb5609fd097c3c3360ae46363287bd0ba7ce8c1e4",
            development_signer_certificate(),
        )

    def test_check_rejects_missing_development_keystore(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            missing = Path(temporary_dir) / "debug.keystore"

            with self.assertRaisesRegex(DevelopmentSigningError, "not found"):
                check_development_key(
                    missing,
                    Path("keytool"),
                    "a" * 64,
                )

    def test_check_rejects_development_certificate_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            keystore = Path(temporary_dir) / "debug.keystore"
            keystore.write_bytes(b"development key")

            with patch("sign_apk.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess(
                    ["keytool"], 0, stdout=b"certificate", stderr=b""
                )

                with self.assertRaisesRegex(DevelopmentSigningError, "certificate"):
                    check_development_key(
                        keystore,
                        Path("keytool"),
                        "a" * 64,
                    )

    def test_signs_to_a_new_file_without_changing_unsigned_source(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            unsigned = root / "release-unsigned.apk"
            signed = root / "release-dev-signed.apk"
            keystore = root / "debug.keystore"
            unsigned.write_bytes(b"unsigned APK payload")
            keystore.write_bytes(b"development key")
            expected_certificate = hashlib.sha256(b"certificate").hexdigest()

            def fake_run(command, **_kwargs):
                if "-exportcert" in command:
                    return subprocess.CompletedProcess(command, 0, b"certificate", b"")
                output = Path(command[command.index("--out") + 1])
                output.write_bytes(b"signed APK payload")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("sign_apk.subprocess.run", side_effect=fake_run):
                sign_development_apk(
                    unsigned,
                    signed,
                    keystore=keystore,
                    keytool=Path("keytool"),
                    apksigner=Path("apksigner"),
                    expected_certificate_sha256=expected_certificate,
                )

            self.assertEqual(b"unsigned APK payload", unsigned.read_bytes())
            self.assertEqual(b"signed APK payload", signed.read_bytes())

    def test_signing_failure_removes_temporary_output(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            unsigned = root / "release-unsigned.apk"
            signed = root / "release-dev-signed.apk"
            keystore = root / "debug.keystore"
            unsigned.write_bytes(b"unsigned APK payload")
            keystore.write_bytes(b"development key")
            expected_certificate = hashlib.sha256(b"certificate").hexdigest()

            def fake_run(command, **_kwargs):
                if "-exportcert" in command:
                    return subprocess.CompletedProcess(command, 0, b"certificate", b"")
                return subprocess.CompletedProcess(command, 1, "", "sign failed")

            with patch("sign_apk.subprocess.run", side_effect=fake_run):
                with self.assertRaisesRegex(DevelopmentSigningError, "sign failed"):
                    sign_development_apk(
                        unsigned,
                        signed,
                        keystore=keystore,
                        keytool=Path("keytool"),
                        apksigner=Path("apksigner"),
                        expected_certificate_sha256=expected_certificate,
                    )

            self.assertFalse(signed.exists())
            self.assertEqual([], list(root.glob(".release-dev-signed.apk.*.tmp")))


if __name__ == "__main__":
    unittest.main()
