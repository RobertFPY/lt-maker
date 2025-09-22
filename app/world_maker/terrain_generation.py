from __future__ import annotations
from typing import Any, Dict, List, Optional

import math
import random
import time

from app.map_maker.terrain import Terrain
from app.map_maker import simplex_noise

from app.utilities import static_random
from app.utilities.typing import NID, Pos

def generate_terrain(theme: Dict[NID, Any], seed: int) -> WorldTileMap:
    if seed == -1:  # Random seed
        random.seed(time.time())
        seed = random.randint(0, 999_999)
        print("Random Seed: %d" % seed)
    orig_seed = seed
    while True:
        result = _generate_terrain_process(theme, seed)
        seed += 1  # If that didn't work, try a different seed
        if result:
            break
        if seed > orig_seed + 10:
            return None

    return result

def _generate_terrain_process(theme: Dict[NID, Any], seed: int) -> Optional[WorldTileMap]:
    tilemap = WorldTileMap(theme, seed)

    # 1. Generate a simplex noise field of the right size and parameters from the theme
    terrain_noise_map: Dict[Pos, float] = simplex_noise.gen_noise_map(
        (tilemap.width + 2, tilemap.height + 2), seed, theme['starting_frequency'],
        1.0, theme['octaves'], theme['lacunarity'],
        theme['gain'])
    terrain_noise_map = simplex_noise.normalize_noise_map(terrain_noise_map)
    # Move noise map so it's topleft is (-1, -1)
    new_terrain_noise_map = {}
    for pos, value in terrain_noise_map.items():
        new_terrain_noise_map[(pos[0] - 1, pos[1] - 1)] = value
    terrain_noise_map = new_terrain_noise_map

    # 2. Assign terrain based on the simplex noise field
    tilemap.generate_terrain_grid_from_noise(terrain_noise_map)

    # 3. Figure out where cliffs go
    tilemap.generate_cliffs_from_noise(terrain_noise_map)

    # 4. Figure out where rivers go

    # 5. Figure out where forests go
    forest_noise_map: Dict[Pos, float] = simplex_noise.gen_noise_map(
        (tilemap.width, tilemap.height), seed, theme['forest_starting_frequency'],
        1.0, theme['forest_octaves'], theme['forest_lacunarity'],
        theme['forest_gain'])
    forest_noise_map = simplex_noise.normalize_noise_map(forest_noise_map)
    tilemap.determine_forests_from_noise(forest_noise_map)

    # 6. Figure out where roads go
    # 7. Figure out where houses, castles, and ruins go

    return tilemap

