from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Tuple

from enum import Enum

import bisect
import math
import random
import time

from app.map_maker.terrain import Terrain
from app.map_maker import simplex_noise, utilities

from app.utilities import direction, static_random, utils
from app.utilities.typing import NID, Pos

NOISE_LACUNARITY = 2.0
NOISE_GAIN = 0.5
# Derived seeds -- distinct fields must not correlate, so each gets seed + its own offset.
HILL_SEED_OFFSET = 1
PASS_SEED_OFFSET = 2
# The pass field modulates mountain-spine width along each ridge; finer than the hill
# field so a low patch cuts *across* a ridge rather than tracking it. 2x -> a pass is
# roughly half a hill wavelength wide (a few tiles at the default frequency).
PASS_FREQUENCY_MULTIPLIER = 2.0
# Exponent on the pass field in the spine score. At 1.0 the hill budget spreads evenly
# between thinning skirts and cutting passes; >1 spends it on carving passes through
# ridges first, keeping skirts mountainous right up to the band edge elsewhere.
PASS_STRENGTH = 2.0

# River source spacing (Chebyshev). Passes 2-3 halve both ranges (Civ's addRivers).
RIVER_SOURCE_MIN_RIVER_RANGE = 4
RIVER_SOURCE_MIN_SEA_RANGE = 2
# Deterministic per-tile jitter modulus. A pure function of (x, y, seed) added to every
# river_value; two rivers approaching the same valley break ties the same way and merge
# instead of running side by side (Civ's getRiverValueAtPlot trick).
RIVER_JITTER = 10
# Terrain -> altitude class for the flow walk. Missing entries (grass/forest family) = 2.
RIVER_ALTITUDE = {
    Terrain.MOUNTAIN: 4, Terrain.CLIFF: 4,
    Terrain.HILL: 3,
    Terrain.SAND: 1,
    Terrain.SEA: 0, Terrain.RIVER: 0,
}
# An off-map tile contributes this to a neighbor sum (Civ's NUM_PLOT_TYPES * 10), so
# river_value spikes near the border and rivers steer away from hugging the edge.
RIVER_OFF_MAP_ALTITUDE = 40
# Terrain a river tile may be painted over; rivers may cut through forest but never
# through mountains/cliffs (hard-excluded during the walk).
RIVER_PAINTABLE = (Terrain.HILL, Terrain.NOISY_GRASS, Terrain.SAND,
                   Terrain.FOREST, Terrain.SPARSE_FOREST, Terrain.THICKET)

class RiverEnd(Enum):
    """How a flow walk terminated. SEA/RIVER/OFFMAP are clean exits; DEADEND/CAP mean
    the river ran out of legal moves (still kept if it painted >= 3 tiles)."""
    SEA = 'sea'
    RIVER = 'river'
    OFFMAP = 'offmap'
    DEADEND = 'deadend'
    CAP = 'cap'

def derive_octaves(frequency: float) -> int:
    """Octaves whose wavelength falls below ~2 tiles (the tile Nyquist limit)
    add nothing visible, so octave depth follows from frequency."""
    return max(1, math.ceil(math.log2(0.5 / frequency)))

def get_threshold_from_percent(noise_map: Dict[Pos, float], percent: float,
                               width: int, height: int,
                               positions: Optional[Iterable[Pos]] = None) -> float:
    """Value v such that `percent`% of in-bounds tiles have noise < v.
    Mirrors Civ 4's CyFractal.getHeightFromPercent. Only in-bounds tiles
    (0 <= x < width, 0 <= y < height) count; the border ring is excluded.
    `positions`, if given, restricts the percentile pool to that subset
    (e.g. land tiles only) instead of the full width x height grid."""
    if positions is None:
        positions = [(x, y) for x in range(width) for y in range(height)]
    values = sorted(noise_map[pos] for pos in positions)
    if percent <= 0:
        return values[0] - 1.0
    if percent >= 100:
        return values[-1] + 1.0
    index = min(len(values) - 1, int(len(values) * percent / 100))
    return values[index]

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

