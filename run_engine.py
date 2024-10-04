import json
from pathlib import Path
import os, sys

from app.constants import VERSION
from app.data.metadata import Metadata
from app.data.resources.resources import RESOURCES
from app.data.database.database import DB
from app.data.serialization.dataclass_serialization import dataclass_from_dict
from app.engine import engine
from app.engine import config as cf
from app.engine import driver
from app.engine import game_state
from app.engine.codegen import source_generator
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.utilities.system_info import is_editor_engine_built_version

def main(name: str = 'testing_proj'):
    # Translation currently unused within engine proper
    # If you need to use translation, remember to copy the locale folder to your build.
    # from app.editor.editor_locale import init_locale
    # init_locale()
    if not os.path.exists(name + '.ltproj'):
        raise ValueError("Could not locate LT project %s" % (name + '.ltproj'))
    metadata = dataclass_from_dict(Metadata, json.loads(Path(name + '.ltproj', 'metadata.json').read_text()))
    if metadata.has_fatal_errors:
        raise ValueError("Fatal errors detected in game. If you are the developer, please validate and then save your game data before proceeding. Aborting launch.")
    RESOURCES.load(name + '.ltproj', CURRENT_SERIALIZATION_VERSION)
    DB.load(name + '.ltproj', CURRENT_SERIALIZATION_VERSION)
    title = DB.constants.value('title')
    driver.start(title)
    game = game_state.start_game()
    driver.run(game)

def test_play(name: str = 'testing_proj'):
    if not os.path.exists(name + '.ltproj'):
        raise ValueError("Could not locate LT project %s" % (name + '.ltproj'))
    metadata = dataclass_from_dict(Metadata, json.loads(Path(name + '.ltproj', 'metadata.json').read_text()))
    if metadata.has_fatal_errors:
        raise ValueError("Fatal errors detected in game. If you are the developer, please validate and then save your game data before proceeding. Aborting launch.")
    RESOURCES.load(name + '.ltproj', CURRENT_SERIALIZATION_VERSION)
    DB.load(name + '.ltproj', CURRENT_SERIALIZATION_VERSION)
    title = DB.constants.value('title')
    driver.start(title, from_editor=True)
    if 'DEBUG' in DB.levels:
        game = game_state.start_level('DEBUG')
    else:
        first_level_nid = DB.levels[0].nid
        game = game_state.start_level(first_level_nid)
    driver.run(game)

def inform_error():
    print("=== === === === === ===")
    print("A bug has been encountered.")
    print("Please copy this error log and send it to rainlash!")
    print('Or send the file "saves/debug.log.1" to rainlash!')
    print("Thank you!")
    print("=== === === === === ===")

def find_and_run_project():
    proj = '.ltproj'
    for name in os.listdir('./'):
        if name.endswith(proj):
            name = name.replace(proj, '')
            if not name.startswith('autosave'):
                main(name)

if __name__ == '__main__':
    import logging, traceback
    from app import lt_log
    success = lt_log.create_logger()
    if not success:
        engine.terminate()

    # compile necessary files
    if not is_editor_engine_built_version():
        source_generator.generate_all()

    try:
        find_and_run_project()
        # main('lion_throne')
        # test_play('sacred_stones')
    except Exception as e:
        logging.exception(e)
        inform_error()
        pyver = f'{sys.version_info.major}.{sys.version_info.minor}'
        print(f'*** Lex Talionis Engine Version {VERSION} on Python {pyver} ***')
        print('Main Crash {0}'.format(str(e)))

        # Now print exception to screen
        import time
        time.sleep(0.5)
        traceback.print_exc()
        time.sleep(0.5)
        inform_error()
        engine.terminate(crash=True)
        if cf.SETTINGS['debug']:
            time.sleep(5)
        else:
            time.sleep(20)
