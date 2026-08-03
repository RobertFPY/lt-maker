"""Safe, queued transitions from an active map back to the game title."""

from __future__ import annotations


def queue_return_to_title(game, direct_to_title_main: bool = False) -> None:
    """Discard active map UI and queue a fresh title-screen state.

    This deliberately uses the state machine queue.  Calling ``clear`` while
    an option child is handling input would otherwise end that child midway
    through its own method.
    """
    from app.engine.runtime_debugger_controller import get_controller

    get_controller().reset_runtime_state()
    game.memory.clear()
    if direct_to_title_main:
        game.memory['_return_directly_to_title_menu'] = True
    game.state.clear()
    game.state.change('title_start')
