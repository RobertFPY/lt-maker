from typing import Tuple

import pygame

from app.utilities.typing import Pos

def _get_image(image: pygame.Surface, coord: Pos, tile_size: Tuple[int, int]) -> pygame.Surface:
    width, height = tile_size
    return image.subsurface(
        (coord[0] * width,
         coord[1] * height,
         width, height)).copy()

def get_image8(image: pygame.Surface, coord: Pos) -> pygame.Surface:
    return _get_image(image, coord, (8, 8))

def get_image16(image: pygame.Surface, coord: Pos) -> pygame.Surface:
    return _get_image(image, coord, (16, 16))

def _find_limit(image: pygame.Surface, idx: int, skip: Tuple[int, int], offset: int = 0) -> int:
    bg_color = (0, 0, 0, 255)
    x = idx * skip[0]
    if x >= image.get_width():
        return 0
    for y in range(offset, image.get_height(), skip[1]):
        current_color = image.get_at((x, y))
        # If we've reached the bottom of the column in our image
        if current_color == bg_color:
            return (y - offset) // skip[1]
    return image.get_height() // skip[1]

def find_limit8(image: pygame.Surface, idx: int, offset: int = 0) -> int:
    return _find_limit(image, idx, (8, 8), offset)

def find_limit16(image: pygame.Surface, idx: int, offset: int = 0) -> int:
    return _find_limit(image, idx, (16, 16), offset)
