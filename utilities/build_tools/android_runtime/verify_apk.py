from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
from typing import Callable
import zipfile

from preflight import atomic_write_json, load_build_config, load_toolchain_manifest


PACKAGE_RE = re.compile(
    r"package: name='(?P<package>[^']+)' "
    r"versionCode='(?P<code>[^']+)' versionName='(?P<name>[^']+)'"
)
SDK_RE = re.compile(r"sdkVersion:'(?P<value>[^']+)'")
TARGET_SDK_RE = re.compile(r"targetSdkVersion:'(?P<value>[^']+)'")
NATIVE_RE = re.compile(r"native-code: (?P<values>.+)")
ELF_MACHINE_BY_ABI = {
    "x86_64": 62,
    "arm64-v8a": 183,
}
LAUNCHABLE_ACTIVITY_RE = re.compile(
    r"launchable-activity: name='(?P<activity>[^']+)'"
)
CERTIFICATE_RE = re.compile(
    r"(?:Signer #1|V\d+(?:\.\d+)? Signer:?)\s+certificate SHA-256 digest:\s*"
    r"(?P<digest>[0-9a-fA-F:]+)"
)
def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}"
        )
    return completed.stdout


def launchable_activity(badging: str) -> str | None:
    """Return the Activity Android will actually launch from aapt metadata."""
    match = LAUNCHABLE_ACTIVITY_RE.search(badging)
    return match.group("activity") if match else None


def native_abis_from_badging(badging: str) -> set[str]:
    match = NATIVE_RE.search(badging)
    return set(re.findall(r"'([^']+)'", match.group("values"))) if match else set()


def elf_machine(header: bytes) -> int | None:
    if len(header) < 20 or header[:4] != b"\x7fELF":
        return None
    if header[5] == 1:
        byteorder = "little"
    elif header[5] == 2:
        byteorder = "big"
    else:
        return None
    return int.from_bytes(header[18:20], byteorder)


def validate_native_abi(
    expected_arch: str,
    advertised_abis: set[str],
    apk_names: list[str],
    read_header: Callable[[str], bytes],
) -> list[str]:
    errors: list[str] = []
    expected_abis = {expected_arch}
    if advertised_abis != expected_abis:
        errors.append(
            "APK advertises native ABIs "
            f"{sorted(advertised_abis)}; expected {sorted(expected_abis)}"
        )
    abi_dirs = {
        name.split("/", 2)[1]
        for name in apk_names
        if name.startswith("lib/") and len(name.split("/", 2)) >= 3
    }
    if abi_dirs != expected_abis:
        errors.append(
            f"APK contains ABI directories {sorted(abi_dirs)}; "
            f"expected {sorted(expected_abis)}"
        )
    expected_machine = ELF_MACHINE_BY_ABI.get(expected_arch)
    if expected_machine is None:
        errors.append(f"No ELF machine policy is defined for ABI {expected_arch!r}")
        return errors
    native_libraries = [
        name
        for name in apk_names
        if name.startswith(f"lib/{expected_arch}/") and name.endswith(".so")
    ]
    if not native_libraries:
        errors.append(f"APK contains no native libraries for ABI {expected_arch}")
    for name in native_libraries:
        header = read_header(name)
        if name.endswith("/libpybundle.so"):
            if not header.startswith(b"\x1f\x8b"):
                errors.append(f"Packaged pybundle is not gzip data: {name}")
            continue
        observed_machine = elf_machine(header)
        if observed_machine != expected_machine:
            errors.append(
                f"Native library {name} has ELF machine {observed_machine}; "
                f"expected {expected_machine} for {expected_arch}"
            )
    return errors


def _read_private_payload(apk_path: Path) -> tuple[dict, dict, list[str]]:
    with zipfile.ZipFile(apk_path) as apk:
        private_tar = apk.read("assets/private.tar")
        apk_names = apk.namelist()
    with tarfile.open(fileobj=io.BytesIO(private_tar), mode="r:*") as archive:
        names = archive.getnames()
        manifest_member = next(
            (name for name in names if name.endswith("runtime_manifest.json")),
            None,
        )
        preflight_member = next(
            (name for name in names if name.endswith("android_preflight.json")),
            None,
        )
        if manifest_member is None or preflight_member is None:
            raise RuntimeError(
                "APK private payload is missing runtime_manifest.json or "
                "android_preflight.json"
            )
        manifest_stream = archive.extractfile(manifest_member)
        preflight_stream = archive.extractfile(preflight_member)
        if manifest_stream is None or preflight_stream is None:
            raise RuntimeError("Could not read Android manifests from private payload")
        manifest = json.load(manifest_stream)
        preflight = json.load(preflight_stream)
    return manifest, preflight, apk_names


