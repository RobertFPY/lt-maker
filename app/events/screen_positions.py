from __future__ import annotations
from typing import Tuple
from app.constants import WINHEIGHT, WINWIDTH
from app.utilities.typing import Point

horizontal_screen_positions = {'OffscreenLeft': -96,
                               'FarLeft': -24,
                               'LeftCorner': -16,
                               'Left': 0,
                               'MidLeft': 24,
                               'CenterLeft': 24,
                               'CenterRight': WINWIDTH - 120,
                               'MidRight': WINWIDTH - 120,
                               'LevelUpRight': WINWIDTH - 100,
                               'Right': WINWIDTH - 96,
                               'RightCorner': WINWIDTH - 80,
                               'FarRight': WINWIDTH - 72,
                               'OffscreenRight': WINWIDTH}

vertical_screen_positions = {'Top': 0,
                             'Middle': (WINHEIGHT - 80) // 2,
                             'Bottom': WINHEIGHT - 80}

def parse_screen_position(pos: Tuple | str, portrait_size: Tuple[int, int] = (96, 80)) -> Tuple[Point, bool]:
    """Returns a tuple of Point (on screen) and bool (indicating if the portrait should be mirrored)"""
    true_ver_screen_pos =  {'Top': 0,
                            'Middle': (WINHEIGHT - portrait_size[1]) // 2,
                            'Bottom':  WINHEIGHT - portrait_size[1]}

    # Only `LevelUpRight` is relative to the right, other horiz are relative to the left
    true_hor_screen_pos = horizontal_screen_positions | {'LevelUpRight': WINWIDTH - portrait_size[0] - 4}

    if not isinstance(pos, tuple):
        pos = (pos,)
    def resolve_pos(p: int | str, horiz=True) -> int:
        if isinstance(p, int):
            return p
        else:
            if horiz:
                return true_hor_screen_pos.get(p, 0)
            else:
                return true_ver_screen_pos.get(p, 0)
    position = (0, 0)

    if len(pos) == 2:
        position = resolve_pos(pos[0]), resolve_pos(pos[1], False)
    else:
        pos = pos[0]
        if isinstance(pos, int) or pos in true_hor_screen_pos:
            position = resolve_pos(pos), true_ver_screen_pos['Bottom']
        else:
            position = true_hor_screen_pos['Left'], resolve_pos(pos, False)
    return position, position[0] <= true_hor_screen_pos['CenterLeft']


def get_desired_center(x: int) -> int:
    if x < 48:  # FarLeft
        return 8
    elif x < 72:  # Left
        return 80
    elif x < 104:  # MidLeft
        return 104
    elif x > WINWIDTH - 48:  # FarRight
        return WINWIDTH - 8
    elif x > WINWIDTH - 72:  # Right
        return WINWIDTH - 88
    elif x > WINWIDTH - 144:  # MidRight
        return WINWIDTH - 112
    else:
        return WINWIDTH//2
