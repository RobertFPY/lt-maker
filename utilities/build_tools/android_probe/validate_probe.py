from __future__ import annotations

import compileall
import configparser
import json
from pathlib import Path

from prepare_probe import PROBE_ROOT, prepare, sha256


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    staging = prepare()
    recipe_dir = PROBE_ROOT / "p4a-recipes" / "pygame-ce"
    require(compileall.compile_dir(staging, quiet=1), "Probe Python sources do not compile")
    require(
        compileall.compile_file(recipe_dir / "__init__.py", quiet=1),
        "pygame-ce recipe does not compile",
    )
    recipe_source = (recipe_dir / "__init__.py").read_text(encoding="utf-8")
    patch_name = "setup-setuptools-distutils-spawn.patch"
    require(patch_name in recipe_source, "pygame-ce setuptools compatibility patch missing")
    require((recipe_dir / patch_name).is_file(), "pygame-ce compatibility patch file missing")

    config = configparser.ConfigParser(interpolation=None)
    config.read(PROBE_ROOT / "buildozer.spec", encoding="utf-8")
    app = config["app"]
    require(app["android.api"] == "36", "android.api must remain 36")
    require(app["android.archs"] == "arm64-v8a", "Probe must be arm64-only")
    require(app["p4a.bootstrap"] == "sdl2", "Probe must use SDL2 bootstrap")
    require("pygame-ce==2.3.2" in app["requirements"], "pygame-ce pin missing")
    require("python3==3.11.9" in app["requirements"], "Python pin missing")
    require("hostpython3==3.11.9" in app["requirements"], "Host Python pin missing")

    manifest_path = staging / "build_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {"main.py", "dynamic_probe.py", "probe_data.json", "probe.png", "probe.ogg"}
    require(expected <= set(manifest["files"]), "Staging manifest is incomplete")
    for relative_path, metadata in manifest["files"].items():
        path = staging / relative_path
        require(path.is_file(), f"Manifest path is missing: {relative_path}")
        require(sha256(path) == metadata["sha256"], f"Hash mismatch: {relative_path}")

    print("ANDROID_PROBE_STATIC_OK")


if __name__ == "__main__":
    main()