def verify(
    apk_path: Path,
    config_path: Path,
    aapt: Path,
    apksigner: Path,
    report_path: Path | None = None,
) -> dict:
    apk_path = apk_path.resolve()
    build_config = load_build_config(config_path)
    toolchain = load_toolchain_manifest()
    development_signer = toolchain.get("development_signer")
    if not isinstance(development_signer, dict):
        raise RuntimeError("Toolchain does not define a development signer")
    expected_certificate = development_signer.get("certificate_sha256")
    signing_profile = development_signer.get("profile")
    if not isinstance(expected_certificate, str) or not isinstance(signing_profile, str):
        raise RuntimeError("Toolchain has an invalid development signer")
    errors: list[str] = []

    badging = _run([str(aapt), "dump", "badging", str(apk_path)])
    manifest_tree = _run(
        [str(aapt), "dump", "xmltree", str(apk_path), "AndroidManifest.xml"]
    )
    signature = _run([str(apksigner), "verify", "--verbose", str(apk_path)])
    certificate_output = _run(
        [str(apksigner), "verify", "--print-certs", str(apk_path)]
    )
    certificate_match = CERTIFICATE_RE.search(certificate_output)
    certificate_digest = (
        certificate_match.group("digest").replace(":", "").lower()
        if certificate_match
        else None
    )
    package_match = PACKAGE_RE.search(badging)
    launcher_activity = launchable_activity(badging)
    sdk_match = SDK_RE.search(badging)
    target_match = TARGET_SDK_RE.search(badging)
    advertised_abis = native_abis_from_badging(badging)
    if not package_match:
        errors.append("aapt did not return package/version metadata")
    else:
        if package_match.group("package") != build_config.package_id:
            errors.append(
                f"Package mismatch: {package_match.group('package')} != "
                f"{build_config.package_id}"
            )
        if package_match.group("name") != build_config.version_name:
            errors.append(
                f"Version name mismatch: {package_match.group('name')} != "
                f"{build_config.version_name}"
            )
        if int(package_match.group("code")) != build_config.version_code:
            errors.append(
                f"Version code mismatch: {package_match.group('code')} != "
                f"{build_config.version_code}"
            )
    if not sdk_match or int(sdk_match.group("value")) != toolchain["android_minapi"]:
        errors.append("APK minimum Android API does not match toolchain manifest")
    if not target_match or int(target_match.group("value")) != toolchain["android_api"]:
        errors.append("APK target Android API does not match toolchain manifest")
    expected_migration_activity = "org.lextalionis.android.LtPythonActivity"
    if launcher_activity != expected_migration_activity:
        errors.append(
            "APK launcher Activity does not run persistent-data migration: "
            f"{launcher_activity!r} != {expected_migration_activity!r}"
        )
    if "Verifies" not in signature or (
        "Verified using v2 scheme (APK Signature Scheme v2): true" not in signature
    ):
        errors.append("APK v2 signature verification failed")
    if certificate_digest is None:
        errors.append("APK signer certificate digest could not be read")
    elif certificate_digest != expected_certificate.casefold():
        errors.append(
            "APK signer certificate mismatch: "
            f"{certificate_digest} != {expected_certificate.casefold()}"
        )
    expected_authority = f"{build_config.package_id}.documents"
    if (
        "org.lextalionis.android.LtDocumentsProvider" not in manifest_tree
        or "android.content.action.DOCUMENTS_PROVIDER" not in manifest_tree
        or "android.permission.MANAGE_DOCUMENTS" not in manifest_tree
        or expected_authority not in manifest_tree
    ):
        errors.append("APK manifest is missing the Lex Talionis DocumentsProvider")

    runtime_manifest, preflight, apk_names = _read_private_payload(apk_path)
    if runtime_manifest.get("phase") != 4:
        errors.append("Packaged runtime manifest is not marked as phase 4")
    if runtime_manifest.get("build") != asdict(build_config):
        errors.append("Packaged build config does not match requested build config")
    if not preflight.get("passed"):
        errors.append("Packaged Android preflight report did not pass")
    if runtime_manifest.get("source_digest") != preflight.get("source_digest"):
        errors.append(
            "Packaged runtime manifest and preflight report use different source digests"
        )
    if runtime_manifest.get("project_dir") != preflight.get("project_dir"):
        errors.append(
            "Packaged runtime manifest and preflight report use different projects"
        )
    with zipfile.ZipFile(apk_path) as apk:
        errors.extend(
            validate_native_abi(
                build_config.arch,
                advertised_abis,
                apk_names,
                lambda name: apk.read(name)[:20],
            )
        )
    abi_dirs = {
        name.split("/", 2)[1]
        for name in apk_names
        if name.startswith("lib/") and len(name.split("/", 2)) >= 3
    }
    dex_names = [
        name for name in apk_names if re.fullmatch(r"classes\d*\.dex", name)
    ]
    with zipfile.ZipFile(apk_path) as apk:
        provider_class_found = any(
            b"LtDocumentsProvider" in apk.read(name) for name in dex_names
        )
        migration_activity_found = any(
            b"LtPythonActivity" in apk.read(name) for name in dex_names
        )
    if not provider_class_found:
        errors.append("APK dex payload is missing LtDocumentsProvider")
    if (
        expected_migration_activity not in manifest_tree
        or not migration_activity_found
    ):
        errors.append("APK is missing the persistent-data migration Activity")

    report = {
        "schema_version": 1,
        "phase": 4,
        "passed": not errors,
        "apk": str(apk_path),
        "apk_bytes": apk_path.stat().st_size,
        "sha256": sha256(apk_path),
        "package_id": package_match.group("package") if package_match else None,
        "version_name": package_match.group("name") if package_match else None,
        "version_code": (
            int(package_match.group("code")) if package_match else None
        ),
        "min_api": int(sdk_match.group("value")) if sdk_match else None,
        "target_api": int(target_match.group("value")) if target_match else None,
        "abis": sorted(abi_dirs),
        "signature_v2": (
            "Verified using v2 scheme (APK Signature Scheme v2): true"
            in signature
        ),
        "signing_profile": signing_profile,
        "signer_certificate_sha256": certificate_digest,
        "launchable_activity": launcher_activity,
        "launcher_activity": launcher_activity == expected_migration_activity,
        "documents_provider": (
            expected_authority in manifest_tree and provider_class_found
        ),
        "migration_activity": (
            expected_migration_activity in manifest_tree
            and migration_activity_found
        ),
        "project_dir": runtime_manifest.get("project_dir"),
        "source_digest": runtime_manifest.get("source_digest"),
        "preflight_source_digest": preflight.get("source_digest"),
        "errors": errors,
    }
    if report_path is not None:
        atomic_write_json(report_path, report)
    if errors:
        raise RuntimeError("APK verification failed:\n- " + "\n- ".join(errors))
    return report


def _default_build_tool(name: str) -> Path:
    sdk_root = Path(
        os.environ.get(
            "ANDROIDSDK",
            str(Path.home() / ".buildozer" / "android" / "platform" / "android-sdk"),
        )
    )
    build_tools = sdk_root / "build-tools"
    versions = sorted(
        (path for path in build_tools.iterdir() if path.is_dir()),
        key=lambda path: tuple(
            int(part) if part.isdigit() else 0 for part in path.name.split(".")
        ),
    )
    if not versions:
        raise FileNotFoundError(f"No Android build-tools found under {build_tools}")
    return versions[-1] / name


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a built LT Android APK")
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--aapt", type=Path)
    parser.add_argument("--apksigner", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = verify(
        args.apk,
        args.config,
        args.aapt or _default_build_tool("aapt"),
        args.apksigner or _default_build_tool("apksigner"),
        args.report,
    )
    print(
        f"ANDROID_APK_VERIFIED package={report['package_id']} "
        f"version={report['version_name']} code={report['version_code']} "
        f"sha256={report['sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