def generate_topology(theme: Dict[NID, Any], seed: int) -> Tuple[WorldTileMap, Dict[Pos, float], float, float]:
    """Elevation classification (SEA/SAND/land) plus hill/peak bands -- everything up to,
    but not including, the terrain-mutating passes (rivers/cliffs/forests). Split out from
    `_generate_terrain_process` so tests can measure band classification in isolation from
    those later passes, which also consume NOISY_GRASS/HILL tiles."""
    tilemap = WorldTileMap(theme, seed)

    # 1. Generate a simplex noise field of the right size and parameters from the theme
    terrain_noise_map: Dict[Pos, float] = simplex_noise.gen_noise_map(
        (tilemap.width + 2, tilemap.height + 2), seed, theme['starting_frequency'],
        1.0, derive_octaves(theme['starting_frequency']), NOISE_LACUNARITY,
        NOISE_GAIN)
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

    # 2. Assign terrain based on the simplex noise field: SEA / SAND / land (NOISY_GRASS)
    sea_threshold, high_elevation_threshold = tilemap.generate_terrain_grid_from_noise(terrain_noise_map)

    # 2.5 Hills and mountains as bands of their own noise fields, decoupled from elevation,
    # so ranges snake across land instead of tracking the elevation blob.
    hill_frequency = theme['hill_frequency']
    hill_noise_map: Dict[Pos, float] = simplex_noise.gen_noise_map(
        (tilemap.width, tilemap.height), seed + HILL_SEED_OFFSET, hill_frequency,
        1.0, derive_octaves(hill_frequency), NOISE_LACUNARITY, NOISE_GAIN)
    hill_noise_map = simplex_noise.normalize_noise_map(hill_noise_map)

    pass_frequency = hill_frequency * PASS_FREQUENCY_MULTIPLIER
    pass_noise_map: Dict[Pos, float] = simplex_noise.gen_noise_map(
        (tilemap.width, tilemap.height), seed + PASS_SEED_OFFSET, pass_frequency,
        1.0, derive_octaves(pass_frequency), NOISE_LACUNARITY, NOISE_GAIN)
    pass_noise_map = simplex_noise.normalize_noise_map(pass_noise_map)

    tilemap.generate_bands_from_noise(hill_noise_map, pass_noise_map)

    return tilemap, terrain_noise_map, sea_threshold, high_elevation_threshold

def _generate_terrain_process(theme: Dict[NID, Any], seed: int) -> Optional[WorldTileMap]:
    tilemap, terrain_noise_map, _sea_threshold, _high_elevation_threshold = generate_topology(theme, seed)

    # 3. Figure out where cliffs go
    tilemap.generate_cliffs_from_noise(terrain_noise_map)

    # 4. Figure out where forests go
    forest_noise_map: Dict[Pos, float] = simplex_noise.gen_noise_map(
        (tilemap.width, tilemap.height), seed, theme['forest_starting_frequency'],
        1.0, derive_octaves(theme['forest_starting_frequency']), NOISE_LACUNARITY,
        NOISE_GAIN)
    forest_noise_map = simplex_noise.normalize_noise_map(forest_noise_map)
    tilemap.generate_forests_from_noise(forest_noise_map)

    # 5. Figure out where rivers go. Rivers run *after* cliffs and forests, matching Civ's
    # order (features last) and letting rivers read the finished altitude field, including
    # forest tiles they may cut through.
    tilemap.generate_rivers()

    return tilemap