class WorldTileMap:
    def __init__(self, theme: Dict[NID, Any], seed: int):
        self.random = static_random.LCG(seed)
        self.theme = theme
        self.width, self.height = theme["size"]
        self.terrain_grid: Dict[Pos, Terrain] = {}

    def get_terrain(self, pos: Pos) -> Optional[Terrain]:
        return self.terrain_grid.get(pos, None)

    def check_bounds(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.width and 0 <= pos[1] < self.height

    def generate_terrain_grid_from_noise(self, noise_map: Dict[Pos, float]):
        for x in range(self.width):
            for y in range(self.height):
                value: float = noise_map[(x, y)]
                if value >= 0.75:
                    terrain = Terrain.MOUNTAIN
                elif 0.75 > value >= 0.70:
                    terrain = Terrain.HILL
                elif 0.70 > value >= 0.4:
                    terrain = Terrain.NOISY_GRASS
                elif 0.4 > value >= 0.35:
                    terrain = Terrain.SAND
                else:
                    terrain = Terrain.SEA
                self.terrain_grid[(x, y)] = terrain

    def generate_cliffs_from_noise(self, noise_map: Dict[Pos, float]):
        # Use Sobel Edge Detection to find areas of discontinuity
        gx = [-1, 0, 1,
              -2, 0, 2,
              -1, 0, 1]
        gy = [1, 2, 1,
              0, 0, 0,
              -1, -2, -1]

        def convolve(values: List[float], kernel: List[int]) -> float:
            assert len(values) == len(kernel)
            return sum([(value * k) for value, k in zip(values, kernel)]) ** 2

        def non_max_suppression(gradient_magnitude: List[float], gradient_orientation: List[float]) -> List[float]:
            output = [0] * len(gradient_magnitude)

            # Ignore the border pixels
            for x in range(1, self.width - 1):
                for y in range(1, self.height - 1):
                    # Will be between -pi and pi
                    magnitude: float = gradient_magnitude[y + self.height * x]
                    direction: float = gradient_orientation[y + self.height * x] 
                    direction += math.pi  # Move to be between 0 and 2*pi

                    if (0 <= direction < math.pi / 8) or (15 * math.pi / 8 <= direction <= 2 * math.pi):
                        before_pixel = gradient_magnitude[y + self.height * (x - 1)]
                        after_pixel = gradient_magnitude[y + self.height * (x + 1)]

                    elif (math.pi / 8 <= direction < 3 * math.pi / 8) or (9 * math.pi / 8 <= direction < 11 * math.pi):
                        before_pixel = gradient_magnitude[(y + 1) + self.height * (x - 1)]
                        after_pixel = gradient_magnitude[(y - 1) + self.height * (x + 1)]

                    elif (3 * math.pi / 8 <= direction < 5 * math.pi / 8) or (11 * math.pi / 8 <= direction < 13 * math.pi):
                        before_pixel = gradient_magnitude[(y - 1) + self.height * x]
                        after_pixel = gradient_magnitude[(y + 1) + self.height * x]

                    else:
                        before_pixel = gradient_magnitude[(y - 1) + self.height * (x - 1)]
                        after_pixel = gradient_magnitude[(y + 1) + self.height * (x + 1)]

                    if magnitude >= before_pixel and magnitude >= after_pixel:
                        output[y + self.height * x] = magnitude
            return output

        x_image, y_image = [], []
        # Do the convolution
        for x in range(self.width):
            for y in range(self.height):
                values = [noise_map[(x - 1, y - 1)], noise_map[(x, y - 1)], noise_map[(x + 1, y - 1)],
                          noise_map[(x - 1, y)], noise_map[(x, y)], noise_map[(x + 1, y)],
                          noise_map[(x - 1, y + 1)], noise_map[(x, y + 1)], noise_map[(x + 1, y + 1)]]
                x_image.append(convolve(values, gx))
                y_image.append(convolve(values, gy))
        
        # Now generate a single magnitude for each point
        gradient_magnitude = [math.sqrt(x**2 + y**2) for (x, y) in zip(x_image, y_image)]
        print(gradient_magnitude)
        gradient_orientation = [math.atan2(y, x) for (x, y) in zip(x_image, y_image)]
        max_magnitude = max(gradient_magnitude)
        gradient_magnitude = [_ / max_magnitude for _ in gradient_magnitude]  # Now between 0 and 1
        print(max_magnitude)
        print(gradient_magnitude)

        for x in range(self.width):
            for y in range(self.height):
                value: float = gradient_magnitude[y + self.height * x]
                if self.get_terrain((x, y)) != Terrain.NOISY_GRASS:
                    continue  # Don't bother if not grass
                
                if value >= (1 - self.theme['cliff_threshold']):
                    self.terrain_grid[(x, y)] = Terrain.CLIFF         

    def determine_forests_from_noise(self, noise_map: Dict[Pos, float]):
        for x in range(self.width):
            for y in range(self.height):
                value: float = noise_map[(x, y)]
                if self.get_terrain((x, y)) != Terrain.NOISY_GRASS:
                    continue  # Don't bother if not grass
                thick_forest_threshold = (1 - self.theme['thick_forest_threshold'])
                if value >= thick_forest_threshold:
                    self.terrain_grid[(x, y)] = Terrain.THICKET
                elif thick_forest_threshold > value >= (1 - self.theme['forest_threshold']):
                    self.terrain_grid[(x, y)] = Terrain.FOREST
