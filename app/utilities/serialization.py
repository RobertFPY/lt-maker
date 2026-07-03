

import json
import os
import shutil
import stat
import sys
from pathlib import Path

def _clear_readonly_and_retry(func, path, _exc):
    """rmtree error handler: clear the read-only bit and retry.

    The most common cause of WinError 5 (access denied) when deleting a
    save directory on Windows is a read-only file. Make it writable and
    retry the failing operation once; if it still fails, let it raise.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)

def rmtree_robust(path):
    """shutil.rmtree that recovers from read-only files across Python versions."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear_readonly_and_retry)
    else:
        # onerror gets (func, path, exc_info); adapt to our handler
        shutil.rmtree(path, onerror=lambda f, p, ei: _clear_readonly_and_retry(f, p, ei[1]))

def load_json(path: Path):
    if not path.exists():
       raise Exception("Path %s does not exist" % str(path))
    with path.open() as source:
        try:
            loaded = json.load(source)
        except Exception as e:
            raise Exception("Could not read %s" % str(path)) from e
        return loaded

def save_json(path: Path, value: str):
    temp_save_loc = path.parent / (path.name + ".tmp")
    with open(temp_save_loc, 'w') as serialize_file:
        json.dump(value, serialize_file, indent=4)
    os.replace(temp_save_loc, path)
