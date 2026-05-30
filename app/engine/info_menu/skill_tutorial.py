from __future__ import annotations

"""
Skill System Tutorial overlay.

This module draws the "Tale of the Golden Knight's Skill System Tutorial" on top
of the unit info menu's skill (notes) page. It dims the page, points an animated
hand at the relevant skill pill(s), and shows an explanatory, paged text box.

There are TWO independent ways this tutorial can start. They are intentionally
kept separate so they are easy to tell apart and enable/disable individually:

1. AUTO trigger (this file): plays automatically the first time the player
   scrolls to the skill page. Guarded by the ``SEEN_VAR`` game var so it only
   ever happens once per save. Toggle it globally with ``AUTO_TUTORIAL_ENABLED``.

2. FORCED trigger (event command): the ``force_skill_tutorial`` event command
   opens the info menu straight onto the skill page and plays the tutorial on
   demand (FE7 "Lyn mode" style). It ignores ``SEEN_VAR`` and always plays.

Both paths ultimately construct and drive a single :class:`SkillTutorial` object
that lives inside ``InfoMenuState``.
"""

import math

from app.constants import WINWIDTH, WINHEIGHT
from app.engine import base_surf, engine, image_mods
from app.engine.fluid_scroll import FluidScroll
from app.engine.game_menus.menu_components.generic_menu.cursor_hand import CursorHand
from app.engine.graphics.text.text_renderer import font_height, render_text
from app.engine.sound import get_sound_thread
from app.engine.sprites import SPRITES
from app.engine import text_funcs
from app.utilities.enums import HAlignment

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Set to False to completely disable the automatic first-visit tutorial.
# (The forced event command still works regardless of this flag.)
AUTO_TUTORIAL_ENABLED = True

# Game var used to remember that the player has already seen the auto tutorial.
SEEN_VAR = '_skill_tutorial_seen'

FONT = 'convo'
PANEL_FONT_COLOR = 'white'

# ---------------------------------------------------------------------------
# Pill geometry (mirrors create_notes_surf, which is blitted at x = 96)
# ---------------------------------------------------------------------------

_NOTES_BLIT_X = 96
_PILL_X = 4
_PILL_W = (WINWIDTH - 96) - 8  # 136 px
_PILL_H = 18
_PILL_START_Y = 14
_PILL_GAP = 2

# Skill pill row indices on the page.
ROW_PERSONAL = 0
ROW_CLASS = 1
ROW_SPECIAL = 2
ROW_SLOTA = 3
ROW_SLOTB = 4
ROW_SLOTC = 5
ROW_EXTRA = 6

# The Costume Item slot lives in the left portrait panel (see
# create_portrait_section -> the accessory option is drawn at (5, 81)).
COSTUME_RECT = (5, 81, 120, 16)


def _pill_rect(idx: int):
    """Screen-space rect of skill pill row ``idx``."""
    y = _PILL_START_Y + idx * (_PILL_H + _PILL_GAP)
    return (_NOTES_BLIT_X + _PILL_X, y, _PILL_W, _PILL_H)


class _Step:
    """A single tutorial page group: some text + the rect(s) it points at."""

    def __init__(self, text: str, targets):
        self.text = text
        self.targets = targets or []  # list of (x, y, w, h) screen rects


def _build_steps() -> list:
    """Build the ordered list of tutorial steps from the provided script."""
    return [
        _Step(
            "This is \"Tale of the Golden Knight's Skill System Tutorial\". "
            "In this game, each unit, including a character with an identity or "
            "a generic unit, can have a total of seven slots of skill to be equipped.",
            [],
        ),
        _Step(
            "This is the Character Skill, the kind of skill that is unique and "
            "belongs to one and only one character. It can't be removed and can "
            "be upgraded throughout the game, as the character's story progresses.",
            [_pill_rect(ROW_PERSONAL)],
        ),
        _Step(
            "This is the Class Skill, the kind of skill that is unique and "
            "belongs to one single class. It can't be removed and only changes "
            "whenever the unit changes class through promotion.",
            [_pill_rect(ROW_CLASS)],
        ),
        _Step(
            "This is the Special Skill, the kind of skill that requires a certain "
            "condition to be activated in combat. It can be removed and replaced "
            "with another Special Skill. A Special Skill is rewarded whenever a "
            "unit reaches level 5 of the current class. Changing class and "
            "reaching another level 5 can acquire another Special Skill.",
            [_pill_rect(ROW_SPECIAL)],
        ),
        _Step(
            "These are the Passive Skills, the kind of skill that provides a "
            "special effect in or out of combat. A Passive Skill can be removed "
            "and replaced with another Passive Skill of the same slot. A Passive "
            "Skill is rewarded whenever a unit reaches level 3 of the current "
            "class. Changing class and reaching another level 3 can acquire "
            "another Passive Skill.",
            [_pill_rect(ROW_SLOTA), _pill_rect(ROW_SLOTB), _pill_rect(ROW_SLOTC)],
        ),
        _Step(
            "This is the Extra Skill, the kind of skill that can only be acquired "
            "by equipping a weapon or item that provides an Extra Skill. It is "
            "removed automatically when the weapon or item that provided it is "
            "unequipped.",
            [_pill_rect(ROW_EXTRA)],
        ),
        _Step(
            "This is the Costume Item, a special item that provides some extra "
            "effect, buff or ability for the character currently equipping it. A "
            "Costume Item can not be stolen by any means and can be removed or "
            "equipped during the battle preparation screen. A Costume Item will "
            "be dropped upon death and stored in the convoy automatically.",
            [COSTUME_RECT],
        ),
    ]


