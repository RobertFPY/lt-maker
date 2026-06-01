from __future__ import annotations

"""
Event tutorial overlay boxes.

These small overlay objects let an event point an animated hand at, and/or draw
a pulsing highlight around, an arbitrary rectangle on screen. They reuse the
exact look of ``SkillTutorial._draw_hand`` / ``SkillTutorial._draw_highlight``
(see ``app/engine/info_menu/skill_tutorial.py``).

They are designed to be appended to ``Event.other_boxes`` so they update/draw
alongside the rest of the event UI. Each overlay is drawn immediately when its
command runs and supports three lifetimes:

* ``persist=True``: standalone. It keeps drawing on its own (even with no
  ``speak``/``say`` following it) until it is removed manually with the
  ``remove_overlay`` command.
* ``end_after=1`` (default): it removes itself automatically when the very next
  ``speak``/``say`` text box that appears after it finishes. This reproduces the
  original "show with the speak box and vanish with it" behaviour.
* ``end_after=N``: it removes itself when the *N*-th ``speak``/``say`` text box
  after it finishes (e.g. ``end_after=3`` keeps it on screen across the next
  three speak boxes and removes it once the third one is gone).
"""

import math

import pygame

from app.engine import engine
from app.engine.sprites import SPRITES
from app.engine.game_menus.menu_components.generic_menu.cursor_hand import CursorHand


class EventTutorialOverlay:
    """Hand and/or highlight overlay drawn over the event.

    ``rect`` is an ``(x, y, w, h)`` rectangle in screen pixels.

    The overlay is visible the moment it is created. Its lifetime depends on the
    ``persist`` / ``end_after`` arguments (see the module docstring): it either
    persists until removed manually, or it removes itself once the ``end_after``-th
    ``speak``/``say`` text box that appears after it has finished.
    """

    HIGHLIGHT_COLOR = (248, 224, 96)

    # The base ``menu_hand`` sprite points to the right. To make it point in
    # another direction we rotate it counter-clockwise by this many degrees.
    _ROTATION = {
        'right': 0,
        'up': 90,
        'left': 180,
        'down': 270,
    }

    def __init__(self, event, rect, show_hand=True, show_highlight=True,
                 color=None, direction='right', persist=False, end_after=1):
        self.event = event
        self.rect = rect  # (x, y, w, h) in screen-space pixels
        self.show_hand = show_hand
        self.show_highlight = show_highlight
        self.color = color or self.HIGHLIGHT_COLOR
        self.direction = direction if direction in self._ROTATION else 'right'

        self.cursor_hand = CursorHand()
        self.hand_sprite = SPRITES.get('menu_hand')

        # Lifetime control (see module docstring):
        #  - persist=True: drawn until removed manually via remove_overlay.
        #  - otherwise: removed once the `end_after`-th speak/say box that
        #    appears after this overlay has finished (1 = the very next one).
        self.persist = persist
        try:
            self.end_after = max(1, int(end_after))
        except (TypeError, ValueError):
            self.end_after = 1
        self._seen_boxes = []  # distinct speak boxes counted so far
        self._bound_box = None

    def update(self) -> bool:
        """Return True to stay in ``Event.other_boxes``, False to be removed."""
        self.cursor_hand.update()
        if self.persist:
            return True  # Standalone: stays until removed manually.
        if self._bound_box is None:
            # Count each new speak/say box as it appears; bind to the Nth one.
            top = self.event.text_boxes[-1] if self.event.text_boxes else None
            if top is not None and not top.is_complete() \
                    and not any(top is b for b in self._seen_boxes):
                self._seen_boxes.append(top)
                if len(self._seen_boxes) >= self.end_after:
                    self._bound_box = top
            return True  # Stay visible while waiting to reach the Nth box.
        # Bound: live only as long as our target dialog box is still on screen.
        return self._bound_box in self.event.text_boxes

    def draw(self, surf):
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
        gap = 2
        # Animated "bob" amount toward the target (reuses CursorHand's wave).
        bob = self.cursor_hand.get_offset()

        sprite = self.hand_sprite
        angle = self._ROTATION[self.direction]
        if angle:
            sprite = pygame.transform.rotate(sprite, angle)
        sw, sh = sprite.get_width(), sprite.get_height()

        # All directions point the finger tip at a single anchor: the exact
        # (x, y) coordinate that was passed to the command. Switching direction
        # only rotates the hand about that point instead of flinging it to a
        # far-away edge, and the tip always lands on the coordinate the user
        # asked for (size does not shift the anchor).
        anchor_x = x
        anchor_y = y + h / 2

        # (pointing unit vector, finger-tip position within the rotated sprite)
        dx, dy, tip_x, tip_y = {
            'right': (1, 0, sw, sh / 2),
            'left': (-1, 0, 0, sh / 2),
            'up': (0, -1, sw / 2, 0),
            'down': (0, 1, sw / 2, sh),
        }[self.direction]

        # Finger tip sits `gap` away from the anchor and bobs toward it.
        tip_global_x = anchor_x + dx * (bob - gap)
        tip_global_y = anchor_y + dy * (bob - gap)
        hand_x = tip_global_x - tip_x
        hand_y = tip_global_y - tip_y
        engine.blit(surf, sprite, (int(round(hand_x)), int(round(hand_y))))

        engine.blit(surf, sprite, (int(hand_x), int(hand_y)))