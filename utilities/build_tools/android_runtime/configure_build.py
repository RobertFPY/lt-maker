from __future__ import annotations

import argparse
import configparser
import json
from pathlib import Path
import shutil

from preflight import load_build_config, load_toolchain_manifest, validate_build_config


RUNTIME_ROOT = Path(__file__).resolve().parent


def configure(
    config_path: Path,
    spec_path: Path | None = None,
) -> Path:
    build_config = load_build_config(config_path)
    errors = validate_build_config(build_config)
    if errors:
        raise RuntimeError("Invalid Android build config:\n- " + "\n- ".join(errors))

    toolchain = load_toolchain_manifest()
    spec_path = spec_path or RUNTIME_ROOT / "buildozer.spec"
    if not spec_path.is_file():
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RUNTIME_ROOT / "buildozer.spec", spec_path)
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(spec_path, encoding="utf-8")
    app = parser["app"]
    app["title"] = build_config.app_name
    app["package.name"] = build_config.package_name
    app["package.domain"] = build_config.package_domain
    app["version"] = build_config.version_name
    app["android.numeric_version"] = str(build_config.version_code)
    app["android.archs"] = build_config.arch
    app["android.api"] = str(toolchain["android_api"])
    app["android.minapi"] = str(toolchain["android_minapi"])
    app["android.ndk"] = str(toolchain["android_ndk"])
    with spec_path.open("w", encoding="utf-8", newline="\n") as output:
        parser.write(output, space_around_delimiters=True)
    return spec_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize an Android buildozer spec")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--spec", type=Path)
    args = parser.parse_args()
    configured = configure(args.config, args.spec)
    payload = json.loads(args.config.read_text(encoding="utf-8"))
    print(
        f"Configured {configured} for {payload['package_id']} "
        f"{payload['version_name']} ({payload['version_code']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
