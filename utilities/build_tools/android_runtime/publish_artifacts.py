from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from preflight import atomic_write_json


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized or "lt-project"


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def publish(
    apk: Path,
    preflight: Path,
    verification: Path,
    build_log: Path,
    config: Path,
    output_dir: Path,
) -> dict:
    verification_payload = json.loads(verification.read_text(encoding="utf-8"))
    preflight_payload = json.loads(preflight.read_text(encoding="utf-8"))
    config_payload = json.loads(config.read_text(encoding="utf-8"))
    if not verification_payload.get("passed") or not preflight_payload.get("passed"):
        raise RuntimeError("Refusing to publish an unverified Android build")

    output_dir.mkdir(parents=True, exist_ok=True)
    apk_hash = sha256(apk)
    if verification_payload.get("sha256") != apk_hash:
        raise RuntimeError("Refusing to publish an APK whose verification SHA-256 is stale")
    if verification_payload.get("source_digest") != preflight_payload.get("source_digest"):
        raise RuntimeError("Refusing to publish an APK with a stale source digest")
    expected_identity = {
        "package_id": config_payload.get("package_id"),
        "version_name": config_payload.get("version_name"),
        "version_code": config_payload.get("version_code"),
    }
    observed_identity = {
        key: verification_payload.get(key)
        for key in expected_identity
    }
    if observed_identity != expected_identity:
        raise RuntimeError("Refusing to publish an APK with mismatched build identity")
    signing_profile = verification_payload.get("signing_profile")
    if config_payload.get("mode") == "release":
        if signing_profile != "development":
            raise RuntimeError("Refusing to publish a Release APK without development signing")
        artifact_mode = "release-dev-signed"
    else:
        artifact_mode = config_payload["mode"]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    project_slug = slug(preflight_payload["project_dir"].removesuffix(".ltproj"))
    build_id = (
        f"{project_slug}-android-{config_payload['version_name']}-"
        f"{timestamp}-{apk_hash[:8]}"
    )
    final_dir = output_dir / build_id
    if final_dir.exists():
        raise FileExistsError(f"Immutable Android artifact already exists: {final_dir}")
    temporary_dir = Path(
        tempfile.mkdtemp(prefix=f".{build_id}.", dir=output_dir)
    )
    try:
        apk_name = (
            f"{project_slug}-{config_payload['version_name']}-"
            f"arm64-{artifact_mode}.apk"
        )
        published_apk = temporary_dir / apk_name
        shutil.copy2(apk, published_apk)
        if sha256(published_apk) != apk_hash:
            raise RuntimeError("Published immutable APK hash does not match source APK")
        shutil.copy2(preflight, temporary_dir / "preflight.json")
        shutil.copy2(verification, temporary_dir / "apk-verification.json")
        shutil.copy2(build_log, temporary_dir / "build.log")
        shutil.copy2(config, temporary_dir / "android-build-config.json")
        (temporary_dir / f"{apk_name}.sha256").write_text(
            f"{apk_hash}  {apk_name}\n",
            encoding="ascii",
        )
        build_manifest = {
            "schema_version": 1,
            "phase": 4,
            "build_id": build_id,
            "created_utc": timestamp,
            "project_dir": preflight_payload["project_dir"],
            "source_digest": preflight_payload["source_digest"],
            "package_id": config_payload["package_id"],
            "version_name": config_payload["version_name"],
            "version_code": config_payload["version_code"],
            "abi": config_payload["arch"],
            "mode": config_payload["mode"],
            "signing_profile": signing_profile,
            "apk": apk_name,
            "apk_bytes": published_apk.stat().st_size,
            "sha256": apk_hash,
        }
        atomic_write_json(temporary_dir / "build-manifest.json", build_manifest)
        temporary_dir.replace(final_dir)
    except Exception:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        raise

    final_apk = final_dir / apk_name
    alias_stem = f"lt-android-runtime-arm64-{artifact_mode}.apk"
    latest_apk = output_dir / alias_stem
    latest_sha = output_dir / f"{alias_stem}.sha256"
    atomic_copy(final_apk, latest_apk)
    if sha256(latest_apk) != apk_hash:
        raise RuntimeError("Latest APK alias hash does not match immutable APK")
    descriptor, sha_tmp_name = tempfile.mkstemp(
        prefix=f".{latest_sha.name}.",
        suffix=".tmp",
        dir=output_dir,
    )
    os.close(descriptor)
    sha_tmp = Path(sha_tmp_name)
    try:
        sha_tmp.write_text(
            f"{apk_hash}  {latest_apk.name}\n",
            encoding="ascii",
        )
        sha_tmp.replace(latest_sha)
    finally:
        sha_tmp.unlink(missing_ok=True)

    return {
        "artifact_dir": str(final_dir),
        "apk": str(final_apk),
        "latest_alias": str(latest_apk),
        "sha256": apk_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Atomically publish LT Android artifacts")
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--verification", required=True, type=Path)
    parser.add_argument("--build-log", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = publish(
        args.apk,
        args.preflight,
        args.verification,
        args.build_log,
        args.config,
        args.output,
    )
    print(f"ARTIFACT_DIR: {result['artifact_dir']}")
    print(f"APK: {result['apk']}")
    print(f"Latest alias: {result['latest_alias']}")
    print(f"SHA256: {result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