class SkillTutorial:
    """Driver/overlay for the skill-system tutorial.

    The owning state should:
      * call :meth:`take_input` while the tutorial ``is_active``;
      * call :meth:`update` every frame;
      * call :meth:`draw` last so the overlay sits on top of the page.
    """

    LINES_PER_PAGE = 4
    PANEL_WIDTH = WINWIDTH - 16  # 224
    HIGHLIGHT_COLOR = (248, 224, 96)

    def __init__(self):
        self.steps = _build_steps()
        self.fluid = FluidScroll(200, 1)
        self.cursor_hand = CursorHand()
        self.hand_sprite = SPRITES.get('menu_hand')

        self.fh = font_height(FONT)
        self.panel_text_width = self.PANEL_WIDTH - 16

        # Flatten steps into (step, page_lines) pages for sequential navigation.
        self.pages = []  # list of (step, [lines])
        for step in self.steps:
            lines = text_funcs.line_wrap(FONT, step.text, self.panel_text_width)
            for i in range(0, len(lines), self.LINES_PER_PAGE):
                self.pages.append((step, lines[i:i + self.LINES_PER_PAGE]))

        self.page_index = 0
        self._finished = False

    @property
    def is_active(self) -> bool:
        return not self._finished

    def _current(self):
        return self.pages[self.page_index]

    def next_page(self):
        if self.page_index < len(self.pages) - 1:
            self.page_index += 1
            get_sound_thread().play_sfx('Select 1')
        else:
            self.finish()

    def prev_page(self):
        if self.page_index > 0:
            self.page_index -= 1
            get_sound_thread().play_sfx('Select 4')

    def finish(self):
        if not self._finished:
            self._finished = True
            get_sound_thread().play_sfx('Select 4')

    def take_input(self, event):
        self.fluid.update()
        directions = self.fluid.get_directions()

        if event in ('SELECT', 'RIGHT'):
            self.next_page()
            return
        elif event in ('BACK', 'LEFT'):
            self.prev_page()
            return
        elif event in ('AUX', 'INFO', 'START'):
            # Skip the whole tutorial.
            self.finish()
            return

        if 'RIGHT' in directions:
            self.next_page()
        elif 'LEFT' in directions:
            self.prev_page()

    def update(self):
        self.cursor_hand.update()

    # -- drawing -----------------------------------------------------------

    def _panel_at_bottom(self, step: _Step) -> bool:
        """Place the text panel away from the rows being pointed at."""
        if not step.targets:
            return True
        avg_y = sum(r[1] + r[3] / 2 for r in step.targets) / len(step.targets)
        return avg_y < WINHEIGHT / 2

    def draw(self, surf):
        step, lines = self._current()

        # 1. Dim the whole page so the tutorial reads clearly.
        dim = engine.create_surface((WINWIDTH, WINHEIGHT))
        dim.fill((0, 0, 0))
        dim = image_mods.make_translucent(dim, 0.45)
        surf.blit(dim, (0, 0))

        # 2. Highlight + point at each target rect.
        pulse = (math.sin(engine.get_time() / 160.0) + 1) / 2  # 0..1
        for rect in step.targets:
            self._draw_highlight(surf, rect, pulse)
            self._draw_hand(surf, rect)

        # 3. Draw the text panel.
        self._draw_panel(surf, step, lines)

        return surf

    def _draw_highlight(self, surf, rect, pulse):
        import pygame
        x, y, w, h = rect
        pad = 2
        thickness = 1 + int(round(pulse))  # 1..2 px pulsing border
        box = (x - pad, y - pad, w + pad * 2, h + pad * 2)
        pygame.draw.rect(surf, self.HIGHLIGHT_COLOR, box, width=thickness,
                         border_radius=(h + pad * 2) // 2)

    def _draw_hand(self, surf, rect):
        x, y, w, h = rect
        hand_w = self.hand_sprite.get_width()
        hand_h = self.hand_sprite.get_height()
        hand_x = max(0, x - hand_w - 2)
        hand_y = y + (h - hand_h) // 2
        self.cursor_hand.draw(surf, (hand_x, hand_y))

    def _draw_panel(self, surf, step: _Step, lines):
        panel_h = self.LINES_PER_PAGE * self.fh + 12
        panel = base_surf.create_base_surf(self.PANEL_WIDTH, panel_h, 'menu_bg_base')

        for idx, line in enumerate(lines):
            render_text(panel, [FONT], [line], [PANEL_FONT_COLOR], (8, 4 + idx * self.fh))

        # Page indicator + continue prompt on the last line of the panel.
        prompt = '%d/%d' % (self.page_index + 1, len(self.pages))
        render_text(panel, ['small'], [prompt], ['yellow'],
                    (self.PANEL_WIDTH - 6, panel_h - 13), HAlignment.RIGHT)

        panel_x = 8
        if self._panel_at_bottom(step):
            panel_y = WINHEIGHT - panel_h - 6
        else:
            panel_y = 6
        surf.blit(panel, (panel_x, panel_y))
