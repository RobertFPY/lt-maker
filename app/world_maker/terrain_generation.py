from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import math
import random
import time

from app.map_maker.terrain import Terrain
from app.map_maker import simplex_noise

from app.utilities import direction, static_random, utils
from app.utilities.typing import NID, Pos

MOUNTAIN_THRESHOLD = 0.75
SEA_THRESHOLD = 0.35

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

    # Modify elevation
    new_terrain_noise_map = {}
    for pos, value in terrain_noise_map.items():
        new_terrain_noise_map[pos] = utils.clamp(value + theme['elevation'], 0, 1)
    terrain_noise_map = new_terrain_noise_map

    # Set Water Border
    if theme['water_border']:
        new_terrain_noise_map = {}
        for pos, value in terrain_noise_map.items():
            distance_from_center_x = abs(tilemap.width/2 - pos[0])/(tilemap.width/2)
            distance_from_center_y = abs(tilemap.height/2 - pos[1])/(tilemap.height/2)
            total_distance_from_center = math.sqrt(distance_from_center_x**2 + distance_from_center_y**2)
            if total_distance_from_center < 0.9:
                total_distance_from_center = 0
            new_value = value * utils.clamp(1 - total_distance_from_center, 0, 1)
            new_terrain_noise_map[pos] = new_value
        terrain_noise_map = new_terrain_noise_map

    # 1.5 Fill any sinks with the lowest average of the adjacent tiles
    new_terrain_noise_map = {}
    for pos, value in terrain_noise_map.items():
        adjacent_positions = [adj for adj in direction.get_cardinal_positions(pos) if adj in terrain_noise_map]
        lowest_average = min(terrain_noise_map[adj] for adj in adjacent_positions)
        if value < lowest_average:
            new_terrain_noise_map[pos] = lowest_average
        else:
            new_terrain_noise_map[pos] = value
    terrain_noise_map = new_terrain_noise_map

    # 2. Assign terrain based on the simplex noise field
    tilemap.generate_terrain_grid_from_noise(terrain_noise_map)

    # 3. Figure out where rivers go
    tilemap.generate_rivers_from_noise(terrain_noise_map)

    # 4. Figure out where cliffs go
    tilemap.generate_cliffs_from_noise(terrain_noise_map)

    # 5. Figure out where forests go
    forest_noise_map: Dict[Pos, float] = simplex_noise.gen_noise_map(
        (tilemap.width, tilemap.height), seed, theme['forest_starting_frequency'],
        1.0, theme['forest_octaves'], theme['forest_lacunarity'],
        theme['forest_gain'])
    forest_noise_map = simplex_noise.normalize_noise_map(forest_noise_map)
    tilemap.generate_forests_from_noise(forest_noise_map)

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
                if value >= MOUNTAIN_THRESHOLD:
                    terrain = Terrain.MOUNTAIN
                elif 0.75 > value >= 0.70:
                    terrain = Terrain.HILL
                elif 0.70 > value >= 0.4:
                    terrain = Terrain.NOISY_GRASS
                elif 0.4 > value >= SEA_THRESHOLD:
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
        gradient_orientation = [math.atan2(y, x) for (x, y) in zip(x_image, y_image)]
        max_magnitude = max(gradient_magnitude)
        if max_magnitude > 0:
            gradient_magnitude = [_ / max_magnitude for _ in gradient_magnitude]  # Now between 0 and 1
        else:
            gradient_magnitude = [0 for _ in gradient_magnitude]

        for x in range(self.width):
            for y in range(self.height):
                value: float = gradient_magnitude[y + self.height * x]
                if self.get_terrain((x, y)) != Terrain.NOISY_GRASS:
                    continue  # Don't bother if not grass
                
                if value >= (1 - self.theme['cliff_threshold']):
                    self.terrain_grid[(x, y)] = Terrain.CLIFF         

    def generate_forests_from_noise(self, noise_map: Dict[Pos, float]):
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

    def generate_rivers_from_noise(self, noise_map: Dict[Pos, float]):
        # Locate all locations near mountains, (high terrain noise)
        # Locate all locations near seas (low terrain noise)
        # based on a river incidence rate, draw connections between high noise tiles and low noise tiles, generally preferring low noise tile movement draw connections between the two
        # Then remove any rivers which cross each other (use order or something), and remove any rivers which overlap a mountain after leaving a mountain

        def get_start_and_end_candidates(high_limit: float, low_limit: float) -> Tuple[List[Pos], List[Pos]]:
            high_noise_locations: List[Pos] = []
            low_noise_locations: List[Pos] = []
            for x in range(self.width):
                for y in range(self.height):
                    value: float = noise_map[(x, y)]
                    if value >= high_limit:
                        high_noise_locations.append((x, y))
                    elif value < low_limit:
                        low_noise_locations.append((x, y))
            return high_noise_locations, low_noise_locations

        # Figure out which positions should be used as start and end positions
        high_limit = MOUNTAIN_THRESHOLD
        low_limit = SEA_THRESHOLD
        high_noise_locations, low_noise_locations = \
            get_start_and_end_candidates(high_limit, low_limit)
        while not high_noise_locations or not low_noise_locations:
            high_limit -= 0.05
            low_limit += 0.05
            high_noise_locations, low_noise_locations = \
                get_start_and_end_candidates(high_limit, low_limit)

        number_of_rivers = self.theme['river_incidence'] * self.width * self.height 
        rivers: List[List[Pos]] = []
        while len(utils.flatten_list(rivers)) < number_of_rivers and high_noise_locations:
            starting_point = self.random.choice(high_noise_locations)
            # Remove the starting point from the high noise locations
            high_noise_locations.remove(starting_point)

            river: List[Pos] = [starting_point]
            current_point = starting_point

            # Build out river!
            directions = []
            while True:
                adjacent_points = direction.get_cardinal_positions(current_point)
                # Make sure we don't go backwards
                adjacent_points = [pos for pos in adjacent_points if pos not in river]
                # Make sure we don't go in the same direction four times in row
                adjacent_points = [pos for pos in adjacent_points if len(river) < 4 
                                   or direction.Direction.determine(current_point, pos) != direction.Direction.determine(river[-2], river[-1])
                                   or direction.Direction.determine(current_point, pos) != direction.Direction.determine(river[-3], river[-2])
                                   or direction.Direction.determine(current_point, pos) != direction.Direction.determine(river[-4], river[-3])
                                   ]
                # Make sure we only go downhill
                adjacent_points = [pos for pos in adjacent_points if (noise_map[pos] if self.check_bounds(pos) else 0.2) <= noise_map[river[-1]]]

                if not adjacent_points:
                    # This is not a valid river, ignore it
                    river = []
                    break

                noise_values = [noise_map[pos] if self.check_bounds(pos) else 0.2 for pos in adjacent_points]
                min_index = noise_values.index(min(noise_values))
                directions.append(direction.Direction.determine(current_point, adjacent_points[min_index]))
                current_point = adjacent_points[min_index]
                # If reach sea, we are done
                # If reach the edge of the map, we are done
                # If reach another river, we are done
                if noise_map[current_point] < SEA_THRESHOLD \
                        or not self.check_bounds(current_point) \
                        or current_point in utils.flatten_list(rivers):  
                    break
                else:
                    river.append(current_point)
            river = [pos for pos in river if self.get_terrain(pos) in (Terrain.HILL, Terrain.NOISY_GRASS, Terrain.SAND)]
            rivers.append(river)

        # Check that rivers don't cross each other -- Later
        # for river in rivers:

        # Convert terrain
        for river in rivers:
            for pos in river:
                current_terrain = self.get_terrain(pos)
                if current_terrain in (Terrain.HILL, Terrain.NOISY_GRASS, Terrain.SAND):
                    self.terrain_grid[pos] = Terrain.RIVER
