import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
ANDROID_RUNTIME = REPO_ROOT / "utilities" / "build_tools" / "android_runtime"


class AndroidDataPersistenceTests(unittest.TestCase):
    def test_build_uses_migration_activity_entrypoint(self):
        spec = (ANDROID_RUNTIME / "buildozer.spec").read_text(encoding="utf-8")
        activity = (
            ANDROID_RUNTIME
            / "android_native"
            / "java"
            / "org"
            / "lextalionis"
            / "android"
            / "LtPythonActivity.java"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "android.entrypoint = org.lextalionis.android.LtPythonActivity",
            spec,
        )
        self.assertIn('new File(filesDir, "app")', activity)
        self.assertIn('new File(filesDir, "user_data")', activity)
        self.assertIn("Files.move", activity)
        self.assertIn("super.onCreate(savedInstanceState)", activity)
        self.assertLess(
            activity.index("migrateLegacySaves();"),
            activity.index("super.onCreate(savedInstanceState);"),
        )
        self.assertIn("StandardCopyOption.ATOMIC_MOVE", activity)
        self.assertNotIn("AtomicMoveNotSupportedException", activity)

    def test_android_runtime_points_player_data_outside_replaceable_app_root(self):
        main = (
            ANDROID_RUNTIME / "app_template" / "main.py"
        ).read_text(encoding="utf-8")

        self.assertIn('"LT_USER_DATA_DIR"', main)
        self.assertIn('private_root / "user_data"', main)
        self.assertIn("runtime_save_dir() / \"android_controls.json\"", main)
        self.assertNotIn('BASE_DIR / "saves"', main)

    def test_android_runtime_requires_private_storage_and_overrides_inherited_path(self):
        main_path = ANDROID_RUNTIME / "app_template" / "main.py"
        with tempfile.TemporaryDirectory() as temporary_dir:
            private_root = Path(temporary_dir) / "files"
            private_root.mkdir()
            with patch.dict(
                os.environ,
                {
                    "ANDROID_PRIVATE": str(private_root),
                    "LT_USER_DATA_DIR": "/replaceable/untrusted/location",
                },
                clear=True,
            ):
                configured = runpy.run_path(str(main_path))["configure_android_user_data"]()
                self.assertEqual(str(configured), os.environ.get("LT_USER_DATA_DIR"))

            self.assertEqual(private_root.resolve() / "user_data", configured)

        with patch.dict(os.environ, {}, clear=True):
            configure = runpy.run_path(str(main_path))["configure_android_user_data"]
            with self.assertRaisesRegex(RuntimeError, "ANDROID_PRIVATE"):
                configure()

    def test_android_payload_does_not_package_repository_saves_placeholder(self):
        prepare = (
            ANDROID_RUNTIME / "prepare_runtime.py"
        ).read_text(encoding="utf-8")
        build_script = (
            ANDROID_RUNTIME / "build_runtime.sh"
        ).read_text(encoding="utf-8")

        self.assertNotIn("save_storage.txt", prepare)
        self.assertNotIn("save_storage.txt", build_script)

    def test_apk_verifier_records_signer_and_migration_activity(self):
        verifier = (
            ANDROID_RUNTIME / "verify_apk.py"
        ).read_text(encoding="utf-8")

        self.assertIn("--print-certs", verifier)
        self.assertIn("signer_certificate_sha256", verifier)
        self.assertIn("development_signer", verifier)
        toolchain = (
            ANDROID_RUNTIME / "toolchain_manifest.json"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "fa4a28469cfc207988510dfeb5609fd097c3c3360ae46363287bd0ba7ce8c1e4",
            toolchain,
        )
        self.assertIn("migration_activity", verifier)
        self.assertIn("launchable_activity", verifier)
        self.assertIn("launcher_activity", verifier)

    def test_apk_verifier_identifies_the_actual_launcher_activity(self):
        sys.path.insert(0, str(ANDROID_RUNTIME))
        try:
            from verify_apk import launchable_activity

            self.assertEqual(
                "org.lextalionis.android.LtPythonActivity",
                launchable_activity(
                    "package: name='example'\n"
                    "launchable-activity: "
                    "name='org.lextalionis.android.LtPythonActivity' "
                    "label='Example'\n"
                ),
            )
            self.assertIsNone(launchable_activity("package: name='example'"))
        finally:
            sys.path.pop(0)


if __name__ == "__main__":
    unittest.main()
