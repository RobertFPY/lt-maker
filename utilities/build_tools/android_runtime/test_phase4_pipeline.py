from __future__ import annotations

import ast
from dataclasses import asdict
import hashlib
import importlib
import json
from pathlib import Path
import py_compile
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.utilities.import_utils import import_submodules
from configure_build import configure
from prepare_runtime import (
    load_verified_preflight,
    minify_project_json,
    prune_unpackageable_project_files,
    validate_ustar_paths,
)
from preflight import (
    BuildConfig,
    PreflightReport,
    discover_project_build_config,
    load_build_config,
    run_preflight,
    snapshot_digest,
    validate_build_config,
    validate_case_collisions,
)
from publish_artifacts import publish
from validate_runtime import validate_touch_controls
from verify_apk import validate_native_abi


class Phase4PipelineTests(unittest.TestCase):
    def test_custom_component_import_cannot_decode_sprites_during_resource_load(self):
        sprite_loader_path = REPO_ROOT / "app" / "engine" / "sprites.py"
        sprite_loader_source = sprite_loader_path.read_text(encoding="utf-8")
        sprite_loader_module = ast.parse(sprite_loader_source)

        import_time_loads = [
            node
            for node in sprite_loader_module.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "load_images"
        ]
        self.assertEqual(
            [],
            import_time_loads,
            "app.engine.sprites must not decode relative sprite paths at import time",
        )

        driver_source = (
            REPO_ROOT / "app" / "engine" / "driver.py"
        ).read_text(encoding="utf-8")
        sprite_load = "sprites.load_images(force=from_editor, optimize_for_display=True)"
        self.assertIn(sprite_load, driver_source)
        self.assertLess(
            driver_source.index("engine.DISPLAYSURF = engine.build_display"),
            driver_source.index(sprite_load),
            "Sprite conversion must happen after Android has selected its display format",
        )

    def test_component_packages_support_bytecode_only_android_layout(self):
        item_init = (
            REPO_ROOT / "app" / "engine" / "item_components" / "__init__.py"
        ).read_text(encoding="utf-8")
        skill_init = (
            REPO_ROOT / "app" / "engine" / "skill_components" / "__init__.py"
        ).read_text(encoding="utf-8")
        resources = (
            REPO_ROOT / "app" / "data" / "resources" / "resources.py"
        ).read_text(encoding="utf-8")

        self.assertIn("import_submodules(__name__, __path__)", item_init)
        self.assertIn("import_submodules(__name__, __path__)", skill_init)
        self.assertIn("BYTECODE_SUFFIXES", resources)
        self.assertIn("import_submodules(", resources)

        with tempfile.TemporaryDirectory() as temporary_dir:
            package_name = "lt_bytecode_component_probe"
            package_dir = Path(temporary_dir) / package_name
            package_dir.mkdir()
            init_source = package_dir / "__init__.py"
            component_source = package_dir / "sample_component.py"
            init_source.write_text("", encoding="utf-8")
            component_source.write_text(
                "REGISTERED_FROM_BYTECODE = True\n",
                encoding="utf-8",
            )
            py_compile.compile(
                str(init_source),
                cfile=str(package_dir / "__init__.pyc"),
                doraise=True,
            )
            py_compile.compile(
                str(component_source),
                cfile=str(package_dir / "sample_component.pyc"),
                doraise=True,
            )
            init_source.unlink()
            component_source.unlink()

            sys.path.insert(0, temporary_dir)
            try:
                package = importlib.import_module(package_name)
                imported = import_submodules(package_name, package.__path__)
                self.assertEqual(
                    [f"{package_name}.sample_component"],
                    [module.__name__ for module in imported],
                )
                self.assertTrue(imported[0].REGISTERED_FROM_BYTECODE)
            finally:
                sys.path.remove(temporary_dir)
                for module_name in list(sys.modules):
                    if (
                        module_name == package_name
                        or module_name.startswith(package_name + ".")
                    ):
                        del sys.modules[module_name]

    def test_custom_components_load_from_bytecode_only_android_layout(self):
        from app.data.resources.resources import Resources

        with tempfile.TemporaryDirectory() as temporary_dir:
            resources_dir = Path(temporary_dir) / "resources"
            package_dir = resources_dir / "custom_components"
            package_dir.mkdir(parents=True)
            init_source = package_dir / "__init__.py"
            component_source = package_dir / "custom_probe.py"
            init_source.write_text("", encoding="utf-8")
            component_source.write_text(
                "REGISTERED_FROM_BYTECODE = True\n",
                encoding="utf-8",
            )
            py_compile.compile(
                str(init_source),
                cfile=str(package_dir / "__init__.pyc"),
                doraise=True,
            )
            py_compile.compile(
                str(component_source),
                cfile=str(package_dir / "custom_probe.pyc"),
                doraise=True,
            )
            init_source.unlink()
            component_source.unlink()

            resources = Resources()
            resources.main_folder = str(resources_dir)
            try:
                resources.load_components()
                custom_probe = importlib.import_module(
                    "custom_components.custom_probe"
                )
                self.assertTrue(custom_probe.REGISTERED_FROM_BYTECODE)
                self.assertTrue(
                    str(resources.loaded_custom_components_path).endswith(
                        "__init__.pyc"
                    )
                )
            finally:
                for module_name in list(sys.modules):
                    if (
                        module_name == "custom_components"
                        or module_name.startswith("custom_components.")
                    ):
                        del sys.modules[module_name]

    def test_touch_control_runtime_and_overlay_cache(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            staging = Path(temporary_dir) / "staging"
            shutil.copytree(Path(__file__).parent / "app_template", staging)
            engine_dir = staging / "app" / "engine"
            engine_dir.mkdir(parents=True)
            shutil.copy2(REPO_ROOT / "app" / "__init__.py", staging / "app")
            shutil.copy2(
                REPO_ROOT / "app" / "engine" / "android_runtime.py",
                engine_dir,
            )
            validate_touch_controls(staging)

    def test_documents_provider_is_packaged_by_build_spec(self):
        root = Path(__file__).parent
        spec = (root / "buildozer.spec").read_text(encoding="utf-8")
        manifest = (root / "android_native" / "provider_manifest.xml").read_text(
            encoding="utf-8"
        )
        provider = (
            root
            / "android_native"
            / "java"
            / "org"
            / "lextalionis"
            / "android"
            / "LtDocumentsProvider.java"
        ).read_text(encoding="utf-8")

        self.assertIn("android.add_src = ./android_native/java", spec)
        self.assertIn("p4a.hook = ./android_native/p4a_hook.py", spec)
        self.assertIn("android.content.action.DOCUMENTS_PROVIDER", manifest)
        self.assertIn("android.permission.MANAGE_DOCUMENTS", manifest)
        self.assertIn('${applicationId}.documents', manifest)
        self.assertIn("extends DocumentsProvider", provider)
        self.assertIn("getContext().getFilesDir().getParentFile()", provider)
        self.assertIn("Game files, saves, cache, and crash logs", provider)
        self.assertIn("isProtectedTopLevel", provider)
        self.assertIn("ensureInsideRoot", provider)

        hook = (root / "android_native" / "p4a_hook.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def before_apk_build", hook)
        self.assertIn("AndroidManifest.tmpl.xml", hook)

    def test_native_debug_input_overlay_is_packaged_by_build_spec(self):
        root = Path(__file__).parent
        overlay = (
            root
            / "android_native"
            / "java"
            / "org"
            / "lextalionis"
            / "android"
            / "LtDebugInputOverlay.java"
        ).read_text(encoding="utf-8")

        self.assertIn("class LtDebugInputOverlay", overlay)
        self.assertIn("addContentView", overlay)
        self.assertIn("EditText", overlay)
        self.assertIn("Typeface.DEFAULT", overlay)
        self.assertIn("onKeyPreIme", overlay)
        self.assertIn("pollResult", overlay)

    def test_build_script_reuses_native_cache_under_a_package_lock(self):
        script = (Path(__file__).parent / "build_runtime.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('PACKAGE_WORKSPACE_KEY="$(printf \'%s\' "${PACKAGE_ID}" | sha256sum | cut -c1-8)"', script)
        self.assertIn('NATIVE_WORKSPACE_KEY="${NATIVE_HASH:0:16}-${PACKAGE_WORKSPACE_KEY}"', script)
        self.assertIn('WORK_DIR="${CACHE_BASE}/n/${NATIVE_WORKSPACE_KEY}"', script)
        self.assertIn('exec 9>"${LOCK_DIR}/${NATIVE_HASH}-${PACKAGE_ID}.lock"', script)
        self.assertIn("ANDROID_NATIVE_CACHE", script)
        self.assertIn(".native-verified", script)
        self.assertIn(".dirty", script)
        self.assertIn("if ! flock -n 9", script)
        self.assertIn("flock 9", script)
        self.assertIn('-newer "${APK_MARKER}"', script)

    def test_release_pipeline_checks_and_signs_before_verification(self):
        script = (Path(__file__).parent / "build_runtime.sh").read_text(
            encoding="utf-8"
        )

        self.assertGreaterEqual(script.count("sign_apk.py"), 2)
        self.assertIn("dev-signed.apk", script)
        self.assertIn(
            'PYTHONPATH="${SOURCE_DIR}${PYTHONPATH:+:${PYTHONPATH}}"',
            script,
        )
        self.assertLess(
            script.rindex("sign_apk.py"),
            script.index("verify_apk.py"),
        )

    def test_verification_failure_does_not_invalidate_native_cache(self):
        script = (Path(__file__).parent / "build_runtime.sh").read_text(
            encoding="utf-8"
        )
        verification_failure = script[
            script.index('if ! "${VERIFY_ARGS[@]}"; then'):
            script.index('touch "${WORK_DIR}/.native-verified"')
        ]

        self.assertNotIn('touch "${WORK_DIR}/.dirty"', verification_failure)

    def test_build_spec_pins_the_verified_p4a_commit(self):
        spec = (Path(__file__).parent / "buildozer.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "p4a.commit = 58d21141f17c889bf8585f5665921d72028f8831",
            spec,
        )

    def test_default_build_config_is_phase4_arm64_debug(self):
        config = load_build_config()
        self.assertEqual("org.lextalionis.ltandroidruntime", config.package_id)
        self.assertEqual("0.4.0", config.version_name)
        self.assertEqual(1026400, config.version_code)
        self.assertEqual("arm64-v8a", config.arch)
        self.assertEqual("debug", config.mode)
        self.assertEqual([], validate_build_config(config))

    def test_x86_64_is_a_supported_explicit_build_abi(self):
        config = load_build_config(arch="x86_64")

        self.assertEqual("x86_64", config.arch)
        self.assertEqual([], validate_build_config(config))

    def test_unknown_build_abi_is_rejected(self):
        config = load_build_config(arch="x86")

        self.assertTrue(any("ABI" in error for error in validate_build_config(config)))

    def test_project_editor_build_config_overrides_release_identity(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "golden.ltproj"
            project.mkdir()
            canonical = project / "android-release.json"
            canonical.write_text('{"mode":"debug"}', encoding="utf-8")
            editor_config = project / "build" / "android.json"
            editor_config.parent.mkdir()
            editor_config.write_text('{"mode":"release"}', encoding="utf-8")

            self.assertEqual(
                editor_config,
                discover_project_build_config(project),
            )

            explicit = project / "manual.json"
            self.assertEqual(
                explicit,
                discover_project_build_config(project, explicit),
            )

    def test_invalid_package_is_rejected_while_release_mode_is_allowed(self):
        config = BuildConfig(
            package_id="Org.Bad",
            app_name="Bad",
            version_name="1",
            version_code=0,
            arch="mips",
            mode="release",
        )
        errors = validate_build_config(config)
        self.assertGreaterEqual(len(errors), 4)
        self.assertFalse(any("mode" in error for error in errors))

    def test_preflight_report_is_rechecked_before_staging(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            project = root / "sample.ltproj"
            project.mkdir()
            (project / "metadata.json").write_text("{}", encoding="utf-8")
            config = load_build_config()
            source_digest, _, _ = snapshot_digest(project)
            report = PreflightReport(
                schema_version=1,
                phase=4,
                passed=True,
                project_dir=project.name,
                project_path=str(project),
                source_digest=source_digest,
                config=asdict(config),
            )
            report_path = root / "preflight.json"
            report_path.write_text(json.dumps(asdict(report)), encoding="utf-8")

            loaded = load_verified_preflight(report_path, project.resolve(), config)
            self.assertEqual(source_digest, loaded.source_digest)

            (project / "changed.txt").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Project changed"):
                load_verified_preflight(report_path, project.resolve(), config)

    def test_case_collision_is_fatal(self):
        errors: list[str] = []
        validate_case_collisions(
            {"resources/icon.png": ["resources/Icon.png", "resources/icon.png"]},
            errors,
        )
        self.assertEqual(1, len(errors))
        self.assertIn("collision", errors[0].casefold())

    def test_preflight_rejects_desktop_custom_import_and_bad_ogg(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "sample.ltproj"
            custom = project / "resources" / "custom_components"
            music = project / "resources" / "music"
            custom.mkdir(parents=True)
            music.mkdir(parents=True)
            (project / "metadata.json").write_text(
                json.dumps(
                    {
                        "serialization_version": 1,
                        "has_fatal_errors": False,
                    }
                ),
                encoding="utf-8",
            )
            (custom / "__init__.py").write_text(
                "from PyQt5 import QtCore\n",
                encoding="utf-8",
            )
            (music / "music.json").write_text(
                json.dumps([["Broken", False, False]]),
                encoding="utf-8",
            )
            (music / "Broken.ogg").write_bytes(b"not-ogg")
            report = run_preflight(project, load_build_config())
            self.assertFalse(report.passed)
            self.assertTrue(
                any("Desktop-only import" in error for error in report.errors)
            )
            self.assertTrue(any("Invalid OGG header" in error for error in report.errors))

    def test_configure_build_materializes_requested_identity(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            config_path = root / "config.json"
            spec_path = root / "buildozer.spec"
            config_path.write_text(
                json.dumps(
                    {
                        "package_id": "com.example.fireemblem",
                        "app_name": "Example Game",
                        "version_name": "1.2.3",
                        "version_code": 123,
                        "arch": "x86_64",
                    }
                ),
                encoding="utf-8",
            )
            configure(config_path, spec_path)
            configured = spec_path.read_text(encoding="utf-8")
            self.assertIn("package.name = fireemblem", configured)
            self.assertIn("package.domain = com.example", configured)
            self.assertIn("version = 1.2.3", configured)
            self.assertIn("android.archs = x86_64", configured)
        self.assertIn("android.numeric_version = 123", configured)

    def test_x86_64_abi_validation_rejects_wrong_elf_machine(self):
        x86_64_header = bytearray(20)
        x86_64_header[:4] = b"\x7fELF"
        x86_64_header[5] = 1
        x86_64_header[18:20] = (62).to_bytes(2, "little")
        arm64_header = bytearray(x86_64_header)
        arm64_header[18:20] = (183).to_bytes(2, "little")

        self.assertEqual(
            [],
            validate_native_abi(
                "x86_64",
                {"x86_64"},
                ["lib/x86_64/libpython3.11.so"],
                lambda _name: bytes(x86_64_header),
            ),
        )
        errors = validate_native_abi(
            "x86_64",
            {"x86_64"},
            ["lib/x86_64/libcrypto.so"],
            lambda _name: bytes(arm64_header),
        )
        self.assertTrue(any("ELF machine" in error for error in errors))

    def test_abi_validation_rejects_unrequested_native_directory(self):
        header = bytearray(20)
        header[:4] = b"\x7fELF"
        header[5] = 1
        header[18:20] = (62).to_bytes(2, "little")

        errors = validate_native_abi(
            "x86_64",
            {"x86_64", "arm64-v8a"},
            [
                "lib/x86_64/libpython3.11.so",
                "lib/arm64-v8a/libpython3.11.so",
            ],
            lambda _name: bytes(header),
        )

        self.assertTrue(any("advertises native ABIs" in error for error in errors))
        self.assertTrue(any("ABI directories" in error for error in errors))

    def test_abi_validation_accepts_only_the_known_gzip_pybundle_payload(self):
        header = bytearray(20)
        header[:4] = b"\x7fELF"
        header[5] = 1
        header[18:20] = (62).to_bytes(2, "little")
        payloads = {
            "lib/x86_64/libpython3.11.so": bytes(header),
            "lib/x86_64/libpybundle.so": b"\x1f\x8b" + bytes(18),
        }

        self.assertEqual(
            [],
            validate_native_abi(
                "x86_64",
                {"x86_64"},
                list(payloads),
                payloads.__getitem__,
            ),
        )
        payloads["lib/x86_64/libpybundle.so"] = b"not-gzip"
        errors = validate_native_abi(
            "x86_64",
            {"x86_64"},
            list(payloads),
            payloads.__getitem__,
        )
        self.assertTrue(any("pybundle" in error for error in errors))

    def test_long_unlisted_portrait_import_is_excluded_from_android_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            staging = Path(temporary_dir) / "staging"
            project = staging / "Long Project Name.ltproj"
            portraits = project / "resources" / "portraits"
            old_portraits = project / "resources" / "old_portraits"
            portraits.mkdir(parents=True)
            old_portraits.mkdir(parents=True)
            (portraits / "portraits.json").write_text(
                json.dumps([{"nid": "Martin"}]),
                encoding="utf-8",
            )
            (portraits / "Martin.png").write_bytes(b"listed")
            long_name = "Portrait Editor " + ("Golden Knight " * 8) + ".png"
            imported = portraits / long_name
            old_imported = old_portraits / long_name
            imported.write_bytes(b"unused")
            old_imported.write_bytes(b"backup")

            excluded = prune_unpackageable_project_files(staging, project)
            validate_ustar_paths(staging)

            self.assertFalse(imported.exists())
            self.assertFalse(old_imported.exists())
            self.assertTrue((portraits / "Martin.png").is_file())
            self.assertEqual(2, len(excluded))

    def test_long_catalogued_portrait_filename_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            staging = Path(temporary_dir) / "staging"
            project = staging / "sample.ltproj"
            portraits = project / "resources" / "portraits"
            portraits.mkdir(parents=True)
            long_nid = "P" * 101
            (portraits / "portraits.json").write_text(
                json.dumps([{"nid": long_nid}]),
                encoding="utf-8",
            )
            (portraits / f"{long_nid}.png").write_bytes(b"listed")

            with self.assertRaisesRegex(RuntimeError, "USTAR 100-byte"):
                prune_unpackageable_project_files(staging, project)

    def test_project_json_is_compacted_without_changing_values(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "sample.ltproj"
            project.mkdir()
            source = {
                "title": "Hiệp sĩ Vàng",
                "entries": [{"nid": "A", "value": 1}, {"nid": "B", "value": 2}],
            }
            json_path = project / "data.json"
            json_path.write_text(
                json.dumps(source, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
            original_size = json_path.stat().st_size

            metrics = minify_project_json(project)

            self.assertEqual(source, json.loads(json_path.read_text(encoding="utf-8")))
            self.assertLess(json_path.stat().st_size, original_size)
            self.assertEqual(1, metrics["json_files_compacted"])
            self.assertEqual(
                original_size - json_path.stat().st_size,
                metrics["json_bytes_saved"],
            )

    def test_project_json_compaction_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            project = Path(temporary_dir) / "sample.ltproj"
            project.mkdir()
            (project / "duplicate.json").write_text(
                '{"nid":"first","nid":"second"}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "Duplicate JSON key"):
                minify_project_json(project)

    def test_publish_creates_immutable_batch_and_atomic_latest_alias(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            apk = root / "input.apk"
            apk.write_bytes(b"phase-4-apk")
            preflight = root / "preflight.json"
            verification = root / "verification.json"
            config = root / "config.json"
            build_log = root / "build.log"
            output = root / "artifacts"
            preflight.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "project_dir": "sample.ltproj",
                        "source_digest": "abc",
                    }
                ),
                encoding="utf-8",
            )
            verification.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
                        "source_digest": "abc",
                        "package_id": "com.example.sample",
                        "version_name": "1.0.0",
                        "version_code": 100,
                        "abis": ["arm64-v8a"],
                    }
                ),
                encoding="utf-8",
            )
            config.write_text(
                json.dumps(
                    {
                        "package_id": "com.example.sample",
                        "app_name": "Sample",
                        "version_name": "1.0.0",
                        "version_code": 100,
                        "icon": None,
                        "arch": "arm64-v8a",
                        "mode": "debug",
                    }
                ),
                encoding="utf-8",
            )
            build_log.write_text("successful build\n", encoding="utf-8")
            result = publish(
                apk,
                preflight,
                verification,
                build_log,
                config,
                output,
            )
            artifact_dir = Path(result["artifact_dir"])
            self.assertTrue(artifact_dir.is_dir())
            self.assertTrue((artifact_dir / "build-manifest.json").is_file())
            self.assertEqual(
                apk.read_bytes(),
                (output / "lt-android-runtime-arm64-debug.apk").read_bytes(),
            )

            verification.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "sha256": "stale",
                        "source_digest": "abc",
                        "package_id": "com.example.sample",
                        "version_name": "1.0.0",
                        "version_code": 100,
                        "abis": ["arm64-v8a"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                publish(
                    apk,
                    preflight,
                    verification,
                    build_log,
                    config,
                    output,
                )

    def test_publish_names_development_signed_release_without_unsigned(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            apk = root / "signed.apk"
            preflight = root / "preflight.json"
            verification = root / "verification.json"
            config = root / "config.json"
            build_log = root / "build.log"
            output = root / "artifacts"
            apk.write_bytes(b"signed release")
            preflight.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "project_dir": "sample.ltproj",
                        "source_digest": "abc",
                    }
                ),
                encoding="utf-8",
            )
            verification.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
                        "source_digest": "abc",
                        "package_id": "com.example.sample",
                        "version_name": "1.0.0",
                        "version_code": 100,
                        "signing_profile": "development",
                        "abis": ["arm64-v8a"],
                    }
                ),
                encoding="utf-8",
            )
            config.write_text(
                json.dumps(
                    {
                        "package_id": "com.example.sample",
                        "app_name": "Sample",
                        "version_name": "1.0.0",
                        "version_code": 100,
                        "icon": None,
                        "arch": "arm64-v8a",
                        "mode": "release",
                    }
                ),
                encoding="utf-8",
            )
            build_log.write_text("successful build\n", encoding="utf-8")

            result = publish(
                apk, preflight, verification, build_log, config, output
            )

            self.assertTrue(result["apk"].endswith("release-dev-signed.apk"))
            self.assertNotIn("unsigned", result["apk"])
            self.assertTrue(
                (output / "lt-android-runtime-arm64-release-dev-signed.apk").is_file()
            )

    def test_publish_names_x86_64_artifacts_from_active_config(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            apk = root / "input.apk"
            apk.write_bytes(b"x86_64 apk")
            preflight = root / "preflight.json"
            verification = root / "verification.json"
            config = root / "config.json"
            build_log = root / "build.log"
            output = root / "artifacts"
            preflight.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "project_dir": "sample.ltproj",
                        "source_digest": "abc",
                    }
                ),
                encoding="utf-8",
            )
            verification.write_text(
                json.dumps(
                    {
                        "passed": True,
                        "sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
                        "source_digest": "abc",
                        "package_id": "com.example.sample",
                        "version_name": "1.0.0",
                        "version_code": 100,
                        "abis": ["x86_64"],
                    }
                ),
                encoding="utf-8",
            )
            config.write_text(
                json.dumps(
                    {
                        "package_id": "com.example.sample",
                        "app_name": "Sample",
                        "version_name": "1.0.0",
                        "version_code": 100,
                        "icon": None,
                        "arch": "x86_64",
                        "mode": "debug",
                    }
                ),
                encoding="utf-8",
            )
            build_log.write_text("successful build\n", encoding="utf-8")

            result = publish(
                apk,
                preflight,
                verification,
                build_log,
                config,
                output,
            )

            self.assertIn("x86_64", Path(result["apk"]).name)
            self.assertEqual(
                apk.read_bytes(),
                (output / "lt-android-runtime-x86_64-debug.apk").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
