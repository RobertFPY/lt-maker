from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


TOOLCHAIN_MANIFEST_PATH = Path(__file__).with_name("toolchain_manifest.json")
DEVELOPMENT_KEYSTORE_NAME = Path(".android") / "debug.keystore"
DEVELOPMENT_KEY_ALIAS = "androiddebugkey"
DEVELOPMENT_STORE_PASSWORD_ENV = "LT_ANDROID_DEVELOPMENT_STORE_PASSWORD"
DEVELOPMENT_KEY_PASSWORD_ENV = "LT_ANDROID_DEVELOPMENT_KEY_PASSWORD"
DEVELOPMENT_PASSWORD = "android"


class DevelopmentSigningError(RuntimeError):
    """The trusted development signing key could not sign an APK."""


def _as_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def development_signer_certificate() -> str:
    payload = json.loads(TOOLCHAIN_MANIFEST_PATH.read_text(encoding="utf-8"))
    signer = payload.get("development_signer")
    if not isinstance(signer, dict):
        raise DevelopmentSigningError(
            "toolchain_manifest.json does not define a development signer"
        )
    certificate = signer.get("certificate_sha256")
    if not isinstance(certificate, str) or len(certificate) != 64:
        raise DevelopmentSigningError(
            "toolchain_manifest.json has an invalid development signer certificate"
        )
    return certificate.casefold()


def development_keystore(home: Path | None = None) -> Path:
    return (home or Path.home()) / DEVELOPMENT_KEYSTORE_NAME


def check_development_key(
    keystore: Path,
    keytool: Path,
    expected_certificate_sha256: str,
) -> Path:
    """Ensure the machine key is the established LT development signer."""
    if not keystore.is_file():
        raise DevelopmentSigningError(
            f"Development keystore was not found: {keystore}"
        )
    completed = subprocess.run(
        [
            str(keytool),
            "-exportcert",
            "-alias",
            DEVELOPMENT_KEY_ALIAS,
            "-keystore",
            str(keystore),
            "-storepass",
            DEVELOPMENT_PASSWORD,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        detail = _as_text(completed.stderr).strip()
        raise DevelopmentSigningError(
            "Could not read the development signing key"
            + (f": {detail}" if detail else "")
        )
    certificate = hashlib.sha256(completed.stdout).hexdigest()
    if certificate != expected_certificate_sha256.casefold():
        raise DevelopmentSigningError(
            "Development signing certificate does not match the existing "
            "LT Android development signer"
        )
    return keystore


def sign_development_apk(
    unsigned_apk: Path,
    signed_apk: Path,
    *,
    keystore: Path | None = None,
    keytool: Path = Path("keytool"),
    apksigner: Path = Path("apksigner"),
    expected_certificate_sha256: str | None = None,
) -> Path:
    """Sign an APK to a separate atomically-published development output."""
    unsigned_apk = unsigned_apk.resolve()
    signed_apk = signed_apk.resolve()
    if not unsigned_apk.is_file():
        raise DevelopmentSigningError(f"Unsigned APK was not found: {unsigned_apk}")
    if unsigned_apk == signed_apk:
        raise DevelopmentSigningError("Development signing output must differ from input")

    expected_certificate_sha256 = (
        expected_certificate_sha256 or development_signer_certificate()
    )
    keystore = check_development_key(
        keystore or development_keystore(),
        keytool,
        expected_certificate_sha256,
    )
    signed_apk.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{signed_apk.name}.",
        suffix=".tmp",
        dir=signed_apk.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    environment = dict(os.environ)
    environment[DEVELOPMENT_STORE_PASSWORD_ENV] = DEVELOPMENT_PASSWORD
    environment[DEVELOPMENT_KEY_PASSWORD_ENV] = DEVELOPMENT_PASSWORD
    try:
        completed = subprocess.run(
            [
                str(apksigner),
                "sign",
                "--ks",
                str(keystore),
                "--ks-key-alias",
                DEVELOPMENT_KEY_ALIAS,
                "--ks-pass",
                f"env:{DEVELOPMENT_STORE_PASSWORD_ENV}",
                "--key-pass",
                f"env:{DEVELOPMENT_KEY_PASSWORD_ENV}",
                "--out",
                str(temporary),
                str(unsigned_apk),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        if completed.returncode:
            detail = _as_text(completed.stderr).strip()
            raise DevelopmentSigningError(
                "Development signing failed" + (f": {detail}" if detail else "")
            )
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise DevelopmentSigningError("Development signing did not create an APK")
        os.replace(temporary, signed_apk)
    finally:
        temporary.unlink(missing_ok=True)
    return signed_apk


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign LT Android APKs for development")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--keystore", type=Path, default=development_keystore())
    parser.add_argument("--keytool", type=Path, default=Path("keytool"))
    parser.add_argument("--apksigner", type=Path, default=Path("apksigner"))
    args = parser.parse_args()
    expected_certificate = development_signer_certificate()
    check_development_key(args.keystore, args.keytool, expected_certificate)
    if args.check:
        if args.input or args.output:
            parser.error("--check cannot be combined with --input or --output")
        print(f"ANDROID_DEVELOPMENT_SIGNER_OK keystore={args.keystore}")
        return 0
    if args.input is None or args.output is None:
        parser.error("--input and --output are required when signing an APK")
    signed = sign_development_apk(
        args.input,
        args.output,
        keystore=args.keystore,
        keytool=args.keytool,
        apksigner=args.apksigner,
        expected_certificate_sha256=expected_certificate,
    )
    print(f"ANDROID_DEVELOPMENT_APK_SIGNED apk={signed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
