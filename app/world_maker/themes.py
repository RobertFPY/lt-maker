from typing import Any, Dict, Tuple

from app.utilities.data import Data
from app.utilities.typing import NID

from app.dungeon_maker.themes import ThemeParameter, percent

theme_parameters = Data([
    ThemeParameter('size', "Map Size", (25, 25), Tuple[int, int]),
    ThemeParameter('starting_frequency', "Frequency", 0.125, float, "How close together samples are on the noise wave; smaller frequency is closer sampling"),
    ThemeParameter('forest_starting_frequency', "Forest Frequency", 0.2, float, "How close together samples are on the noise wave; smaller frequency is closer sampling"),
    ThemeParameter('cliff_threshold', "Cliff Threshold", 0.3, float, "Necessary discontinuity in noise value to produce a cliff"),
    ThemeParameter('forest_threshold', "Forest Chance", 0.35, percent, "Height of forest noise map that produces forests"),
    ThemeParameter('thick_forest_threshold', "Thick Forest Chance", 0.2, percent, "Height of forest noise map that produces thick forests"),
    ThemeParameter('tiles_per_river_tile', "Tiles Per River Tile", 40, int, "One river tile is targeted per this many land tiles per landmass; 0 disables rivers"),
    ThemeParameter('elevation', "Elevation Modification", 0.0, float, "Modify the effective elevation generated"),
    ThemeParameter('water_border', "Set Sea Border", False, bool, "Add a sea border around the map"),
    ThemeParameter('sea_percent', "Sea Percent", 0.35, percent, "Portion of map that is sea"),
    ThemeParameter('sand_percent', "Sand Percent", 0.05, percent, "Portion of map that is beach/sand (above sea)"),
    ThemeParameter('hill_frequency', "Hill Frequency", 0.15, float, "How close together samples are on the hill/mountain noise wave"),
    ThemeParameter('highland_percent', "Highland Percent", 0.30, percent, "Portion of land that is hills+mountains"),
    ThemeParameter('peak_percent', "Peak Percent", 0.40, percent, "Portion of highland that is mountains (rest is hills)"),
])

theme_presets: Dict[str, Dict[NID, Any]] = {
    "Default": {},
    "Pangaea": {"water_border": True}
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
