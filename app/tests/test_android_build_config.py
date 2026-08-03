from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile
import unittest

from app.editor.file_manager.android_builder.android_build_config import (
    AndroidEditorBuildConfig,
    CONFIG_RELATIVE_PATH,
    default_config,
    load_config,
    parse_build_output_line,
    powershell_arguments,
    save_config,
    validate_config,
)


class AndroidBuildConfigTests(unittest.TestCase):
    def test_default_config_is_project_specific_arm64_debug(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "My Great Game.ltproj"
            project.mkdir()
            config = default_config(project, "My Great Game")

            self.assertEqual(
                "org.lextalionis.my_great_game",
                config.package_id,
            )
            self.assertEqual("arm64-v8a", config.arch)
            self.assertEqual("debug", config.mode)
            self.assertFalse(config.runtime_debugger)
            self.assertEqual([], validate_config(config))

    def test_config_round_trip_uses_project_build_folder(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "sample.ltproj"
            project.mkdir()
            config = AndroidEditorBuildConfig(
                package_id="com.example.sample",
                app_name="Sample Game",
                version_name="1.2.3",
                version_code=123,
                output_directory=str(project.parent / "android-output"),
            )

            saved_path = save_config(project, config)
            loaded, warning = load_config(project)

            self.assertEqual(project / CONFIG_RELATIVE_PATH, saved_path)
            self.assertIsNone(warning)
            self.assertEqual(config, loaded)
            payload = json.loads(saved_path.read_text(encoding="utf-8"))
            self.assertEqual(5, payload["phase"])
            self.assertNotIn("password", payload)
            self.assertNotIn("keystore", payload)

    def test_bad_saved_config_falls_back_without_crashing(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "sample.ltproj"
            path = project / CONFIG_RELATIVE_PATH
            path.parent.mkdir(parents=True)
            path.write_text("{broken", encoding="utf-8")

            loaded, warning = load_config(project)

            self.assertIsNotNone(warning)
            self.assertEqual("debug", loaded.mode)

    def test_tracked_release_config_supplies_identity_when_editor_config_is_absent(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "sample.ltproj"
            project.mkdir()
            (project / "android-release.json").write_text(
                json.dumps(
                    {
                        "package_id": "org.example.sample",
                        "app_name": "Sample Game",
                        "version_name": "9.9.9",
                        "version_code": 999,
                    }
                ),
                encoding="utf-8",
            )

            loaded, warning = load_config(project)

            self.assertIsNone(warning)
            self.assertEqual("org.example.sample", loaded.package_id)
            self.assertEqual("9.9.9", loaded.version_name)
            self.assertEqual(999, loaded.version_code)
            self.assertTrue(loaded.output_directory)

    def test_release_and_invalid_identity_are_validated_independently(self):
        config = AndroidEditorBuildConfig(
            package_id="Org.Bad",
            app_name="",
            version_name="1",
            version_code=0,
            arch="x86_64",
            mode="release",
            output_directory="",
        )
        errors = validate_config(config)
        self.assertGreaterEqual(len(errors), 5)
        self.assertFalse(any("Build mode" in error for error in errors))

    def test_release_mode_is_forwarded_to_the_powershell_builder(self):
        config = AndroidEditorBuildConfig(
            package_id="com.example.sample",
            app_name="Sample Game",
            version_name="2.0.0",
            version_code=200,
            mode="release",
            output_directory=r"E:\Build Output",
        )

        arguments = powershell_arguments(
            Path(r"E:\repo\build_runtime.ps1"),
            Path(r"E:\Games\Sample.ltproj"),
            config,
        )

        self.assertEqual("release", arguments[arguments.index("-Mode") + 1])

    def test_release_mode_is_labeled_as_development_signed(self):
        dialog = (
            Path(__file__).resolve().parents[1]
            / "editor"
            / "file_manager"
            / "android_builder"
            / "android_build_dialog.py"
        ).read_text(encoding="utf-8")

        self.assertIn("Release optimized", dialog)
        self.assertIn("development signed", dialog)
        self.assertIn("not for Play Store", dialog)

    def test_powershell_arguments_are_structured_and_include_icon(self):
        config = AndroidEditorBuildConfig(
            package_id="com.example.sample",
            app_name="Sample Game",
            version_name="2.0.0",
            version_code=200,
            icon=r"E:\Icons\sample.png",
            output_directory=r"E:\Build Output",
        )
        arguments = powershell_arguments(
            Path(r"E:\repo\build_runtime.ps1"),
            Path(r"E:\Games\Sample.ltproj"),
            config,
        )

        self.assertIn("-Project", arguments)
        self.assertIn(r"E:\Games\Sample.ltproj", arguments)
        self.assertIn(r"E:\Build Output", arguments)
        self.assertIn("-Icon", arguments)
        self.assertIn(r"E:\Icons\sample.png", arguments)
        self.assertNotIn(" ".join(arguments), arguments)

    def test_runtime_debugger_is_an_explicit_build_option(self):
        config = AndroidEditorBuildConfig(
            package_id="com.example.sample",
            app_name="Sample Game",
            version_name="2.0.0",
            version_code=200,
            runtime_debugger=True,
            output_directory=r"E:\Build Output",
        )
        arguments = powershell_arguments(
            Path(r"E:\repo\build_runtime.ps1"),
            Path(r"E:\Games\Sample.ltproj"),
            config,
        )

        self.assertIn("-EnableRuntimeDebugger", arguments)

    def test_non_square_android_icon_is_rejected_before_build(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            icon = Path(temporary_dir) / "title_background.png"
            icon.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + struct.pack(">I", 13)
                + b"IHDR"
                + struct.pack(">II", 240, 160)
            )
            config = AndroidEditorBuildConfig(
                package_id="com.example.sample",
                app_name="Sample Game",
                version_name="1.0.0",
                version_code=100,
                icon=str(icon),
                output_directory=str(Path(temporary_dir) / "output"),
            )

            errors = validate_config(config)

            self.assertTrue(
                any(
                    "square and at least 48x48" in error
                    and "240x160" in error
                    for error in errors
                )
            )

    def test_square_android_icon_passes_editor_validation(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            icon = Path(temporary_dir) / "icon.png"
            icon.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + struct.pack(">I", 13)
                + b"IHDR"
                + struct.pack(">II", 96, 96)
            )
            config = AndroidEditorBuildConfig(
                package_id="com.example.sample",
                app_name="Sample Game",
                version_name="1.0.0",
                version_code=100,
                icon=str(icon),
                output_directory=str(Path(temporary_dir) / "output"),
            )

            self.assertEqual([], validate_config(config))

    def test_build_output_parser_maps_wsl_artifacts_to_selected_output(self):
        output = Path(r"E:\Build Output")
        artifact = parse_build_output_line(
            "ARTIFACT_DIR: /mnt/e/Build Output/sample-android-1.0.0-hash",
            output,
        )
        apk = parse_build_output_line(
            "APK: /mnt/e/Build Output/sample-android-1.0.0-hash/sample.apk",
            output,
            artifact.artifact_dir,
        )
        verified = parse_build_output_line(
            "\x1b[32mANDROID_APK_VERIFIED package=com.example.sample\x1b[0m",
            output,
        )
        signed = parse_build_output_line(
            "ANDROID_DEVELOPMENT_APK_SIGNED apk=/tmp/sample.apk",
            output,
        )

        self.assertEqual(
            str(output / "sample-android-1.0.0-hash"),
            artifact.artifact_dir,
        )
        self.assertEqual(
            str(output / "sample-android-1.0.0-hash" / "sample.apk"),
            apk.apk_path,
        )
        self.assertEqual(90, verified.progress)
        self.assertEqual(84, signed.progress)
        self.assertEqual("Release APK development-signed", signed.description)


if __name__ == "__main__":
    unittest.main()
