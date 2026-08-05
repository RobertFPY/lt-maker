from __future__ import annotations
from typing import ClassVar
from app.constants import TILEHEIGHT, TILEWIDTH, WINHEIGHT, WINWIDTH
from app.engine.fluid_scroll import FluidScroll
from app.engine.game_state import game

class State():
    name: ClassVar[str] = None
    in_level = True
    show_map = True
    transparent = False
    blocks_fast_forward = False

    started = False
    processed = False

    def __init__(self, name=None):
        self.name = name

    def start(self):
        """
        Called when state is first loaded
        """
        pass

    def begin(self):
        """
        Called whenever state begins being top of state stack
        """
        pass

    def take_input(self, event):
        pass

    def update(self):
        pass

    def update_visuals(self):
        """Advance simulation-timed visuals for this visible state.

        Fast-forward can run several updates while rendering only the final
        surface.  Time-dependent visual state belongs here rather than in
        ``draw`` so visible underlays stay synchronized with the game clock.
        """
        pass

    def should_defer_render(self) -> bool:
        """Whether this state must retain the last presented surface this step.

        Updates and lifecycle commits still run.  This is only for an atomic
        visual mutation that cannot be shown until its event command batch has
        reached a present-safe boundary.
        """
        return False

    def draw(self, surf):
        return surf

    def end(self):
        pass

    def finish(self):
        pass

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: State) -> bool:
        return self.name == other.name

class MapState(State):
    def __init__(self, name=None):
        if name:
            self.name = name
        self.fluid = FluidScroll()

    def update(self):
        pass

    def update_visuals(self):
        # Android's staged save restore can expose a saved MapState for one
        # frame before its level/overworld tilemap has been rebuilt.  Camera
        # bounds and MapView animation updates require a real tilemap; the
        # highlight clock remains safe to advance during that boundary.
        if game.camera and game.tilemap:
            game.camera.update()
        if game.highlight:
            game.highlight.update()
        if game.map_view and game.tilemap:
            game.map_view.update_visuals()

    def draw(self, surf, culled_rect=None):
        camera_cull = int(game.camera.get_x() * TILEWIDTH), int(game.camera.get_y() * TILEHEIGHT), WINWIDTH, WINHEIGHT
        map_surf = game.map_view.draw(camera_cull, culled_rect)
        surf.blit(map_surf, (0, 0))
        return surf
