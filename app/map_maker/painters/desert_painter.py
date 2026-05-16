from app.utilities.typing import Pos

from app.map_maker.utilities import random_choice
from app.map_maker.painters import WangCorner16Painter
from app.map_maker.terrain import Terrain

class DesertPainter(WangCorner16Painter):
    terrain_like = (Terrain.DESERT, Terrain.DESERT_CLIFF, Terrain.DESERT_ROCK,
                    Terrain.BRIDGEH, Terrain.BRIDGEV, Terrain.WALL_TOP, Terrain.WALL_BOTTOM)
    base_coord = (0, 4)

    full_desert_data = [(x, y) for x in range(3) for y in range(4, 10)]

    def _surrounded_by_desert(self, tilemap, pos: Pos) -> bool:
        return all(_ == Terrain.DESERT for _ in tilemap.get_cardinal_terrain(pos) + tilemap.get_diagonal_terrain(pos))

    def get_coord(self, tilemap, position: Pos) -> Pos:
        index = self._determine_index(tilemap, position)
        if index == 15 and self._surrounded_by_desert(tilemap, position):
            coord = random_choice(self.full_desert_data, position)        
        else:
            coord = random_choice([(index, k) for k in range(self.limit[index])], position)
        return coord
