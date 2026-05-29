from __future__ import annotations
from app.utilities.algorithms.interpolation import tcubic_easing, tlerp

import math
from typing import TYPE_CHECKING, Callable, Optional, Tuple, List

from app.constants import TILEX, TILEY, TILEWIDTH, TILEHEIGHT
from app.engine import engine
from app.utilities import utils

if TYPE_CHECKING:
    from app.engine.game_state import GameState

class Camera():
    def __init__(self, game: GameState):
        self.game = game

        # Where the camera is going
        self.target_x = 0
        self.target_y = 0
        # Where the camera actually is
        self.current_x = 0
        self.current_y = 0

        # How fast the camera should move
        self.speed = 8.0  # Linear speed based on distance from target

        # Whether the camera should be panning at a constant speed
        self.pan_mode = False
        self.pan_speed = 0.125
        self.pan_targets = []

        # if we want to set a custom algorithm for the camera movement
        # custom algorithms should take in original_position, new_position, and current_time
        self.pan_algorithm: Callable[[float, float, int], Tuple[float, float]] = None

        self.last_at_rest_time: int = engine.get_time()
        self.last_at_rest_position: Tuple[float, float] = (self.current_x, self.current_y)

        # ----- Continuous multi-waypoint smooth path -----
        # Driven entirely by elapsed time. Movement is computed from a list of
        # clamped waypoints with a single ease curve (or linear) applied to the
        # whole journey, so there is no "hitch" at intermediate waypoints.
        self.path_mode: bool = False
        self.path_waypoints: List[Tuple[float, float]] = []
        self.path_segment_lengths: List[float] = []
        self.path_total_dist: float = 0.0
        self.path_start_time: int = 0
        self.path_duration: int = 0
        self.path_ease: bool = True
        self.path_ramp_frac: float = 0.15
        self.path_curved: bool = False
        # When True, lets MoveCameraState (or anyone else) request an early end.
        self.path_allow_skip: bool = False
        self._path_skip_requested: bool = False
        # Optional callable run exactly once when the active path ends (whether
        # naturally or via skip). Used by event commands to restore cursor /
        # fade music back without coupling those concerns into the camera.
        self.path_on_end: Optional[Callable[[], None]] = None

        # For screenshake
        self.no_shake = [(0, 0)]
        self.shake = self.no_shake
        self.shake_idx = 0
        self.shake_end_at = 0

    def get_next_position(self) -> Tuple[float, float]:
        if self.path_mode:
            return self._path_position()
        diff_x = self.target_x - self.current_x
        diff_y = self.target_y - self.current_y

        diff_time = engine.get_time() - self.last_at_rest_time
        if self.pan_algorithm:
            return self.pan_algorithm(self.last_at_rest_position, (self.target_x, self.target_y), diff_time)
        elif self.pan_mode:
            new_x = self.pan_speed * utils.sign(diff_x) + self.current_x
            new_y = self.pan_speed * utils.sign(diff_y) + self.current_y
            return (new_x, new_y)
        elif diff_x or diff_y:
            dist = utils.distance((self.current_x, self.current_y), (self.target_x, self.target_y))
            total_speed = utils.clamp(dist / self.speed, min(dist, 0.25), 1.0)  # max of 0.5 is faithful to GBA, but I like the snappyness of 1.0
            angle = math.atan2(abs(diff_y), abs(diff_x))
            x_push = math.cos(angle)
            y_push = math.sin(angle)
            new_x = total_speed * x_push * utils.sign(diff_x) + self.current_x
            new_y = total_speed * y_push * utils.sign(diff_y) + self.current_y
            return (new_x, new_y)
        else:
            return (self.current_x, self.current_y)

    def _shift_x(self, x):
        if x <= self.target_x + 2:
            self.target_x -= 1
        elif x >= (TILEX + self.target_x - 3):
            self.target_x += 1

    def _shift_y(self, y):
        if y <= self.target_y + 1:
            self.target_y -= 1
        elif y >= (TILEY + self.target_y - 2):
            self.target_y += 1

    def cursor_x(self, x):
        self._shift_x(x)

    def cursor_y(self, y):
        self._shift_y(y)

    def mouse_x(self, x):
        self._shift_x(x)

    def mouse_y(self, y):
        self._shift_y(y)

    def mouse_xy(self, x, y):
        """
        Gives mouse position
        """
        self.mouse_x(x)
        self.mouse_y(y)

    def _change_x(self, x):
        if x <= self.target_x + 3:
            new_x = x - 3
        elif x >= self.target_x + TILEX - 3:
            new_x = x - TILEX + 3
        else:
            new_x = self.target_x
        return new_x

    def _change_y(self, y):
        if y <= self.target_y + 3:
            new_y = y - 3
        elif y >= self.target_y + TILEY - 3:
            new_y = y - TILEY + 3
        else:
            new_y = self.target_y
        return new_y

    def _center_x(self, x):
        return utils.clamp(x - TILEX//2, 0, self.game.tilemap.width - TILEX)

    def _center_y(self, y):
        return utils.clamp(y - TILEY//2, 0, self.game.tilemap.height - TILEY)

    def set_xy(self, x, y):
        x = self._change_x(x)
        self.target_x = x
        y = self._change_y(y)
        self.target_y = y

    def force_xy(self, x, y):
        x = self._change_x(x)
        self.current_x = self.target_x = x
        y = self._change_y(y)
        self.current_y = self.target_y = y

    def set_center(self, x, y):
        x = self._center_x(x)
        self.target_x = x
        y = self._center_y(y)
        self.target_y = y

    def force_center(self, x, y):
        x = self._center_x(x)
        self.current_x = self.target_x = x
        y = self._center_y(y)
        self.current_y = self.target_y = y

    def set_center2(self, pos1, pos2):
        x1, y1 = pos1
        x2, y2 = pos2
        mid_x = (x1 + x2) // 2
        mid_y = (y1 + y2) // 2
        self.set_center(mid_x, mid_y)

    def get_x(self):
        """
        Returns the current x position of the camera. Normalizes to pixel proportion, e.g. if a tile is 16 pixels, can only return floats equal to 0/16, 1/16, 2/16, etc.
        """
        return int(self.current_x * TILEWIDTH) / TILEWIDTH

    def get_y(self):
        """
        Returns the current y position of the camera. Normalizes to pixel proportion, e.g. if a tile is 16 pixels, can only return floats equal to 0/16, 1/16, 2/16, etc.
        """
        return int(self.current_y * TILEHEIGHT) / TILEHEIGHT

    def get_xy(self):
        return self.get_x(), self.get_y()

    def get_shake(self):
        return self.shake[self.shake_idx]

    def at_rest(self):
        if self.path_mode:
            return False
        return self.current_x == self.target_x and self.current_y == self.target_y

    def set_target_limits(self, tilemap):
        if self.target_x < 0:
            self.target_x = 0
        elif self.target_x > tilemap.width - TILEX:
            self.target_x = max(0, tilemap.width - TILEX)
        if self.target_y < 0:
            self.target_y = 0
        elif self.target_y > tilemap.height - TILEY:
            self.target_y = max(0, tilemap.height - TILEY)

    def set_current_limits(self, tilemap):
        if self.current_x < 0:
            self.current_x = 0
        elif self.current_x > tilemap.width - TILEX:
            self.current_x = max(0, tilemap.width - TILEX)
        if self.current_y < 0:
            self.current_y = 0
        elif self.current_y > tilemap.height - TILEY:
            self.current_y = max(0, tilemap.height - TILEY)

    def do_slow_pan(self, duration):
        # queues up a slower algorithm for the next pan
        self.pan_algorithm = lambda a, b, t: tcubic_easing(a, b, t/duration)

    def do_linear_pan(self, duration):
        # Constant-speed pan algorithm. Useful for chaining several move_cursor
        # commands without an ease-out/ease-in "hitch" at every waypoint.
        self.pan_algorithm = lambda a, b, t: tlerp(a, b, t/duration)

    # -------------------- Continuous smooth path --------------------

    def start_smooth_path(self, waypoints: List[Tuple[float, float]], duration: int,
                          ease: bool = True, curved: bool = False, allow_skip: bool = False,
                          ramp_frac: float = 0.15):
        """
        Begin a continuous multi-waypoint pan. The camera will travel through
        every waypoint without stopping. Time is distributed by *arc length*
        across linear segments (or the spline arc when curved=True), so a
        constant t maps to a constant distance and the motion is uniform.

        Args:
            waypoints: list of (tile_x, tile_y) targets, in order.
            duration: total travel time in milliseconds.
            ease: if True, use a trapezoidal velocity profile (smooth ramp-up,
                  constant cruise, smooth ramp-down). If False, linear timing.
            curved: if True, smooth the path with a Catmull-Rom spline so the
                    camera bows gently around corners instead of bending sharply.
            allow_skip: if True, MoveCameraState will end the path early when
                        START is pressed.
            ramp_frac: fraction of total time spent ramping up *and* ramping
                       down (each). 0.15 means 15% accelerate + 70% cruise +
                       15% decelerate. Smaller -> snappier, larger -> softer.
        """
        if not waypoints or duration <= 0:
            return

        # Convert each waypoint into a clamped camera-target position, the same
        # way move_cursor would have placed it, so the path stays valid.
        anchored: List[Tuple[float, float]] = [(self.current_x, self.current_y)]
        saved_tx, saved_ty = self.target_x, self.target_y
        self.target_x, self.target_y = self.current_x, self.current_y
        for (wx, wy) in waypoints:
            cx = self._change_x(wx)
            cy = self._change_y(wy)
            self.target_x, self.target_y = cx, cy
            anchored.append((cx, cy))
        self.target_x, self.target_y = saved_tx, saved_ty

        # De-duplicate consecutive identical points (zero-length segments break
        # arc-length parameterization).
        deduped: List[Tuple[float, float]] = [anchored[0]]
        for p in anchored[1:]:
            if p != deduped[-1]:
                deduped.append(p)
        if len(deduped) < 2:
            return

        if curved:
            # Sample Catmull-Rom spline densely; the resulting polyline behaves
            # exactly like the linear branch for arc-length parameterization.
            sampled = _sample_catmull_rom(deduped, samples_per_segment=16)
        else:
            sampled = deduped

        seg_lens: List[float] = []
        total = 0.0
        for i in range(len(sampled) - 1):
            ax, ay = sampled[i]
            bx, by = sampled[i + 1]
            d = math.hypot(bx - ax, by - ay)
            seg_lens.append(d)
            total += d

        if total <= 0:
            return

        self.path_waypoints = sampled
        self.path_segment_lengths = seg_lens
        self.path_total_dist = total
        self.path_start_time = engine.get_time()
        self.path_duration = duration
        self.path_ease = ease
        self.path_ramp_frac = utils.clamp(ramp_frac, 0.0, 0.49)
        self.path_curved = curved
        self.path_allow_skip = allow_skip
        self._path_skip_requested = False
        self.path_mode = True
        self.pan_algorithm = None
        # Lock target to the final waypoint so legacy logic stays consistent.
        final_x, final_y = sampled[-1]
        self.target_x = final_x
        self.target_y = final_y

    def _path_position(self) -> Tuple[float, float]:
        """Compute current camera position along the active smooth path."""
        elapsed = engine.get_time() - self.path_start_time
        if self.path_duration <= 0:
            return self.path_waypoints[-1]
        t = utils.clamp(elapsed / self.path_duration, 0.0, 1.0)
        if self.path_ease:
            # Trapezoidal velocity profile: accelerate over `r`, cruise at peak
            # velocity, then decelerate over `r`. Unlike cubic ease-in/out the
            # velocity never drops near zero except at the very first / last
            # instant, so the camera doesn't appear to "creep" at the start
            # and finish.
            r = self.path_ramp_frac
            if r <= 0.0:
                pass  # linear
            else:
                v_peak = 1.0 / (1.0 - r)
                if t < r:
                    t = 0.5 * v_peak * t * t / r
                elif t <= 1.0 - r:
                    t = v_peak * (t - 0.5 * r)
                else:
                    rem = 1.0 - t
                    t = 1.0 - 0.5 * v_peak * rem * rem / r
        target_dist = t * self.path_total_dist
        accum = 0.0
        for i, seg_len in enumerate(self.path_segment_lengths):
            if accum + seg_len >= target_dist or i == len(self.path_segment_lengths) - 1:
                local_t = 0.0 if seg_len <= 0 else (target_dist - accum) / seg_len
                ax, ay = self.path_waypoints[i]
                bx, by = self.path_waypoints[i + 1]
                return (ax + (bx - ax) * local_t, ay + (by - ay) * local_t)
            accum += seg_len
        return self.path_waypoints[-1]

    def request_path_skip(self):
        """End the active smooth path early on the next update (snaps to end)."""
        if self.path_mode and self.path_allow_skip:
            self._path_skip_requested = True

    def cancel_smooth_path(self):
        self.path_mode = False
        self.path_waypoints = []
        self.path_segment_lengths = []
        self.path_total_dist = 0.0
        self.path_duration = 0
        self.path_curved = False
        self.path_allow_skip = False
        self._path_skip_requested = False
        self.path_on_end = None

    # -----------------------------------------------------------------

    def set_shake(self, shake: List[Tuple[int, int]], duration: int = 0):
        """
        shake - A List of camera offset tuples that will be looped over each frame to create the screen shake effect
        duration - How long the effect should last (in milliseconds). If 0 or negative, effect is permanent until reset_shake is called
        """
        self.shake = shake
        self.shake_idx = 0
        if duration > 0:
            self.shake_end_at = engine.get_time() + duration

    def reset_shake(self):
        self.shake = self.no_shake
        self.shake_idx = 0
        self.shake_end_at = 0

    def update(self):
        # Make sure target is within bounds
        self.set_target_limits(self.game.tilemap)

        if self.path_mode:
            # Continuous multi-waypoint pan: drive position purely from time.
            elapsed = engine.get_time() - self.path_start_time
            if self._path_skip_requested or elapsed >= self.path_duration:
                # Snap to the final waypoint and exit path mode cleanly.
                fx, fy = self.path_waypoints[-1]
                self.current_x = self.target_x = fx
                self.current_y = self.target_y = fy
                end_cb = self.path_on_end
                self.cancel_smooth_path()
                self.last_at_rest_time = engine.get_time()
                self.last_at_rest_position = (self.current_x, self.current_y)
                if end_cb is not None:
                    try:
                        end_cb()
                    except Exception:
                        pass
            else:
                new_x, new_y = self._path_position()
                self.current_x = new_x
                self.current_y = new_y
            self.set_current_limits(self.game.tilemap)
            # Update screenshake even while panning along a path
            self.shake_idx += 1
            self.shake_idx %= len(self.shake)
            if self.shake_end_at and engine.get_time() > self.shake_end_at:
                self.reset_shake()
            return

        # Move camera around
        (new_x, new_y) = self.get_next_position()
        self.current_x = new_x
        self.current_y = new_y

        # If close enough to target, just make it so
        diff_x = self.target_x - self.current_x
        diff_y = self.target_y - self.current_y
        if abs(diff_x) <= 0.125:
            self.current_x = self.target_x
        if abs(diff_y) <= 0.125:
            self.current_y = self.target_y

        if self.at_rest():
            # all custom algorithms should only last one pan
            self.pan_algorithm = None
            self.last_at_rest_time = engine.get_time()
            self.last_at_rest_position = (self.current_x, self.current_y)

        if self.pan_targets and self.at_rest():
            self.target_x, self.target_y = self.pan_targets.pop()

        # Make sure we do not go offscreen -- maybe shouldn't happen?
        # Could happen when map size changes?
        self.set_current_limits(self.game.tilemap)

        # Update screenshake
        self.shake_idx += 1
        self.shake_idx %= len(self.shake)
        if self.shake_end_at and engine.get_time() > self.shake_end_at:
            self.reset_shake()


def _sample_catmull_rom(points: List[Tuple[float, float]], samples_per_segment: int = 16) -> List[Tuple[float, float]]:
    """
    Sample a centripetal Catmull-Rom spline through `points`. The first and
    last points are kept exactly; intermediate corners are bowed gently so the
    camera does not bend at sharp 90 degree angles.
    """
    if len(points) < 2:
        return list(points)
    if len(points) == 2:
        return list(points)

    # Pad endpoints by reflecting so the spline starts/ends at the original points.
    p0 = (2 * points[0][0] - points[1][0], 2 * points[0][1] - points[1][1])
    pN = (2 * points[-1][0] - points[-2][0], 2 * points[-1][1] - points[-2][1])
    pts = [p0] + list(points) + [pN]

    out: List[Tuple[float, float]] = [points[0]]
    for i in range(len(pts) - 3):
        p_a, p_b, p_c, p_d = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        for s in range(1, samples_per_segment + 1):
            t = s / samples_per_segment
            t2 = t * t
            t3 = t2 * t
            # Standard Catmull-Rom basis (tension = 0.5).
            x = 0.5 * ((2 * p_b[0]) +
                       (-p_a[0] + p_c[0]) * t +
                       (2 * p_a[0] - 5 * p_b[0] + 4 * p_c[0] - p_d[0]) * t2 +
                       (-p_a[0] + 3 * p_b[0] - 3 * p_c[0] + p_d[0]) * t3)
            y = 0.5 * ((2 * p_b[1]) +
                       (-p_a[1] + p_c[1]) * t +
                       (2 * p_a[1] - 5 * p_b[1] + 4 * p_c[1] - p_d[1]) * t2 +
                       (-p_a[1] + 3 * p_b[1] - 3 * p_c[1] + p_d[1]) * t3)
            out.append((x, y))
    return out