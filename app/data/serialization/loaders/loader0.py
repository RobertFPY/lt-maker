import logging
import os
from pathlib import Path
from typing import List
from app.data.database import database
from app.utilities.data_order import parse_order_keys_file
from app.utilities.serialization import load_json
from app.utilities.typing import NestedPrimitiveDict

def load_as_dict(data_dir: Path) -> NestedPrimitiveDict:
    as_dict = {}
    category_suffix = database.CATEGORY_SUFFIX
    for key in database.Database.save_data_types:
        as_dict[key] = json_load(data_dir, key)
        # Load any of the categories we need
        if Path(data_dir, key + category_suffix + '.json').exists():
            as_dict[key + category_suffix] = json_load(data_dir, key + category_suffix)
    return as_dict

def json_load(data_dir: str, key: str):
    data_path = Path(data_dir, key)
    if data_path.exists(): # data type is a directory, browse within
        data_fnames = os.listdir(data_path)
        ordering = []
        if '.orderkeys' in data_fnames:
            ordering = parse_order_keys_file(Path(data_dir, key, '.orderkeys'))
        data_fnames: List[Path] = [Path(data_dir, key, fname) for fname in data_fnames if fname.endswith('.json')]
        data_fnames = sorted(data_fnames, key=lambda fname: ordering.index(fname.stem) if fname.stem in ordering else 99999)
        full_data = []
        for fname in data_fnames:
            full_data += load_json(fname)
        return full_data
    else:   # data type is a singular file
        save_loc = Path(data_dir, key + '.json')
        if not save_loc.exists():
            logging.warning("%s does not exist!", save_loc)
            return None
        return load_json(save_loc)