class WorldTileMap:
    def __init__(self, theme: Dict[NID, Any], seed: int):
        self.random = static_random.LCG(seed)
        self.seed = seed
        self.theme = theme
        self.width, self.height = theme["size"]
        self.terrain_grid: Dict[Pos, Terrain] = {}

    def get_terrain(self, pos: Pos) -> Optional[Terrain]:
        return self.terrain_grid.get(pos, None)

    def check_bounds(self, pos: Pos) -> bool:
        return 0 <= pos[0] < self.width and 0 <= pos[1] < self.height

    def generate_terrain_grid_from_noise(self, noise_map: Dict[Pos, float]) -> Tuple[float, float]:
        # Cumulative percentile thresholds, computed on the final (post-elevation,
        # post-water-border, post-sink-fill) field, so ratios are exact for every seed.
        # This field now decides only SEA / SAND / land -- hills and mountains are
        # classified separately in generate_bands_from_noise, from the hill field.
        sea_percent = self.theme['sea_percent'] * 100
        sand_percent = self.theme['sand_percent'] * 100

        sea_threshold = get_threshold_from_percent(noise_map, sea_percent, self.width, self.height)
        sand_threshold = get_threshold_from_percent(noise_map, sea_percent + sand_percent, self.width, self.height)

        for x in range(self.width):
            for y in range(self.height):
                value: float = noise_map[(x, y)]
                if value < sea_threshold:
                    terrain = Terrain.SEA
                elif value < sand_threshold:
                    terrain = Terrain.SAND
                else:
                    terrain = Terrain.NOISY_GRASS
                self.terrain_grid[(x, y)] = terrain

        # Stand-in "high ground" bound for the river logic, which still reads the
        # elevation field for now (Phase 3 replaces river source selection entirely).
        high_elevation_threshold = get_threshold_from_percent(
            noise_map, 100 - self.theme['highland_percent'] * 100, self.width, self.height)

        return sea_threshold, high_elevation_threshold

    def generate_bands_from_noise(self, hill_noise_map: Dict[Pos, float], pass_noise_map: Dict[Pos, float]):
        # Hills/mountains form as percentile *bands* of the hill field (a level set of a
        # continuous field is an elongated ridge, not a blob) rather than being thresholded
        # directly -- this is what produces mountain ranges instead of scattered clumps.
        land_positions = [(x, y) for x in range(self.width) for y in range(self.height)
                          if self.get_terrain((x, y)) == Terrain.NOISY_GRASS]
        if not land_positions:
            return

        highland_percent = self.theme['highland_percent'] * 100
        half_width = highland_percent / 4  # two bands, each with two edges

        # Percentile rank of each land tile within the hill field; the bands and the
        # spines inside them are both defined in this space. Centrality is 0 on a
        # band's center line (the ridge crest) and 1 at its edge; tiles outside both
        # bands stay NOISY_GRASS.
        sorted_values = sorted(hill_noise_map[pos] for pos in land_positions)
        total = len(sorted_values)
        centrality: Dict[Pos, float] = {}
        for pos in land_positions:
            percentile = bisect.bisect_left(sorted_values, hill_noise_map[pos]) / total * 100
            for center in (25, 75):
                band_position = abs(percentile - center) / half_width
                if band_position < 1:
                    centrality[pos] = band_position
                    break
        if not centrality:
            return

        # Mountains are the most-central slice of each band, so every range is a
        # mountain spine flanked by hill skirts. The pass field scales spine width
        # along the ridge: where it nears zero the score diverges and the spine
        # pinches off entirely, leaving an all-hill gap -- a mountain pass.
        # Thresholding the score at a percentile over highland tiles keeps mountain
        # coverage at exactly peak_percent regardless of the pass field's distribution.
        score_map = {pos: value / max(pass_noise_map[pos], 1e-9) ** PASS_STRENGTH
                     for pos, value in centrality.items()}
        highland_positions = list(centrality)
        peak_percent = self.theme['peak_percent'] * 100
        peak_threshold = get_threshold_from_percent(score_map, peak_percent, self.width, self.height, highland_positions)

        for pos in highland_positions:
            if score_map[pos] <= peak_threshold:
                self.terrain_grid[pos] = Terrain.MOUNTAIN
            else:
                self.terrain_grid[pos] = Terrain.HILL

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
                # Clamped noise (normalize_noise_map) can land exactly on value == 1.0,
                # so a bare `>= (1 - 0)` threshold would still fire at 0% chance.
                thick_forest_threshold = (1 - self.theme['thick_forest_threshold'])
                if self.theme['thick_forest_threshold'] > 0 and value >= thick_forest_threshold:
                    self.terrain_grid[(x, y)] = Terrain.THICKET
                elif self.theme['forest_threshold'] > 0 and thick_forest_threshold > value >= (1 - self.theme['forest_threshold']):
                    self.terrain_grid[(x, y)] = Terrain.FOREST

    def _identify_landmasses(self) -> Tuple[Dict[Pos, int], Dict[int, int]]:
        """Flood-fill 4-connected non-SEA tiles into landmasses. Returns
        (area_id per tile, size per area)."""
        area_id: Dict[Pos, int] = {}
        area_size: Dict[int, int] = {}
        next_area = 0
        for x in range(self.width):
            for y in range(self.height):
                start = (x, y)
                if start in area_id or self.get_terrain(start) == Terrain.SEA:
                    continue
                stack = [start]
                area_id[start] = next_area
                size = 0
                while stack:
                    cur = stack.pop()
                    size += 1
                    for adj in direction.get_cardinal_positions(cur):
                        if self.check_bounds(adj) and adj not in area_id \
                                and self.get_terrain(adj) != Terrain.SEA:
                            area_id[adj] = next_area
                            stack.append(adj)
                area_size[next_area] = size
                next_area += 1
        return area_id, area_size

    def _altitude_class(self, pos: Pos) -> int:
        return RIVER_ALTITUDE.get(self.get_terrain(pos), 2)

    def _river_value(self, pos: Pos) -> int:
        # altitude of the tile (weighted) + altitudes of its 8 neighbors + deterministic
        # jitter. Rivers greedily descend this field; jitter (a pure function of position
        # and map seed) is what makes two rivers heading into the same valley merge.
        self_alt = self._altitude_class(pos) if self.check_bounds(pos) else 0
        neighbor_total = 0
        neighbors = direction.get_cardinal_positions(pos) + direction.get_diagonal_positions(pos)
        for n in neighbors:
            if self.check_bounds(n):
                neighbor_total += self._altitude_class(n)
            else:
                neighbor_total += RIVER_OFF_MAP_ALTITUDE
        # Deterministic per-tile jitter (0 .. RIVER_JITTER-1), a pure function of position
        # and map seed, so two rivers reaching the same valley break ties identically and
        # merge. random_random hides the coordinate hash in the trusted map_maker util.
        jitter = int(utilities.random_random(pos, self.seed) * RIVER_JITTER)
        return self_alt * 20 + neighbor_total + jitter

    def _do_river(self, source: Pos) -> Tuple[List[Pos], RiverEnd]:
        # Greedy min-river_value descent with Civ's no-U-turn rule. Returns the path
        # (starting at source) and how it ended (see RiverEnd).
        path: List[Pos] = [source]
        path_set = {source}
        first_dir: Optional[direction.Direction] = None
        prev_dir: Optional[direction.Direction] = None
        reason = RiverEnd.DEADEND
        for _ in range(self.width * self.height):
            current = path[-1]
            candidates: List[Tuple[Pos, direction.Direction]] = []
            for n in direction.get_cardinal_positions(current):
                step_dir = direction.Direction.determine(current, n)
                if prev_dir is not None and step_dir == direction.Direction.opposite(prev_dir):
                    continue
                if first_dir is not None and step_dir == direction.Direction.opposite(first_dir):
                    continue
                if n in path_set:
                    continue
                if self.check_bounds(n) and self.get_terrain(n) in (Terrain.MOUNTAIN, Terrain.CLIFF):
                    continue
                candidates.append((n, step_dir))
            if not candidates:
                reason = RiverEnd.DEADEND
                break
            best_pos, best_dir = min(candidates, key=lambda c: self._river_value(c[0]))
            if first_dir is None:
                first_dir = best_dir
            prev_dir = best_dir
            if not self.check_bounds(best_pos):
                reason = RiverEnd.OFFMAP
                break
            terrain = self.get_terrain(best_pos)
            if terrain == Terrain.SEA:
                reason = RiverEnd.SEA
                break
            if terrain == Terrain.RIVER:
                reason = RiverEnd.RIVER
                break
            path.append(best_pos)
            path_set.add(best_pos)
        else:
            reason = RiverEnd.CAP
        return path, reason

    def generate_rivers(self):
        # Port of Civ 4's addRivers/doRiver: rivers seeded per landmass with quotas and
        # spacing, then flowed downhill along the altitude field until they hit water or
        # the map edge (or merge into an existing river). Replaces the old strictly-downhill
        # noise walk. self.river_sources / self.rivers are exposed for tests.
        self.river_sources: List[Pos] = []
        self.rivers: List[Tuple[List[Pos], RiverEnd]] = []

        tiles_per_river_tile = self.theme['tiles_per_river_tile']
        if tiles_per_river_tile <= 0:
            return

        area_id, area_size = self._identify_landmasses()
        river_tiles_placed: Dict[int, int] = {area: 0 for area in area_size}
        placed_river_tiles: set = set()

        def under_quota(area: int) -> bool:
            return river_tiles_placed[area] < area_size[area] // tiles_per_river_tile + 1

        def near_sea(pos: Pos, rng: int) -> bool:
            for dx in range(-rng, rng + 1):
                for dy in range(-rng, rng + 1):
                    n = (pos[0] + dx, pos[1] + dy)
                    if self.check_bounds(n) and self.get_terrain(n) == Terrain.SEA:
                        return True
            return False

        def near_river(pos: Pos, rng: int) -> bool:
            for dx in range(-rng, rng + 1):
                for dy in range(-rng, rng + 1):
                    if (pos[0] + dx, pos[1] + dy) in placed_river_tiles:
                        return True
            return False

        for pass_num in range(4):
            # Passes 0-1 place the well-spaced "nice" rivers at full spacing. Passes 2-3
            # are quota backfill: they only fire on landmasses still under quota, and halve
            # both ranges so a river can be squeezed onto a small or cramped landmass that
            # full spacing would leave with no legal source tile at all.
            if pass_num <= 1:
                river_range = RIVER_SOURCE_MIN_RIVER_RANGE
                sea_range = RIVER_SOURCE_MIN_SEA_RANGE
            else:
                river_range = RIVER_SOURCE_MIN_RIVER_RANGE // 2
                sea_range = RIVER_SOURCE_MIN_SEA_RANGE // 2

            for x in range(self.width):
                for y in range(self.height):
                    pos = (x, y)
                    terrain = self.get_terrain(pos)
                    if terrain == Terrain.SEA:
                        continue
                    area = area_id[pos]
                    highland = terrain in (Terrain.HILL, Terrain.MOUNTAIN)

                    if pass_num == 0:
                        candidate = highland
                    elif pass_num == 1:
                        candidate = (not near_sea(pos, RIVER_SOURCE_MIN_SEA_RANGE)
                                     and self.random.randint(0, 7) == 0)
                    elif pass_num == 2:
                        candidate = highland and under_quota(area)
                    else:
                        candidate = under_quota(area)
                    if not candidate:
                        continue

                    # Spacing: keep sources apart and away from the coast. Checked against
                    # every earlier river's tiles (placed within this same pass too), so
                    # rivers spread instead of bunching.
                    if near_sea(pos, sea_range) or near_river(pos, river_range):
                        continue

                    path, reason = self._do_river(pos)
                    paintable = [p for p in path if self.get_terrain(p) in RIVER_PAINTABLE]
                    if len(paintable) < 3:
                        continue  # too short -- erase it
                    for p in paintable:
                        self.terrain_grid[p] = Terrain.RIVER
                    placed_river_tiles.update(path)
                    river_tiles_placed[area] += len(paintable)
                    self.river_sources.append(pos)
                    self.rivers.append((path, reason))
