import os
import shutil

from app.engine import engine
from app.constants import COLORKEY
from app.utilities import utils
from app.utilities.typing import NestedPrimitiveDict
from app.data.serialization.migrators.migrator_base import MigratorBase

class Migrator0(MigratorBase):
    def migrate_database(self, db_dict: NestedPrimitiveDict) -> NestedPrimitiveDict:
        return db_dict

    def migrate_resources(self, resource_dict: NestedPrimitiveDict, data_dir: str) -> NestedPrimitiveDict:
        portraits = resource_dict.get('portraits')
        if not portraits:
            return resource_dict

        # Back-up into 'old_portraits' folder
        shutil.copytree(os.path.join('.', data_dir, 'portraits'),
                        os.path.join('.', data_dir, 'old_portraits'),
                        dirs_exist_ok=True)
        filetype = '.png'
        for portrait in portraits:
            # Update PNG files
            fn = os.path.join(data_dir, 'portraits', portrait.get('nid') + filetype)
            im = engine.image_load(fn)
            face_frame = im.subsurface((0, 0, 96, 80))
            blink_frames = im.subsurface((96, 48, 32, 32))
            mouth_frames = im.subsurface((0, 80, 128, 32))
            minimug = im.subsurface((96, 16, 32, 32))

            new_im = engine.create_simple_surface((160, 112))
            new_im.fill(COLORKEY)
            new_im.blit(face_frame, (32, 0))
            new_im.blit(blink_frames, (128, 48))
            new_im.blit(mouth_frames, (0, 80))
            new_im.blit(minimug, (128, 80))
            engine.save_surface(new_im, fn)

            # Update data
            portrait['info_offset'] = (8, portrait.get('info_offset'))
            portrait['chibi_coord'] = (128, 80)
            portrait['full_size'] = (160, 112)
            portrait['face_size'] = (96, 80)
            portrait['blink_size'] = (32, 16)
            portrait['mouth_size'] = (32, 16)
            portrait['blink_frames'] = 2
            portrait['mouth_frames'] = 3

        return resource_dict