from app.utilities.typing import Pos

from app.map_maker.painter_utils import Painter
from app.map_maker.utilities import random_choice
from app.map_maker.terrain import Terrain

class DesertRockPainter(Painter): 
    base_coord = (0, 0)
    data = {
        'singles': [(0, 0), (1, 0), (0, 1), (2, 0), (2, 1)],
        'pairs1': [(0, 1), ],
        'pairs2': [(1, 1), ],
        'middle': [(0, 0), (1, 0), (0, 1), (2, 0), (2, 1)],
    }
    
    @property
    def check_flood_fill(self):
        return True

    def get_coord(self, tilemap, pos: Pos) -> Pos:
        _, east, _, west = tilemap.get_cardinal_terrain(pos)
        if east != Terrain.DESERT_ROCK and west != Terrain.DESERT_ROCK:
            coord = random_choice(self.data['singles'], pos)
        elif west != Terrain.DESERT_ROCK:
            coord = random_choice(self.data['pairs1'], pos)
        elif east != Terrain.DESERT_ROCK:
            coord = random_choice(self.data['pairs2'], pos)
        else:
            coord = random_choice(self.data['middle'], pos)

        return coord
