from typing import Any, Dict, Tuple

from app.utilities.data import Data
from app.utilities.typing import NID

from app.dungeon_maker.themes import ThemeParameter, percent

theme_parameters = Data([
    ThemeParameter('size', "Map Size", (25, 25), Tuple[int, int]),
    ThemeParameter('starting_frequency', "Frequency", 0.125, float),
    ThemeParameter('octaves', "Number of Octaves", 4, int),
    ThemeParameter('lacunarity', "Lacunarity", 2.0, float),
    ThemeParameter('gain', "Gain", 0.5, float),
    ThemeParameter('forest_starting_frequency', "Forest Frequency", 0.2, float),
    ThemeParameter('forest_octaves', "Forest Octaves", 4, int),
    ThemeParameter('forest_lacunarity', "Forest Lacunarity", 2.0, float),
    ThemeParameter('forest_gain', "Forest Gain", 0.5, float),
    ThemeParameter('cliff_threshold', "Cliff Chance", 0.3, percent),
    ThemeParameter('forest_threshold', "Forest Chance", 0.35, percent),
    ThemeParameter('thick_forest_threshold', "Thick Forest Chance", 0.2, percent),
])

theme_presets: Dict[str, Dict[NID, Any]] = {
    "Default": {},
}

def get_default_theme() -> Dict[NID, Any]:
    new_theme = {}
    for parameter in theme_parameters:
        new_theme[parameter.nid] = parameter.value
    return new_theme

def get_theme(preset: NID) -> Dict[NID, Any]:
    """Given a theme preset's nid, return the theme
    parameters for it"""
    base_theme = get_default_theme()
    theme_preset = theme_presets[preset]
    base_theme.update(theme_preset)
    return base_theme
