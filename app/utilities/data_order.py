import json
from pathlib import Path
from typing import List

def rchop(s: str, suffix: str):
    if suffix and s.endswith(suffix):
        return s[:-len(suffix)]
    return s

def parse_order_keys_file(fname: Path) -> List[str]:
    with open(fname) as load_file:
        okeys = json.load(load_file)
    # TODO(mag): this is migration code; remove it on 1/1/2024
    if isinstance(okeys, dict):
        ordering = okeys.keys()
        ordering = [rchop(f, '.json') for f in ordering]
        ordering = sorted(ordering, key=lambda k: okeys.get(k, 99999))
        return ordering
    # correct code
    elif isinstance(okeys, list):
        okeys = [rchop(f, '.json') for f in okeys]
        return okeys