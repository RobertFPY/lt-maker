import logging

from app.engine.game_state import game
from app.engine.state import State

from app.events.mock_event import MockEvent

class MockEventState(State):
    name = 'mock_event'
    transparent = True
    event: MockEvent = None

    def begin(self):
        logging.debug("Begin Mock Event State")
        if not self.event:
            if game.memory.get('mock_events'):
                self.event = game.memory['mock_events'].pop()
            else:
                self.event = None
            if self.event and game.cursor:
                game.cursor.hide()

    def take_input(self, event):
        if self.event:
            self.event.take_input(event)

    def update(self):
        if self.event:
            self.event.update()
        else:
            logging.debug("Event complete")
            game.memory.pop('mock_events')
            game.state.back()
            return 'repeat'

        if self.event.state == 'paused':
            return 'repeat'

        elif self.event.state == 'complete':
            return self.end_event()

    def draw(self, surf):
        if self.event:
            self.event.draw(surf)
        return surf

    def end_event(self):
        logging.debug("Ending Mock Event")
        game.state.back()

        return 'repeat'
