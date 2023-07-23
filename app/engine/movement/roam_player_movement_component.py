from __future__ import annotations

from typing import List, Tuple

from app.data.database.database import DB

from app.engine.game_state import game
from app.engine import action
from app.engine.movement.movement_component import MovementComponent
from app.engine.movement import movement_funcs
from app.utilities import utils

import logging

class RoamPlayerMovementComponent(MovementComponent):
    """
    # Used for moving the player's roaming unit according to the player's inputs
    """
    grid_move = False
    
    min_speed = 0.48  # Unit must have a velocity above this to actually move (tiles per second)
    base_max_speed = 6.0  # maximum speed allowed (tiles per second)
    base_accel = 30.0  # normal acceleration to maximum speed (tiles per second^2)
    running_accel = 36.0  # acceleration to maximum speed while sprinting (tiles per second^2)
    deceleration = 72.0  # deceleration to 0 (tiles per second^2)

    def __init__(self, unit, follow=True, muted=False):
        super().__init__(unit, follow=follow, muted=muted)
        # This is the copy we will work with
        self.position = self.unit.position
        self.sprint = False

        self.start()

    def reset_position(self):
        self.position = self.unit.position

    def set_sprint(self, b: bool):
        self.sprint = b

    def get_camera_position(self) -> Tuple[float, float]:
        return self.position

    def set_acceleration(self, vec: Tuple[float, float]):
        self.x_mag, self.y_mag = vec

    def get_acceleration(self):
        if self.sprint:
            return self.running_accel
        else:
            return self.base_accel

    def get_max_speed(self) -> float:
        if self.sprint:
            max_speed = 1.5 * game.game_vars.get("_roam_speed", 1) * self.base_max_speed
        else:
            max_speed = 1.0 * game.game_vars.get("_roam_speed", 1) * self.base_max_speed
        # Lower speed when walking through difficult terrain
        mcost = movement_funcs.get_mcost(self.unit, self.unit.position)
        max_speed /= mcost
        return max_speed

    def start(self):
        # The unit's position is self.unit.position
        # What the unit's velocity is
        self.x_vel, self.y_vel = 0.0, 0.0
        # What the player is inputting
        self.x_mag, self.y_mag = 0.0, 0.0
        self.active = True

    def finish(self, surprise=False):
        self.unit.sprite.change_state('normal')
        self.unit.sound.stop()
        self.active = False

    def update(self, current_time: int):
        delta_time_ms = (current_time - self._last_update)
        # Never make delta time too large
        delta_time_ms = min(delta_time_ms, utils.frames2ms(4))
        delta_time = delta_time_ms / 1000  # Get delta time in seconds
        self._last_update = current_time

        if not self.active:
            return

        if not self.unit.position:
            logging.error("Unit %s is no longer on the map", self.unit)
            self.active = False
            return

        # === Process inputs ===
        self._kinematics(delta_time)

        # Actually move the unit if it's above the minimum speed
        if utils.magnitude((self.x_vel, self.y_vel)) > self.min_speed:
            self.move(delta_time)
            self.unit.sprite.change_state('moving')
            self.unit.sprite.handle_net_position((self.x_vel, self.y_vel))
            if not self.muted:
                self.unit.sound.play()
        else:
            self.unit.sprite.change_state('normal')
            self.unit.sound.stop()

    def _kinematics(self, delta_time):
        """
        # Updates the velocity of the current unit
        """
        # Modify velocity
        self._accelerate(delta_time, self.x_mag, self.y_mag)

    def _accelerate(self, delta_time, x_mag: float, y_mag: float):
        max_speed: float = self.get_max_speed()
        # Modify velocity
        if x_mag > 0:
            self.x_vel += (self.get_acceleration() * delta_time)
        elif x_mag < 0:
            self.x_vel -= (self.get_acceleration() * delta_time)
        else:
            if self.x_vel > 0:
                self.x_vel -= (self.deceleration * delta_time)
                self.x_vel = max(0, self.x_vel)
            elif self.x_vel < 0:
                self.x_vel += (self.deceleration * delta_time)
                self.x_vel = min(0, self.x_vel)
        self.x_vel = utils.clamp(self.x_vel, -max_speed, max_speed)

        if y_mag > 0:
            self.y_vel += (self.get_acceleration() * delta_time)
        elif y_mag < 0:
            self.y_vel -= (self.get_acceleration() * delta_time)
        else:
            if self.y_vel > 0:
                self.y_vel -= (self.deceleration * delta_time)
                self.y_vel = max(0, self.y_vel)
            elif self.y_vel < 0:
                self.y_vel += (self.deceleration * delta_time)
                self.y_vel = min(0, self.y_vel)
        self.y_vel = utils.clamp(self.y_vel, -max_speed, max_speed)
        # Diagonal movement shouldn't be faster than single-axis
        full_mag = utils.magnitude((self.x_vel, self.y_vel))
        if full_mag > max_speed:
            self.x_vel *= max_speed / full_mag
            self.y_vel *= max_speed / full_mag

    def _can_move(self, pos: Tuple[int, int]) -> bool:
        traversable = movement_funcs.check_traversable(self.unit, pos)
        if not traversable:
            return False
        if game.board.get_unit(pos):
            other_team = game.board.get_team(pos)
            if not other_team or self.unit.team in DB.teams.get_allies(other_team):
                return True # Allies, this is fine
            else:  # Enemies
                return False
        # If diagonal, also check the diagonal spots
        if pos[0] != self.unit.position[0] and pos[1] != self.unit.position[1]:
            pos_h = (pos[0], self.unit.position[1])
            pos_v = (self.unit.position[0], pos[1])
            # Check that not both are impassable
            if not self._can_move(pos_h) and not self._can_move(pos_v):
                return False
        return True

    def move(self, delta_time):
        x, y = self.position
        dx = self.x_vel * delta_time
        dy = self.y_vel * delta_time
        next_position = (x + dx, y + dy)
        alt_position_h = (x + dx, y)
        alt_position_v = (x, y + dy)

        rounded_pos = utils.round_pos(next_position)
        rounded_pos_h = utils.round_pos(alt_position_h)
        rounded_pos_v = utils.round_pos(alt_position_v)
        # Can always move within current position
        if rounded_pos == self.unit.position or self._can_move(rounded_pos):
            self.position = next_position
        # Try to move to a valid position just horizontally
        elif self._can_move(rounded_pos_h):
            self.position = alt_position_h
            rounded_pos = rounded_pos_h
        # Try to move to a valid position just vertically
        elif self._can_move(rounded_pos_v):
            self.position = alt_position_v
            rounded_pos = rounded_pos_v
        else:
            return

        # Assign the position to the sprite
        self.unit.sprite.set_roam_position(self.position)

        # Move the unit's true position if necessary
        if rounded_pos != self.unit.position:
            game.leave(self.unit)
            self.unit.position = rounded_pos
            game.arrive(self.unit)
            action.UpdateFogOfWar(self.unit).do()
