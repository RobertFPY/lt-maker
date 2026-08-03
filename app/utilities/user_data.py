"""Paths for data that belongs to a player's installation."""

import os
from pathlib import Path


USER_DATA_ENV = "LT_USER_DATA_DIR"


def user_data_dir() -> Path:
    """Return the persistent user-data root, or the desktop working root."""
    configured = os.environ.get(USER_DATA_ENV)
    if configured:
        return Path(configured)
    return Path(".")


def save_dir() -> Path:
    """Return the directory containing saves and player settings."""
    if os.environ.get(USER_DATA_ENV):
        return user_data_dir() / "saves"
    return Path("saves")


def save_path(*parts: str | os.PathLike[str]) -> Path:
    """Return a path below the player save directory, never outside it."""
    root = save_dir()
    path = root.joinpath(*parts)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Save path escapes the player save directory: {path}") from exc
    return path


def ensure_save_dir() -> Path:
    """Create and return the player save directory."""
    path = save_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
