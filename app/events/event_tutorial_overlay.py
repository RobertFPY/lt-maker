from __future__ import annotations

"""
Event tutorial overlay boxes.

These small overlay objects let an event point an animated hand at, and/or draw
a pulsing highlight around, an arbitrary rectangle on screen. They reuse the
exact look of ``SkillTutorial._draw_hand`` / ``SkillTutorial._draw_highlight``
(see ``app/engine/info_menu/skill_tutorial.py``).

They are designed to be appended to ``Event.other_boxes`` so they update/draw
alongside the rest of the event UI. Crucially, each overlay binds itself to the
*dialog box* produced by a ``speak``/``say`` command: it only becomes visible
once that text box is on screen, and it removes itself automatically the moment
that text box disappears. This makes the two new event commands (``draw_hand``
and ``draw_highlight``) show up together with their accompanying speak box and
vanish with it.
"""

import math

import pygame

from app.engine import engine
from app.engine.sprites import SPRITES
from app.engine.game_menus.menu_components.generic_menu.cursor_hand import CursorHand


class EventTutorialOverlay:
    """Hand and/or highlight overlay tied to the lifetime of a dialog box.

    ``rect`` is an ``(x, y, w, h)`` rectangle in screen pixels.

    The overlay binds to the most recent, still-active dialog box. If no such
    box exists yet (the common case: ``draw_hand`` is written *before* the
    ``speak`` it accompanies), the overlay waits, invisible, until the next
    ``speak``/``say`` creates one. Once bound, it stays alive only while that
    dialog box is still present in ``event.text_boxes`` and removes itself
    afterwards.
    """

    HIGHLIGHT_COLOR = (248, 224, 96)

    def __init__(self, event, rect, show_hand=True, show_highlight=True, color=None):
        self.event = event
        self.rect = rect  # (x, y, w, h) in screen-space pixels
        self.show_hand = show_hand
        self.show_highlight = show_highlight
        self.color = color or self.HIGHLIGHT_COLOR

        self.cursor_hand = CursorHand()
        self.hand_sprite = SPRITES.get('menu_hand')

        # Bind to a dialog box so we appear and disappear together with it.
        top = event.text_boxes[-1] if event.text_boxes else None
        if top is not None and not top.is_complete():
            self._bound_box = top
            self._waiting = False
        else:
            self._bound_box = None
            self._waiting = True

    @property
    def _visible(self) -> bool:
        # Only draw once we are actually tied to a live dialog box, so the
        # hand/highlight pops in at the same time as the speak box.
        return not self._waiting

    def update(self) -> bool:
        """Return True to stay in ``Event.other_boxes``, False to be removed."""
        self.cursor_hand.update()
        if self._waiting:
            top = self.event.text_boxes[-1] if self.event.text_boxes else None
            if top is not None and not top.is_complete():
                self._bound_box = top
                self._waiting = False
            return True  # Keep waiting for the speak/say box to appear.
        # Bound: live only as long as our dialog box is still on screen.
        return self._bound_box in self.event.text_boxes

    def draw(self, surf):
        if not self._visible:
            return surf
        pulse = (math.sin(engine.get_time() / 160.0) + 1) / 2  # 0..1
        if self.show_highlight:
            self._draw_highlight(surf, self.rect, pulse)
        if self.show_hand:
            self._draw_hand(surf, self.rect)
        return surf

    # -- drawing (mirrors SkillTutorial) -----------------------------------

    def _draw_highlight(self, surf, rect, pulse):
        x, y, w, h = rect
        pad = 2
        thickness = 1 + int(round(pulse))  # 1..2 px pulsing border
        box = (x - pad, y - pad, w + pad * 2, h + pad * 2)
        pygame.draw.rect(surf, self.color, box, width=thickness,
                         border_radius=(h + pad * 2) // 2)

    def _draw_hand(self, surf, rect):
        x, y, w, h = rect
        hand_w = self.hand_sprite.get_width()
        hand_h = self.hand_sprite.get_height()
        hand_x = max(0, x - hand_w - 2)
        hand_y = y + (h - hand_h) // 2
        self.cursor_hand.draw(surf, (hand_x, hand_y))
