from __future__ import annotations

import logging
import random
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import List, Optional

import pygame

import app.engine.config as cf
from app.constants import (COLORKEY, TILEHEIGHT, TILEWIDTH, TILEX, TILEY, WINHEIGHT,
                           WINWIDTH)
from app.data.database.database import DB
from app.engine import (action, background, battle_animation, combat_calcs,
                        engine, gui, icons, image_mods, item_funcs,
                        item_system, skill_system)
from app.engine.android_runtime import is_android_render_optimization_enabled
from app.engine.performance import RUNTIME_PROFILER
from app.engine.combat import playback as pb
from app.engine.combat.playback import PlaybackBrush
from app.engine.combat.base_combat import BaseCombat
from app.engine.combat.map_combat import MapCombat
from app.engine.combat.mock_combat import MockCombat
from app.engine.combat.solver import CombatPhaseSolver
from app.engine.fonts import FONT
from app.engine.game_counters import ANIMATION_COUNTERS
from app.engine.game_state import game
from app.engine.health_bar import CombatHealthBar
from app.engine.objects.item import ItemObject
from app.engine.objects.unit import UnitObject
from app.engine.sound import get_sound_thread
from app.engine.sprites import SPRITES
from app.engine.graphics.text.text_renderer import render_text, text_width, rendered_text_width
from app.events import triggers
from app.data.resources.resources import RESOURCES
from app.utilities import utils
from app.utilities.typing import NID
from app.utilities.enums import HAlignment
from app.engine.combat.utils import resolve_weapon


@dataclass(eq=False)
class _AndroidCombatUILayer:
    """Immutable UI pixels plus lazily-built Android display variants."""
    raw: pygame.Surface
    variants: dict[int, pygame.Surface] = field(default_factory=dict)


class AnimationCombat(BaseCombat, MockCombat):
    alerts: bool = True
    # On-map animated combat (delegates handle_state_stack to MapCombat's), so
    # it does finalize a turn -- override BaseCombat's False.
    finalizes_turn: bool = True

    def __init__(self, attacker: UnitObject, main_item: ItemObject, defender: UnitObject, def_item: ItemObject,
                 script: list, total_rounds: int = 1, arena_combat: bool = False):
        self.attacker = attacker
        self.defender = defender
        self.main_item = main_item
        self.def_item = def_item
        self.attack_partner_weapon: Optional[ItemObject] = resolve_weapon(self.attacker.strike_partner)
        if self.defender:
            self.defense_partner_weapon: Optional[ItemObject] = resolve_weapon(self.defender.strike_partner)
        else:
            self.defense_partner_weapon: Optional[ItemObject] = None

        if self.defender.team == 'player' and self.attacker.team != 'player':
            self.right = self.defender
            self.right_item = self.def_item
            self.left = self.attacker
            self.left_item = self.main_item
        elif self.attacker.team in DB.teams.enemies and self.defender.team not in DB.teams.enemies:
            self.right = self.defender
            self.right_item = self.def_item
            self.left = self.attacker
            self.left_item = self.main_item
        else:
            self.right = self.attacker
            self.right_item = self.main_item
            self.left = self.defender
            self.left_item = self.def_item

        if self.attacker.position and self.defender.position:
            self.distance = utils.calculate_distance(self.attacker.position, self.defender.position)
        else:
            self.distance = 1
        self.at_range = self.distance - 1

        if self.defender.position:
            self.view_pos = self.defender.position
        elif self.attacker.position:
            self.view_pos = self.attacker.position
        else:
            self.view_pos = (0, 0)

        self.state_machine = CombatPhaseSolver(
            self.attacker, self.main_item, [self.main_item],
            [self.defender], [[]], [self.defender.position],
            self.defender, self.def_item, script, total_rounds,
            update_stats=self._set_stats)

        self.last_update = engine.get_time()
        self.arena_combat = arena_combat
        if self.arena_combat:
            self.state = 'arena_init'
            self.bg_black = SPRITES.get('bg_black').copy()
            self.bg_black_progress = 0
        else:
            self.state = 'init'
            self.bg_black = None
            self.bg_black_progress = 1

        self.left_hp_bar = CombatHealthBar(self.left)
        self.right_hp_bar = CombatHealthBar(self.right)

        self._skip = False
        self.full_playback = []
        self.playback = []
        self.actions = []

        self.viewbox_time = 250
        self.viewbox = None
        self.battle_background = None

        self.setup_dark()

        self.setup_ui()

        # For pan
        self.focus_right: bool = self.attacker is self.right
        self.setup_pan()

        # For shake
        self.setup_shake()

        self.battle_music = None

        self.llast_gauge = self.left.get_guard_gauge()
        self.rlast_gauge = self.right.get_guard_gauge()
        self.left_battle_anim = battle_animation.get_battle_anim(self.left, self.left_item, self.distance, allow_transform=True)
        self.right_battle_anim = battle_animation.get_battle_anim(self.right, self.right_item, self.distance, allow_transform=True)
        self.lp_battle_anim = None
        self.rp_battle_anim = None
        self.left_partner = None
        self.right_partner = None

        if DB.constants.value('pairup'):
            if self.left.strike_partner:
                pp = self.left.strike_partner
                self.left_partner = pp
                self.lp_battle_anim = battle_animation.get_battle_anim(pp, pp.get_weapon(), self.distance, allow_transform=True)
            elif self.left.traveler and item_system.is_weapon(self.right, self.right_item):
                pp = game.get_unit(self.left.traveler)
                self.left_partner = pp
                self.lp_battle_anim = battle_animation.get_battle_anim(pp, pp.get_weapon(), self.distance, allow_transform=True)
            if self.right.strike_partner:
                pp = self.right.strike_partner
                self.right_partner = pp
                self.rp_battle_anim = battle_animation.get_battle_anim(pp, pp.get_weapon(), self.distance, allow_transform=True)
            elif self.right.traveler and item_system.is_weapon(self.left, self.left_item):
                pp = game.get_unit(self.right.traveler)
                self.right_partner = pp
                self.rp_battle_anim = battle_animation.get_battle_anim(pp, pp.get_weapon(), self.distance, allow_transform=True)

        self.current_battle_anim = None

        self.initial_paint_setup()
        self._set_stats(self.playback)

        self._delay_death = False

    def skip(self):
        self._skip = True
        battle_animation.battle_anim_speed = 0.25

    def end_skip(self):
        self._skip = False
        battle_animation.battle_anim_speed = 1

    def get_actors(self):
        if self.get_from_playback('defender_phase'):
            if self.attacker is self.left:
                attacker, defender = self.right, self.left
                item, d_item = self.right_item, self.left_item
                current_battle_anim = self.right_battle_anim
            else:
                attacker, defender = self.left, self.right
                item, d_item = self.left_item, self.right_item
                current_battle_anim = self.left_battle_anim
        elif self.get_from_playback('defender_partner_phase'):
            if self.attacker is self.left and self.rp_battle_anim:
                attacker, defender = self.right_partner, self.left
                item, d_item = self.right_partner.get_weapon(), self.left_item
                current_battle_anim = self.rp_battle_anim
            elif self.attacker is self.left:
                attacker, defender = self.right, self.left
                item, d_item = self.right_item, self.left_item
                current_battle_anim = self.right_battle_anim
            elif self.lp_battle_anim:
                attacker, defender = self.left_partner, self.right
                item, d_item = self.left_partner.get_weapon(), self.right_item
                current_battle_anim = self.lp_battle_anim
            else:
                attacker, defender = self.left, self.right
                item, d_item = self.left_item, self.right_item
                current_battle_anim = self.left_battle_anim
        elif self.get_from_playback('attacker_partner_phase'):
            if self.attacker is self.left and self.lp_battle_anim:
                attacker, defender = self.left_partner, self.right
                item, d_item = self.left_partner.get_weapon(), self.right_item
                current_battle_anim = self.lp_battle_anim
            elif self.attacker is self.left:
                attacker, defender = self.left, self.right
                item, d_item = self.left_item, self.right_item
                current_battle_anim = self.left_battle_anim
            elif self.rp_battle_anim:
                attacker, defender = self.right_partner, self.left
                item, d_item = self.right_partner.get_weapon(), self.left_item
                current_battle_anim = self.rp_battle_anim
            else:
                attacker, defender = self.right, self.left
                item, d_item = self.right_item, self.left_item
                current_battle_anim = self.right_battle_anim
        else:
            if self.attacker is self.left:
                attacker, defender = self.left, self.right
                item, d_item = self.left_item, self.right_item
                current_battle_anim = self.left_battle_anim
            else:
                attacker, defender = self.right, self.left
                item, d_item = self.right_item, self.left_item
                current_battle_anim = self.right_battle_anim
        return attacker, item, defender, d_item, current_battle_anim

    def pair_battle_animations(self, entrance_frames=14):
        left_pos = (self.left.position[0] - game.camera.get_x()) * TILEWIDTH, \
            (self.left.position[1] - game.camera.get_y()) * TILEHEIGHT
        right_pos = (self.right.position[0] - game.camera.get_x()) * TILEWIDTH, \
            (self.right.position[1] - game.camera.get_y()) * TILEHEIGHT
        self.left_battle_anim.pair(self, self.right_battle_anim, False, self.at_range, 14, left_pos)
        self.left_battle_anim.entrance_counter = entrance_frames
        if self.lp_battle_anim:
            self.lp_battle_anim.pair(self, self.right_battle_anim, False, self.at_range, 14, left_pos)
            self.lp_battle_anim.entrance_counter = entrance_frames
        self.right_battle_anim.pair(self, self.left_battle_anim, True, self.at_range, 14, right_pos)
        self.right_battle_anim.entrance_counter = entrance_frames
        if self.rp_battle_anim:
            self.rp_battle_anim.pair(self, self.left_battle_anim, True, self.at_range, 14, right_pos)
            self.rp_battle_anim.entrance_counter = entrance_frames

    def ui_should_be_hidden(self):
        return game.game_vars.get("_hide_ui")

    def update(self) -> bool:
        current_time = engine.get_time() - self.last_update
        current_state = self.state

        if self.state == 'init':
            self.start_combat()
            self.attacker.sprite.change_state('combat_attacker')
            self.defender.sprite.change_state('combat_defender')
            self.state = 'red_cursor'
            game.cursor.combat_show()
            game.cursor.set_pos(self.view_pos)
            if not self._skip:
                game.state.change('move_camera')
            self._set_stats(self.playback)  # For start combat changes

        elif self.state == 'red_cursor':
            if self._skip or current_time > 400:
                game.cursor.hide()
                game.highlight.remove_highlights()
                self.state = 'fade_in'

        elif self.state == 'fade_in':
            self.build_viewbox(current_time)
            if current_time > self.viewbox_time:
                self.viewbox = (self.viewbox[0], self.viewbox[1], 0, 0)
                self.state = 'entrance'
                self.pair_battle_animations(14)
                # Unit should be facing down
                self.attacker.sprite.change_state('selected')

        elif self.state == 'entrance':
            entrance_time = utils.frames2ms(10)
            if not self.ui_should_be_hidden():
                self.bar_offset = current_time / entrance_time
                self.name_offset = current_time / entrance_time
            self.platform_offset = current_time / entrance_time
            if self._skip or current_time > entrance_time:
                if not self.ui_should_be_hidden():
                    self.bar_offset = 1
                    self.name_offset = 1
                self.platform_offset = 1
                if self.battle_background:
                    self.battle_background.fade_in(utils.frames2ms(25))
                self.state = 'init_pause'

        elif self.state == 'arena_init':
            self.start_combat()
            self._set_stats(self.playback)
            self.pair_battle_animations(0)
            if not self.ui_should_be_hidden():
                self.bar_offset = 1
                self.name_offset = 1
            self.platform_offset = 1
            self.state = 'arena_fade_in'

        elif self.state == 'arena_fade_in':
            entrance_time = utils.frames2ms(10)
            self.bg_black_progress = current_time / entrance_time
            if self._skip or current_time > entrance_time:
                self.bg_black_progress = 1
                self.state = 'init_pause'

        elif self.state == 'init_pause':
            if self._skip or current_time > utils.frames2ms(25):
                if self.battle_background:
                    self.battle_background.set_normal()
                self.start_event(True)
                self.state = 'battle_music'

        elif self.state == 'battle_music':
            self.start_battle_music()
            # Check for transforms here
            if self.left_battle_anim.is_transform() or self.right_battle_anim.is_transform() or \
                    (self.lp_battle_anim and self.lp_battle_anim.is_transform()) or \
                    (self.rp_battle_anim and self.rp_battle_anim.is_transform()):
                self.state = 'transform'
                if self.left_battle_anim.is_transform():
                    self.left_battle_anim.initiate_transform()
                if self.right_battle_anim.is_transform():
                    self.right_battle_anim.initiate_transform()
                if self.lp_battle_anim and self.lp_battle_anim.is_transform():
                    self.lp_battle_anim.initiate_transform()
                if self.rp_battle_anim and self.rp_battle_anim.is_transform():
                    self.rp_battle_anim.initiate_transform()
            else:
                self.state = 'pre_proc'

        elif self.state == 'transform':
            if self.left_battle_anim.done() and self.right_battle_anim.done() and \
                    (not self.lp_battle_anim or self.lp_battle_anim.done()) and \
                    (not self.rp_battle_anim or self.rp_battle_anim.done()):
                # Get new battle anims
                if self.left_battle_anim.is_transform():
                    self.left_battle_anim = battle_animation.get_battle_anim(self.left, self.left_item, self.distance)
                if self.right_battle_anim.is_transform():
                    self.right_battle_anim = battle_animation.get_battle_anim(self.right, self.right_item, self.distance)
                if self.lp_battle_anim and self.lp_battle_anim.is_transform():
                    self.lp_battle_anim = battle_animation.get_battle_anim(self.left_partner, self.left_partner.get_weapon(), self.distance)
                if self.rp_battle_anim and self.rp_battle_anim.is_transform():
                    self.rp_battle_anim = battle_animation.get_battle_anim(self.right_partner, self.right_partner.get_weapon(), self.distance)
                # re-pair
                self.pair_battle_animations(0)
                self.state = 'pre_proc'

        elif self.state == 'pre_proc':
            if self.left_battle_anim.done() and self.right_battle_anim.done() and \
                    not self.proc_icons:
                # These would have happened from pre_combat and start_combat
                if self.get_from_full_playback('attack_pre_proc'):
                    self.set_up_pre_proc_animation('attack_pre_proc')
                elif self.get_from_full_playback('defense_pre_proc'):
                    self.set_up_pre_proc_animation('defense_pre_proc')
                elif self.set_up_other_proc_icons(self.attacker):
                    pass  # Processing is done in the if check above
                elif self.set_up_other_proc_icons(self.defender):
                    pass  # Processing is done in the if check above
                else:
                    self.add_proc_icon.memory.clear()
                    self.state = 'begin_phase'

        elif self.state == 'begin_phase':
            # Get playback
            if not self.state_machine.get_state():
                logging.debug("End Combat")
                if self._delay_death:
                    self.state = 'delayed_death'
                    all_units = self._all_units()
                    self.handle_combat_death(all_units)
                else:
                    self.state = 'end_combat'
                self.actions.clear()
                self.playback.clear()
                return False
            self.actions, self.playback = self.state_machine.do()
            self.full_playback += self.playback
            if not self.actions and not self.playback:
                logging.debug("Set Up Next State")
                self.state_machine.setup_next_state()
                return False
            # self._set_stats()

            # Set up combat effects (legendary)
            attacker, item, defender, d_item, self.current_battle_anim = self.get_actors()
            any_effect: bool = False
            if not any(brush.attacker_nid == attacker.nid for brush in self.get_from_full_playback('combat_effect')):
                if item:
                    effect_nid = item_system.combat_effect(attacker, item, defender, d_item, 'attack')
                    if effect_nid:
                        effect = self.current_battle_anim.get_effect(effect_nid, pose='Attack')
                        any_effect = True
                        self.full_playback.append(pb.CombatEffect(attacker.nid))  # Mark that we've done their combat effect
                        self.current_battle_anim.add_effect(effect)

            if any_effect:
                self.state = 'combat_effect'
            elif self.get_from_playback('attack_proc'):
                self.set_up_proc_animation('attack_proc')
            elif self.get_from_playback('defense_proc'):
                self.set_up_proc_animation('defense_proc')
            else:
                self.add_proc_icon.memory.clear()
                self.set_up_combat_animation()

        elif self.state == 'combat_effect':
            if not self.left_battle_anim.effect_playing() and not self.right_battle_anim.effect_playing() and current_time > 400:
                if self.get_from_playback('attack_proc'):
                    self.set_up_proc_animation('attack_proc')
                elif self.get_from_playback('defense_proc'):
                    self.set_up_proc_animation('defense_proc')
                else:
                    self.add_proc_icon.memory.clear()
                    self.set_up_combat_animation()

        elif self.state == 'attack_proc':
            if self.left_battle_anim.done() and self.right_battle_anim.done() and not self.proc_icons:
                if self.get_from_playback('attack_proc'):
                    self.set_up_proc_animation('attack_proc')
                elif self.get_from_playback('defense_proc'):
                    self.set_up_proc_animation('defense_proc')
                else:
                    self.add_proc_icon.memory.clear()
                    self.set_up_combat_animation()

        elif self.state == 'defense_proc':
            if self.left_battle_anim.done() and self.right_battle_anim.done() and not self.proc_icons:
                if self.get_from_playback('defense_proc'):
                    self.set_up_proc_animation('defense_proc')
                else:
                    self.add_proc_icon.memory.clear()
                    self.set_up_combat_animation()

        elif self.state == 'combat_hit':
            self.clean_up0()
            
            # Set up on-hit effects for magic stuff
            attacker, item, defender, d_item, self.current_battle_anim = self.get_actors()   
            if item:
                effect_nid = item_system.on_hit_effect(attacker, item, defender, d_item, 'attack')
                if effect_nid:
                    # Must designate a pose called `Effect` that has no `SpellHit` and `BreakParentLoop` (unsure about this) in the editor so we don't hang
                    # I used the `Legend` effect from the discord as a template to format other effects
                    effect = self.current_battle_anim.get_effect(effect_nid, pose='Effect')
                    self.current_battle_anim.add_effect(effect)

            self.state = 'hp_change'
                
        elif self.state == 'hp_change':
            proceed = self.current_battle_anim.can_proceed()
            if current_time > utils.frames2ms(27) and self.left_hp_bar.done() and self.right_hp_bar.done() and proceed:
                self.current_battle_anim.resume()
                if not self._delay_death:
                    if self.left.get_hp() <= 0:
                        self.left_battle_anim.start_dying_animation()
                    if self.right.get_hp() <= 0:
                        self.right_battle_anim.start_dying_animation()
                    if (self.left.get_hp() <= 0 or self.right.get_hp() <= 0) and self.current_battle_anim.state != 'dying':
                        self.current_battle_anim.wait_for_dying()
                self.state = 'anim'

        elif self.state == 'anim':
            if self.left_battle_anim.done() and self.right_battle_anim.done() and \
                    (not self.rp_battle_anim or self.rp_battle_anim.done()) and \
                    (not self.lp_battle_anim or self.lp_battle_anim.done()):
                self.state = 'end_phase'

        elif self.state == 'end_phase':
            self._end_phase()
            self.state = 'begin_phase'

        elif self.state == 'delayed_death':
            if self.left.get_hp() <= 0:
                self.left_battle_anim.start_dying_animation()
            if self.right.get_hp() <= 0:
                self.right_battle_anim.start_dying_animation()
            if (self.left.get_hp() <= 0 or self.right.get_hp() <= 0) and self.current_battle_anim.state != 'dying':
                self.current_battle_anim.wait_for_dying()
            self.state = 'anim_delayed_death'

        elif self.state == 'anim_delayed_death':
            if self.left_battle_anim.done() and self.right_battle_anim.done() and \
                    (not self.rp_battle_anim or self.rp_battle_anim.done()) and \
                    (not self.lp_battle_anim or self.lp_battle_anim.done()):
                self._delay_death = False
                self.state = 'end_combat'

        elif self.state == 'end_combat':
            if self.left_battle_anim.done() and self.right_battle_anim.done():
                self.focus_exp()
                self.move_camera()
                self.state = 'exp_pause'

        elif self.state == 'exp_pause':
            if self._skip or current_time > 450:
                self.clean_up1()
                self.state = 'exp_wait'

        elif self.state == 'exp_wait':
            # waits here for exp_gain state to finish
            self.state = 'revert_transform'

        elif self.state == 'revert_transform':
            # Get new battle anims
            if not self._skip:
                if not self.left.is_dying:
                    new_left_battle_anim = battle_animation.get_battle_anim(self.left, self.left_item, self.distance, allow_revert=True)
                    if new_left_battle_anim:  # Need to check that the new animation actually exists
                        self.left_battle_anim = new_left_battle_anim
                if not self.right.is_dying:
                    new_right_battle_anim = battle_animation.get_battle_anim(self.right, self.right_item, self.distance, allow_revert=True)
                    if new_right_battle_anim:
                        self.right_battle_anim = new_right_battle_anim
                if self.lp_battle_anim:
                    new_lp_battle_anim = battle_animation.get_battle_anim(self.left_partner, self.left_partner.get_weapon(), self.distance, allow_revert=True)
                    if new_lp_battle_anim:
                        self.lp_battle_anim = new_lp_battle_anim
                if self.rp_battle_anim:
                    new_rp_battle_anim = battle_animation.get_battle_anim(self.right_partner, self.right_partner.get_weapon(), self.distance, allow_revert=True)
                    if new_rp_battle_anim:
                        self.rp_battle_anim = new_rp_battle_anim
                # re-pair
                self.pair_battle_animations(0)
                if self.left_battle_anim.is_transform():
                    self.left_battle_anim.initiate_transform()
                if self.right_battle_anim.is_transform():
                    self.right_battle_anim.initiate_transform()
                if self.lp_battle_anim and self.lp_battle_anim.is_transform():
                    self.lp_battle_anim.initiate_transform()
                if self.rp_battle_anim and self.rp_battle_anim.is_transform():
                    self.rp_battle_anim.initiate_transform()
            self.state = 'fade_out_wait'

        elif self.state == 'fade_out_wait':
            if self._skip or current_time > 820:
                if self.arena_combat:
                    self.state = 'arena_out'
                else:
                    self.left_battle_anim.finish()
                    if self.lp_battle_anim:
                        self.lp_battle_anim.finish()
                    self.right_battle_anim.finish()
                    if self.rp_battle_anim:
                        self.rp_battle_anim.finish()
                    if self.battle_background:
                        fade_time = utils.frames2ms(2.5 if self._skip else 10)
                        self.battle_background.fade_out(fade_time)
                    self.state = 'name_tags_out'

        elif self.state == 'name_tags_out':
            exit_time = utils.frames2ms(2.5 if self._skip else 10)
            if not self.ui_should_be_hidden():
                self.name_offset = 1 - current_time / exit_time
            if current_time > exit_time:
                self.name_offset = 0
                self.state = 'all_out'

        elif self.state == 'all_out':
            exit_time = utils.frames2ms(2.5 if self._skip else 10)
            if not self.ui_should_be_hidden():
                self.bar_offset = 1 - current_time / exit_time
            self.platform_offset = 1 - current_time / exit_time
            if current_time > exit_time:
                self.platform_offset = 0
                self.bar_offset = 0
                self.state = 'fade_out'

        elif self.state == 'fade_out':
            self.build_viewbox(self.viewbox_time - current_time)
            if current_time > self.viewbox_time:
                self.finish()
                self.clean_up2()
                self.end_skip()
                return True

        elif self.state == 'arena_out':
            exit_time = utils.frames2ms(2.5 if self._skip else 10)
            self.bg_black_progress = 1 - current_time / exit_time
            if current_time > exit_time:
                self.bg_black_progress = 0
                self.finish()
                self.clean_up2()
                self.end_skip()
                return True

        if self.state != current_state:
            logging.debug("New Animation Combat State: %s", self.state)
            self.last_update = engine.get_time()

        # Update hp bars
        self.left_hp_bar.update()
        self.right_hp_bar.update()

        self.update_anims()
        if is_android_render_optimization_enabled():
            self.update_android_transient_visuals()
            for proc_icon in self.proc_icons:
                proc_icon.update()
            self.proc_icons = [proc_icon for proc_icon in self.proc_icons if not proc_icon.done]

        if RUNTIME_PROFILER.enabled and self.state != current_state:
            battle_anim = self.current_battle_anim
            logging.warning(
                "PERF combat-transition phase=%s pose=%s frame=%s/%s effects=%d",
                self.state,
                getattr(battle_anim, 'current_pose', None),
                getattr(battle_anim, 'frame_count', 0),
                getattr(battle_anim, 'num_frames', 0),
                len(getattr(battle_anim, 'child_effects', ())) +
                len(getattr(battle_anim, 'under_child_effects', ())),
            )

        return False

    def initial_paint_setup(self):
        self._android_ui_cache_key = None
        self._android_left_bar_base = None
        self._android_right_bar_base = None
        self._android_bar_layers = {'left': OrderedDict(), 'right': OrderedDict()}
        self._android_gauge_layers = OrderedDict()
        self._android_bar_strip_layers = OrderedDict()
        self._android_name_strip_layers = OrderedDict()
        self._android_arrow_layers = OrderedDict()
        crit_flag = DB.constants.value('crit')
        # Left
        left_color = self.get_color(self.left.team)
        # Name tag
        self.left_name = SPRITES.get('combat_name_left_' + left_color).copy()
        if text_width('text', self.left.name) > 52:
            font = 'narrow'
        else:
            font = 'text'
        render_text(self.left_name, [font], [self.left.name], ['brown'], (30, 8), HAlignment.CENTER)
        # Partner name tag
        if self.lp_battle_anim:
            if self.left.strike_partner:
                ln = self.left.strike_partner.name
            else:
                ln = game.get_unit(self.left.traveler).name
            self.lp_name = SPRITES.get('combat_name_left_' + left_color).copy()
            if text_width('text', ln) > 52:
                font = 'narrow'
            else:
                font = 'text'
            render_text(self.lp_name, [font], [ln], ['brown'], (30, 8), HAlignment.CENTER)
        # Bar
        if crit_flag:
            self.left_bar = SPRITES.get('combat_main_crit_left_' + left_color).copy()
        else:
            self.left_bar = SPRITES.get('combat_main_left_' + left_color).copy()
        if self.left_item:
            name = self.left_item.name
            if text_width('text', name) > 56:
                font = 'narrow'
            else:
                font = 'text'
            render_text(self.left_bar, [font], [name], ['brown'], (WINWIDTH//4 + 31, 5 + (8 if crit_flag else 0)), HAlignment.CENTER)

        # Right
        right_color = self.get_color(self.right.team)
        # Name tag
        self.right_name = SPRITES.get('combat_name_right_' + right_color).copy()
        if text_width('text', self.right.name) > 52:
            font = 'narrow'
        else:
            font = 'text'
        render_text(self.right_name, [font], [self.right.name], ['brown'], (36, 8), HAlignment.CENTER)
        if self.rp_battle_anim:
            if self.right.strike_partner:
                rn = self.right.strike_partner.name
            else:
                rn = game.get_unit(self.right.traveler).name
            self.rp_name = SPRITES.get('combat_name_right_' + right_color).copy()
            if text_width('text', rn) > 52:
                font = 'narrow'
            else:
                font = 'text'
            render_text(self.rp_name, [font], [rn], ['brown'], (36, 8), HAlignment.CENTER)
        # Bar
        if crit_flag:
            self.right_bar = SPRITES.get('combat_main_crit_right_' + right_color).copy()
        else:
            self.right_bar = SPRITES.get('combat_main_right_' + right_color).copy()
        if self.right_item:
            name = self.right_item.name
            if text_width('text', name) > 56:
                font = 'narrow'
            else:
                font = 'text'
            render_text(self.right_bar, [font], [name], ['brown'], (WINWIDTH//4 - 13, 5 + (8 if crit_flag else 0)), HAlignment.CENTER)

        # Platforms
        if self.left.position:
            terrain_nid = game.tilemap.get_terrain(self.left.position)
            left_terrain = DB.terrain.get(terrain_nid)
            if not left_terrain:
                left_terrain = DB.terrain[0]
            left_platform_type = left_terrain.platform
        else:
            left_platform_type = 'Arena'

        if self.right.position:
            terrain_nid = game.tilemap.get_terrain(self.right.position)
            right_terrain = DB.terrain.get(terrain_nid)
            if not right_terrain:
                right_terrain = DB.terrain[0]
            right_platform_type = right_terrain.platform
        else:
            right_platform_type = 'Arena'

        if self.at_range:
            suffix = '-Ranged'
        else:
            suffix = '-Melee'

        left_platform_full_loc = RESOURCES.platforms.get(left_platform_type + suffix, RESOURCES.platforms.get('Arena' + suffix))
        self.left_platform = engine.image_load(left_platform_full_loc)
        right_platform_full_loc = RESOURCES.platforms.get(right_platform_type + suffix, RESOURCES.platforms.get('Arena' + suffix))
        self.right_platform = engine.flip_horiz(engine.image_load(right_platform_full_loc))

        if self.arena_combat:
            panorama = RESOURCES.panoramas.get('combat_arena')
            if not panorama:
                panorama = RESOURCES.panoramas[0]
            self.battle_background = background.PanoramaBackground(panorama)
        elif cf.SETTINGS['battle_bg'] and game.tilemap and self.attacker.position:
            terrain_nid = game.tilemap.get_terrain(self.attacker.position)
            background_nid = DB.terrain.get(terrain_nid).background
            if background_nid:
                panorama = RESOURCES.panoramas.get(background_nid)
                if panorama:
                    self.battle_background = background.PanoramaBackground(panorama)
                    self.battle_background.set_off()

    def start_hit(self, sound=True, miss=False):
        self._apply_actions()
        self._handle_playback(sound)

        if miss:
            self.miss_anim()

    def spell_hit(self):
        self._apply_actions()
        self._handle_playback()

        hp_brushes = ('damage_hit', 'damage_crit', 'heal_hit')
        if not any(brush.nid in hp_brushes for brush in self.playback):
            self.current_battle_anim.resume()

        # If damage is 0 and this is a damaging spell
        if self.get_damage() <= 0 and any(brush.nid in ('damage_hit', 'damage_crit') for brush in self.playback):
            self.no_damage()

    def _handle_playback(self, sound=True):
        hp_brushes = ('damage_hit', 'damage_crit', 'heal_hit')
        hit_brushes = ('defense_hit_proc', 'attack_hit_proc')
        _, _, defender, _, _ = self.get_actors()
        for brush in self.playback:
            if brush.nid in hp_brushes:
                self.last_update = engine.get_time()
                self.state = 'combat_hit'
                self.handle_damage_numbers(brush)
            elif brush.nid in hit_brushes:
                self.add_proc_icon(brush.unit, brush.skill)
            elif brush.nid == 'hit_sound' and sound and not brush.map_only:
                play_sound = brush.sound
                if play_sound == 'Attack Miss 2':
                    play_sound = 'Miss'  # Replace with miss sound
                if self.special_boss_crit(defender, after_attack=True):
                    if play_sound.startswith('Attack Hit'):
                        play_sound = 'Critical Hit ' + str(random.randint(1, 2))
                    elif play_sound.startswith('Final Hit'):
                        new_sound = 'Critical Hit ' + str(random.randint(1, 2))
                        get_sound_thread().play_sfx(new_sound)

                get_sound_thread().play_sfx(play_sound)

    def _apply_actions(self):
        """
        Actually commit the actions that we had stored!
        """
        for act in self.actions:
            action.do(act)
        # Now nothing else should be using the current state, so we can move the state
        self.state_machine.setup_next_state()

    def _end_phase(self):
        if self.llast_gauge == self.left.get_guard_gauge():
            pass
        else:
            self.llast_gauge += self.left.get_gauge_inc()
        if self.rlast_gauge == self.right.get_guard_gauge():
            pass
        else:
            self.rlast_gauge += self.right.get_gauge_inc()

    def finish(self):
        # Fade back music if and only if it was faded in
        from_start = DB.constants.value('restart_battle_music')
        if self.battle_music:
            # Don't battle fade back when we don't restart battle music
            get_sound_thread().battle_fade_back(self.battle_music, from_start)

    def build_viewbox(self, current_time):
        vb_multiplier = utils.clamp(current_time / self.viewbox_time, 0, 1)
        true_x, true_y = self.view_pos[0] - game.camera.get_x() + 0.5, self.view_pos[1] - game.camera.get_y() + 0.5
        vb_x = int(vb_multiplier * true_x * TILEWIDTH)
        vb_y = int(vb_multiplier * true_y * TILEHEIGHT)
        vb_width = int(WINWIDTH - vb_x - (vb_multiplier * (TILEX - true_x)) * TILEWIDTH)
        vb_height = int(WINHEIGHT - vb_y - (vb_multiplier * (TILEY - true_y)) * TILEHEIGHT)
        self.viewbox = (vb_x, vb_y, vb_width, vb_height)

    def map_underlay_visible(self) -> bool:
        """Whether the map must be composed behind this combat frame.

        A normal panorama covers the complete logical combat surface.  Drawing
        the map beneath it is therefore invisible work; all transition states
        and battles without a panorama retain the established map path.
        """
        battle_background = self.battle_background
        if not battle_background or battle_background.fade_state != 'normal':
            return True
        images = getattr(getattr(battle_background, 'panorama', None), 'images', ())
        if not images:
            return True
        image = images[battle_background.counter % len(images)]
        return not image or image.get_width() < WINWIDTH or image.get_height() < WINHEIGHT

    def start_battle_music(self):
        attacker_battle = item_system.battle_music(self.attacker, self.main_item, self.defender, resolve_weapon(self.defender), 'attack') \
            or skill_system.battle_music(self.playback, self.attacker, self.main_item, self.defender, resolve_weapon(self.defender), 'attack')
        if not attacker_battle and 'Boss' in self.attacker.tags:
            attacker_battle = game.level.music.get('boss_battle', None)
        defender_battle = None
        if self.defender:
            if self.def_item:
                defender_battle = item_system.battle_music(self.defender, self.def_item, self.attacker, self.main_item, 'defense') \
                or skill_system.battle_music(self.playback, self.defender, self.def_item, self.attacker, self.main_item, 'defense')
            else:
                defender_battle = skill_system.battle_music(self.playback, self.defender, self.def_item, self.attacker, self.main_item, 'defense')
            if not defender_battle and 'Boss' in self.defender.tags:
                defender_battle = game.level.music.get('boss_battle', None)
        battle_music = game.level.music.get('%s_battle' % self.attacker.team, None)
        from_start = DB.constants.value('restart_battle_music')
        if attacker_battle:
            self.battle_music = get_sound_thread().battle_fade_in(attacker_battle, from_start=from_start)
        elif defender_battle:
            self.battle_music = get_sound_thread().battle_fade_in(defender_battle, from_start=from_start)
        elif battle_music:
            self.battle_music = get_sound_thread().battle_fade_in(battle_music, from_start=from_start)

    def left_team(self):
        return self.left.team

    def right_team(self):
        return self.right.team

    def get_color(self, team: NID) -> str:
        return game.teams.get(team).combat_color

    def _set_stats(self, playback: List[PlaybackBrush]):
        a_hit = combat_calcs.compute_hit(self.attacker, self.defender, self.main_item, self.def_item, 'attack', self.state_machine.get_attack_info())
        a_mt = combat_calcs.compute_damage(self.attacker, self.defender, self.main_item, self.def_item, 'attack', self.state_machine.get_attack_info())
        if DB.constants.value('crit'):
            a_crit = combat_calcs.compute_crit(self.attacker, self.defender, self.main_item, self.def_item, 'attack', self.state_machine.get_attack_info())
        else:
            a_crit = 0
        a_stats = a_hit, a_mt, a_crit

        if self.attacker.strike_partner:
            attacker = self.attacker.strike_partner
            ap_hit = combat_calcs.compute_hit(attacker, self.defender, attacker.get_weapon(), self.def_item, 'attack', self.state_machine.get_attack_info())
            ap_mt = combat_calcs.compute_damage(attacker, self.defender, attacker.get_weapon(), self.def_item, 'attack', self.state_machine.get_attack_info(), assist=True)
            if DB.constants.value('crit'):
                ap_crit = combat_calcs.compute_crit(attacker, self.defender, attacker.get_weapon(), self.def_item, 'attack', self.state_machine.get_attack_info())
            else:
                ap_crit = 0
            ap_stats = ap_hit, ap_mt, ap_crit
        else:
            ap_stats = 0, 0, 0

        if self.def_item and combat_calcs.can_counterattack(self.attacker, self.main_item, self.defender, self.def_item):
            d_hit = combat_calcs.compute_hit(self.defender, self.attacker, self.def_item, self.main_item, 'defense', self.state_machine.get_defense_info())
            d_mt = combat_calcs.compute_damage(self.defender, self.attacker, self.def_item, self.main_item, 'defense', self.state_machine.get_defense_info())
            if DB.constants.value('crit'):
                d_crit = combat_calcs.compute_crit(self.defender, self.attacker, self.def_item, self.main_item, 'defense', self.state_machine.get_defense_info())
            else:
                d_crit = 0
            d_stats = d_hit, d_mt, d_crit

            if self.defender.strike_partner:
                defender = self.defender.strike_partner
                dp_hit = combat_calcs.compute_hit(defender, self.attacker, resolve_weapon(defender), self.main_item, 'defense', self.state_machine.get_defense_info())
                dp_mt = combat_calcs.compute_damage(defender, self.attacker, resolve_weapon(defender), self.main_item, 'defense', self.state_machine.get_defense_info(), assist=True)
                if DB.constants.value('crit'):
                    dp_crit = combat_calcs.compute_crit(defender, self.attacker, resolve_weapon(defender), self.main_item, 'defense', self.state_machine.get_defense_info())
                else:
                    dp_crit = 0
                dp_stats = dp_hit, dp_mt, dp_crit
            else:
                dp_stats = 0, 0, 0
        else:
            d_stats = None
            dp_stats = None

        if any(brush.nid == 'attacker_partner_phase' for brush in playback):
            ta_stats = ap_stats
        else:
            ta_stats = a_stats

        if any(brush.nid == 'defender_partner_phase' for brush in playback):
            td_stats = dp_stats
        else:
            td_stats = d_stats

        if self.attacker is self.right:
            self.left_stats = td_stats
            self.right_stats = ta_stats
        else:
            self.left_stats = ta_stats
            self.right_stats = td_stats

    def set_up_pre_proc_animation(self, mark_type):
        marks = self.get_from_full_playback(mark_type)
        mark = marks.pop()
        self.full_playback.remove(mark)
        self.mark_proc(mark)

    def set_up_proc_animation(self, mark_type):
        self.state = mark_type
        marks = self.get_from_playback(mark_type)
        mark = marks.pop()
        # Remove the mark since we no longer want to consider it
        self.playback.remove(mark)
        self.mark_proc(mark)

    def set_up_other_proc_icons(self, unit) -> bool:
        """
        Returns whether it added a proc icon
        """
        for skill in unit.skills:
            if skill_system.get_show_skill_icon(unit, skill):
                if self.add_proc_icon(unit, skill):
                    return True
        return False

    def mark_proc(self, mark):
        skill = mark.skill
        unit = mark.unit
        if unit == self.right:
            effect = self.right_battle_anim.get_effect(skill.nid, pose='Attack')
            if effect:
                self.right_battle_anim.add_effect(effect)
        else:
            effect = self.left_battle_anim.get_effect(skill.nid, pose='Attack')
            if effect:
                self.left_battle_anim.add_effect(effect)

        self.add_proc_icon(unit, skill)

    def add_proc_icon(self, unit, skill) -> bool:
        """
        Returns whether it successfully added the proc icon
        """
        if skill_system.get_hide_skill_icon(unit, skill):
            return False
        if skill.nid in self.add_proc_icon.memory.get(unit.nid, []):
            return False

        c = False
        if (unit is self.right or unit is self.right.strike_partner) and self.rp_battle_anim:
            c = True
        elif (unit is self.left or unit is self.left.strike_partner) and self.lp_battle_anim:
            c = True
        new_icon = gui.SkillIcon(skill, unit is self.right, center=c)
        self.proc_icons.append(new_icon)

        # Make sure the same proc icon never shows up twice in the same phase
        if unit.nid not in self.add_proc_icon.memory:
            self.add_proc_icon.memory[unit.nid] = []
        self.add_proc_icon.memory[unit.nid].append(skill.nid)

        if unit == self.right:
            self.focus_right = True
        else:
            self.focus_right = False
        self.move_camera()
        return True
    add_proc_icon.memory = {}

    def special_boss_crit(self, defender, after_attack=False):
        return DB.constants.value('boss_crit') and \
            self.get_from_playback('mark_hit') and \
            'Boss' in defender.tags and \
            (defender.get_hp() <= 0 if after_attack else self.get_damage() >= defender.get_hp())

    def set_up_combat_animation(self):
        self.state = 'anim'
        _, _, defender, _, self.current_battle_anim = self.get_actors()
        alternate_pose = self.get_from_playback('alternate_battle_pose')
        if alternate_pose:
            alternate_pose = alternate_pose[0].alternate_pose
        if alternate_pose and self.current_battle_anim.has_pose(alternate_pose):
            self.current_battle_anim.start_anim(alternate_pose)
        elif self.get_from_playback('mark_crit') or self.special_boss_crit(defender):
            self.current_battle_anim.start_anim('Critical')
        elif self.get_from_playback('mark_hit'):
            self.current_battle_anim.start_anim('Attack')
        elif self.get_from_playback('mark_miss'):
            self.current_battle_anim.start_anim('Miss')

        if self.right_battle_anim == self.current_battle_anim or self.rp_battle_anim == self.current_battle_anim:
            self.focus_right = True
        else:
            self.focus_right = False
        self.move_camera()

    def handle_damage_numbers(self, brush):
        if brush.nid == 'damage_hit':
            damage = brush.damage
            if damage <= 0:
                return
            str_damage = str(damage)
            left = brush.defender == self.left or (self.left.strike_partner and brush.defender == self.left.strike_partner)
            for idx, num in enumerate(str_damage):
                d = gui.DamageNumber(int(num), idx, len(str_damage), left, 'red')
                self.damage_numbers.append(d)
        elif brush.nid == 'damage_crit':
            damage = brush.damage
            if damage <= 0:
                return
            str_damage = str(damage)
            left = brush.defender == self.left or (self.left.strike_partner and brush.defender == self.left.strike_partner)
            for idx, num in enumerate(str_damage):
                d = gui.DamageNumber(int(num), idx, len(str_damage), left, 'yellow')
                self.damage_numbers.append(d)
        elif brush.nid == 'heal_hit':
            damage = brush.damage
            if damage <= 0:
                return
            str_damage = str(damage)
            left = brush.defender == self.left
            for idx, num in enumerate(str_damage):
                d = gui.DamageNumber(int(num), idx, len(str_damage), left, 'cyan')
                self.damage_numbers.append(d)

    def get_damage(self) -> int:
        damage_hit_marks = self.get_from_playback('damage_hit')
        damage_crit_marks = self.get_from_playback('damage_crit')
        if damage_hit_marks:
            damage = damage_hit_marks[0].damage
        elif damage_crit_marks:
            damage = damage_crit_marks[0].damage
        else:
            damage = 0
        return damage

    def shake(self):
        for brush in self.playback:
            if brush.nid == 'damage_hit':
                damage = brush.damage
                unit = brush.attacker
                item = brush.item
                magic = item_funcs.is_magic(unit, item, self.distance)
                if damage > 0:
                    if self.special_boss_crit(brush.defender):
                        self._shake(4)
                    elif magic:
                        self._shake(3)
                    else:
                        self._shake(1)
                else:
                    self._shake(2)  # No damage
            elif brush.nid == 'damage_crit':
                damage = brush.damage
                if damage > 0:
                    self._shake(4)  # Critical
                else:
                    self._shake(2)  # No damage

    def pan_back(self):
        next_state = self.state_machine.get_next_state()
        if next_state:
            if next_state.startswith('attacker'):
                self.focus_right = (self.attacker is self.right)
            elif next_state.startswith('defender'):
                self.focus_right = (self.defender is self.right)
        else:
            self.focus_exp()
        self.move_camera()

    def focus_exp(self):
        # Handle exp
        if self.attacker.team == 'player':
            self.focus_right = (self.attacker is self.right)
        elif self.defender.team == 'player':
            self.focus_right = (self.defender is self.right)

    def draw_battle_anims(self, surf, shake, anim_order, y_offset=0):
        first, second = anim_order
        first_main_battle_anim, first_offset, first_partner, fp_offset = first
        second_main_battle_anim, second_offset, second_partner, sp_offset = second
        # Actor is second main battle anim

        with RUNTIME_PROFILER.section('combat_battle_under'):
            first_main_battle_anim.draw_under(surf, shake, first_offset, self.pan_offset)
            second_main_battle_anim.draw_under(surf, shake, second_offset, self.pan_offset)

        with RUNTIME_PROFILER.section('combat_battle_first'):
            if first_partner:
                first_partner.draw(surf, shake, fp_offset, self.pan_offset, y_offset=y_offset)
            first_main_battle_anim.draw(surf, shake, first_offset, self.pan_offset)

        with RUNTIME_PROFILER.section('combat_battle_second'):
            if second_partner:
                second_partner.draw(surf, shake, sp_offset, self.pan_offset, y_offset=y_offset)
            second_main_battle_anim.draw(surf, shake, second_offset, self.pan_offset)

        with RUNTIME_PROFILER.section('combat_battle_over'):
            second_main_battle_anim.draw_over(surf, shake, second_offset, self.pan_offset)
            first_main_battle_anim.draw_over(surf, shake, first_offset, self.pan_offset)

    def draw(self, surf):
        with RUNTIME_PROFILER.section('combat_background'):
            if self.battle_background:
                self.battle_background.draw(surf)
        # This code is so ugly, sorry rain
        with RUNTIME_PROFILER.section('combat_ui'):
            left_range_offset, right_range_offset, total_shake_x, total_shake_y = \
                self.draw_ui(surf)

        shake = (-total_shake_x, total_shake_y)
        lp_range_offset = left_range_offset - 20
        rp_range_offset = right_range_offset + 20
        y_offset = -3
        if self.playback:
            # Right unit is main boi
            if self.current_battle_anim is self.right_battle_anim:
                # Left unit is being guarded right now!
                if self.llast_gauge == self.left.get_max_guard_gauge() and self.lp_battle_anim:
                    anim_order = [(self.lp_battle_anim, left_range_offset, self.left_battle_anim, lp_range_offset),
                                  (self.right_battle_anim, right_range_offset, self.rp_battle_anim, rp_range_offset)]
                else:  # Normal right anim
                    anim_order = [(self.left_battle_anim, left_range_offset, self.lp_battle_anim, lp_range_offset),
                                  (self.right_battle_anim, right_range_offset, self.rp_battle_anim, rp_range_offset)]
                with RUNTIME_PROFILER.section('combat_battle_anims'):
                    self.draw_battle_anims(surf, shake, anim_order, y_offset)
            # Right partner is main boi
            elif self.rp_battle_anim and self.current_battle_anim is self.rp_battle_anim:
                anim_order = [(self.left_battle_anim, left_range_offset, self.lp_battle_anim, lp_range_offset),
                              (self.rp_battle_anim, right_range_offset, self.right_battle_anim, rp_range_offset)]
                with RUNTIME_PROFILER.section('combat_battle_anims'):
                    self.draw_battle_anims(surf, shake, anim_order, y_offset)
            # Left partner is main boi
            elif self.lp_battle_anim and self.current_battle_anim is self.lp_battle_anim:
                anim_order = [(self.right_battle_anim, right_range_offset, self.rp_battle_anim, rp_range_offset),
                              (self.lp_battle_anim, left_range_offset, self.left_battle_anim, lp_range_offset)]
                with RUNTIME_PROFILER.section('combat_battle_anims'):
                    self.draw_battle_anims(surf, shake, anim_order, y_offset)
            # Left is main boi
            else:
                # Right unit is being guarded right now!
                if self.rlast_gauge == self.right.get_max_guard_gauge() and self.rp_battle_anim:
                    anim_order = [(self.rp_battle_anim, right_range_offset, self.right_battle_anim, rp_range_offset),
                                  (self.left_battle_anim, left_range_offset, self.lp_battle_anim, lp_range_offset)]
                else:  # Normal left anim
                    anim_order = [(self.right_battle_anim, right_range_offset, self.rp_battle_anim, rp_range_offset),
                                  (self.left_battle_anim, left_range_offset, self.lp_battle_anim, lp_range_offset)]
                with RUNTIME_PROFILER.section('combat_battle_anims'):
                    self.draw_battle_anims(surf, shake, anim_order, y_offset)
        else:  # When battle hasn't started yet
            anim_order = [(self.left_battle_anim, left_range_offset, self.lp_battle_anim, lp_range_offset),
                          (self.right_battle_anim, right_range_offset, self.rp_battle_anim, rp_range_offset)]
            with RUNTIME_PROFILER.section('combat_battle_anims'):
                self.draw_battle_anims(surf, shake, anim_order, y_offset)

        # Animations
        with RUNTIME_PROFILER.section('combat_effect_draw'):
            self.draw_anims(surf)

        # Proc Icons
        with RUNTIME_PROFILER.section('combat_proc_icons'):
            for proc_icon in self.proc_icons:
                if not is_android_render_optimization_enabled():
                    proc_icon.update()
                proc_icon.draw(surf)
            if not is_android_render_optimization_enabled():
                self.proc_icons = [proc_icon for proc_icon in self.proc_icons if not proc_icon.done]

        # Damage Numbers
        with RUNTIME_PROFILER.section('combat_damage_numbers'):
            self.draw_damage_numbers(surf, (left_range_offset, right_range_offset, total_shake_x, total_shake_y))

        # make the combat ui (nametags & bars) fade out when appropriate
        ui_fade_states = ['name_tags_out', 'all_out', 'entrance',
                          'fade_in', 'red_cursor', 'init', 'arena_out',
                          'fade_out']
        if self.ui_should_be_hidden() and self.bar_offset > 0:
            self.name_offset -= 0.1
            self.bar_offset -= 0.1
        elif not self.ui_should_be_hidden() and self.state not in ui_fade_states:
            # Combat UI comes in without a fade
            self.name_offset = 1
            self.bar_offset = 1

        with RUNTIME_PROFILER.section('combat_final_compose'):
            crit = 7 if DB.constants.value('crit') else 0
            if is_android_render_optimization_enabled():
                self._draw_android_final_ui(surf, crit)
            else:
                self._draw_legacy_final_ui(surf, crit)

            with RUNTIME_PROFILER.section('combat_foreground'):
                self.foreground.draw(surf)

            if self.bg_black:
                with RUNTIME_PROFILER.section('combat_fade'):
                    bg_black = image_mods.make_translucent(self.bg_black, self.bg_black_progress)
                    surf.blit(bg_black, (0, 0))

    def _draw_legacy_final_ui(self, surf, crit) -> None:
        """Desktop's established full-surface composition path."""
        combat_surf = engine.copy_surface(self.combat_surf)
        with RUNTIME_PROFILER.section('combat_bars'):
            left_bar = self.left_bar.copy()
            right_bar = self.right_bar.copy()
            if self.left_item:
                self.draw_item(left_bar, self.left_item, self.right_item, self.left, self.right, (45, 2 + crit))
            if self.right_item:
                self.draw_item(right_bar, self.right_item, self.left_item, self.right, self.left, (1, 2 + crit))
            self.draw_stats(left_bar, self.left_stats, (42, 0))
            self.draw_stats(right_bar, self.right_stats, (WINWIDTH//2 - 3, 0))
            self.left_hp_bar.draw(left_bar, 27, 30 + crit)
            self.right_hp_bar.draw(right_bar, 25, 30 + crit)

            bar_trans = 52
            left_pos_x = -3 + self.shake_offset[0]
            left_pos_y = WINHEIGHT - left_bar.get_height() + (bar_trans - self.bar_offset * bar_trans) + self.shake_offset[1]
            right_pos_x = WINWIDTH // 2 + self.shake_offset[0]
            right_pos_y = left_pos_y
            combat_surf.blit(left_bar, (left_pos_x, left_pos_y))
            combat_surf.blit(right_bar, (right_pos_x, right_pos_y))

        with RUNTIME_PROFILER.section('combat_guard_gauges'):
            if DB.constants.value('pairup') and not DB.constants.value('attack_stance_only'):
                left_color = self.get_color(self.left.team)
                right_color = self.get_color(self.right.team)
                left_gauge = SPRITES.get('guard_' + left_color).copy()
                font = FONT['number_small2']
                text = str(self.left.get_guard_gauge()) + '-' + str(self.left.get_max_guard_gauge())
                font.blit_center(text, left_gauge, (18, -1))
                right_gauge = SPRITES.get('guard_' + right_color).copy()
                text = str(self.right.get_guard_gauge()) + '-' + str(self.right.get_max_guard_gauge())
                font.blit_center(text, right_gauge, (18, -1))
                gauge_y = WINHEIGHT - 52 + (bar_trans - self.bar_offset * bar_trans) + self.shake_offset[1]
                combat_surf.blit(right_gauge, (right_pos_x, gauge_y))
                combat_surf.blit(left_gauge, (right_pos_x - 37, gauge_y))

        with RUNTIME_PROFILER.section('combat_names'):
            top = -60 + self.name_offset * 60 + self.shake_offset[1]
            if self.lp_battle_anim:
                combat_surf.blit(self.lp_name, (left_pos_x, top + 19))
            if self.rp_battle_anim:
                combat_surf.blit(self.rp_name, (WINWIDTH + 3 - self.rp_name.get_width() + self.shake_offset[0], top + 19))
            combat_surf.blit(self.left_name, (left_pos_x, top))
            combat_surf.blit(self.right_name, (WINWIDTH + 3 - self.right_name.get_width() + self.shake_offset[0], top))

        with RUNTIME_PROFILER.section('combat_ui_tint_build'):
            self.color_ui(combat_surf)
        surf.blit(combat_surf, (0, 0))

    def _draw_android_final_ui(self, surf, crit) -> None:
        """Draw small cached UI layers; position and arrows stay dynamic."""
        tint_phase = self._android_ui_tint_phase()
        with RUNTIME_PROFILER.section('combat_bars'):
            left_base, right_base = self._android_cached_bars(crit)
            left_layer = self._android_cached_health_bar('left', left_base, self.left_hp_bar, 27, 30 + crit)
            right_layer = self._android_cached_health_bar('right', right_base, self.right_hp_bar, 25, 30 + crit)
            bar_trans = 52
            left_pos_x = -3 + self.shake_offset[0]
            left_pos_y = WINHEIGHT - left_layer.raw.get_height() + (bar_trans - self.bar_offset * bar_trans) + self.shake_offset[1]
            right_pos_x = WINWIDTH // 2 + self.shake_offset[0]

        with RUNTIME_PROFILER.section('combat_guard_gauges'):
            left_gauge = right_gauge = None
            if DB.constants.value('pairup') and not DB.constants.value('attack_stance_only'):
                left_gauge = self._android_cached_guard_gauge(
                    self.get_color(self.left.team), self.left.get_guard_gauge(), self.left.get_max_guard_gauge(),
                )
                right_gauge = self._android_cached_guard_gauge(
                    self.get_color(self.right.team), self.right.get_guard_gauge(), self.right.get_max_guard_gauge(),
                )
            bar_strip, bar_top = self._android_cached_bar_strip(
                left_layer, right_layer, left_gauge, right_gauge,
            )

        with RUNTIME_PROFILER.section('combat_names'):
            top = -60 + self.name_offset * 60 + self.shake_offset[1]
            name_strip = self._android_cached_name_strip()

        with RUNTIME_PROFILER.section('combat_ui_blit'):
            surf.blit(self._android_layer_variant(bar_strip, tint_phase), (
                self.shake_offset[0], left_pos_y + bar_top,
            ))
            surf.blit(self._android_layer_variant(name_strip, tint_phase), (
                self.shake_offset[0], top,
            ))

        with RUNTIME_PROFILER.section('combat_ui_arrows'):
            self._draw_android_advantage_arrows(surf, left_pos_x, left_pos_y, right_pos_x, crit, tint_phase)

    def _android_ui_tint_phase(self) -> int:
        """Mirror MockCombat.color_ui's finite darken/lighten state machine."""
        phase = self.darken_ui_background
        if phase:
            phase = min(phase, 4)
            self.darken_ui_background = phase + 1
        return phase

    def _android_cached_bars(self, crit):
        """Return immutable bar pixels without the animated advantage arrow."""
        cache_key = (
            id(self.left_bar), id(self.right_bar), id(self.left_item), id(self.right_item),
            tuple(self.left_stats or ()), tuple(self.right_stats or ()), crit,
        )
        if cache_key != getattr(self, '_android_ui_cache_key', None):
            with RUNTIME_PROFILER.section('combat_ui_cache_build'):
                left_base = self.left_bar.copy()
                right_base = self.right_bar.copy()
                if self.left_item:
                    self._draw_item_icon(left_base, self.left_item, self.right_item, self.left, self.right, (45, 2 + crit))
                if self.right_item:
                    self._draw_item_icon(right_base, self.right_item, self.left_item, self.right, self.left, (1, 2 + crit))
                self.draw_stats(left_base, self.left_stats, (42, 0))
                self.draw_stats(right_base, self.right_stats, (WINWIDTH//2 - 3, 0))
                self._android_ui_cache_key = cache_key
                self._android_left_bar_base = left_base
                self._android_right_bar_base = right_base
                self._android_bar_layers = {'left': OrderedDict(), 'right': OrderedDict()}
        return self._android_left_bar_base, self._android_right_bar_base

    def _android_cached_health_bar(self, side, base, health_bar, left, top):
        cache = getattr(self, '_android_bar_layers', {}).get(side)
        if cache is None:
            cache = OrderedDict()
            if not hasattr(self, '_android_bar_layers'):
                self._android_bar_layers = {}
            self._android_bar_layers[side] = cache
        health_key = (
            id(base), id(health_bar), getattr(health_bar, 'displayed_val', None),
            health_bar.get_max_val() if hasattr(health_bar, 'get_max_val') else None,
            health_bar.big_number() if hasattr(health_bar, 'big_number') else None,
        )
        layer = cache.get(health_key)
        if layer is None:
            with RUNTIME_PROFILER.section('combat_ui_cache_build'):
                raw = base.copy()
                health_bar.draw(raw, left, top)
                layer = _AndroidCombatUILayer(raw)
                cache[health_key] = layer
                while len(cache) > 8:
                    cache.popitem(last=False)
        else:
            cache.move_to_end(health_key)
        return layer

    def _android_cached_guard_gauge(self, color, current, maximum):
        cache = getattr(self, '_android_gauge_layers', None)
        if cache is None:
            cache = self._android_gauge_layers = OrderedDict()
        key = (color, current, maximum)
        layer = cache.get(key)
        if layer is None:
            with RUNTIME_PROFILER.section('combat_ui_cache_build'):
                raw = SPRITES.get('guard_' + color).copy()
                FONT['number_small2'].blit_center(str(current) + '-' + str(maximum), raw, (18, -1))
                layer = _AndroidCombatUILayer(raw)
                cache[key] = layer
                while len(cache) > 8:
                    cache.popitem(last=False)
        else:
            cache.move_to_end(key)
        return layer

    def _android_cached_bar_strip(self, left_layer, right_layer, left_gauge, right_gauge):
        """Combine static bottom UI pieces so a settled frame needs one blit."""
        cache = getattr(self, '_android_bar_strip_layers', None)
        if cache is None:
            cache = self._android_bar_strip_layers = OrderedDict()
        key = (
            left_layer, right_layer, left_gauge, right_gauge,
        )
        strip = cache.get(key)
        if strip is None:
            with RUNTIME_PROFILER.section('combat_ui_cache_build'):
                gauge_y = left_layer.raw.get_height() - 52
                minimum_y = min(0, gauge_y) if left_gauge else 0
                content_y = -minimum_y
                height = max(
                    content_y + left_layer.raw.get_height(),
                    content_y + right_layer.raw.get_height(),
                    content_y + gauge_y + (left_gauge.raw.get_height() if left_gauge else 0),
                    content_y + gauge_y + (right_gauge.raw.get_height() if right_gauge else 0),
                )
                raw = engine.create_surface((WINWIDTH, height), transparent=True)
                raw.blit(left_layer.raw, (-3, content_y))
                raw.blit(right_layer.raw, (WINWIDTH // 2, content_y))
                if right_gauge:
                    raw.blit(right_gauge.raw, (WINWIDTH // 2, content_y + gauge_y))
                if left_gauge:
                    raw.blit(left_gauge.raw, (WINWIDTH // 2 - 37, content_y + gauge_y))
                strip = (_AndroidCombatUILayer(raw), minimum_y)
                cache[key] = strip
                while len(cache) > 8:
                    cache.popitem(last=False)
        else:
            cache.move_to_end(key)
        return strip

    def _android_cached_name_strip(self):
        """Combine immutable name tags; slide and shake stay at blit time."""
        entries = [
            (self.left_name, -3, 0),
            (self.right_name, WINWIDTH + 3 - self.right_name.get_width(), 0),
        ]
        if self.lp_battle_anim:
            entries.append((self.lp_name, -3, 19))
        if self.rp_battle_anim:
            entries.append((self.rp_name, WINWIDTH + 3 - self.rp_name.get_width(), 19))
        key = tuple((id(raw), raw.get_size(), x, y) for raw, x, y in entries)
        cache = getattr(self, '_android_name_strip_layers', None)
        if cache is None:
            cache = self._android_name_strip_layers = OrderedDict()
        layer = cache.get(key)
        if layer is None:
            with RUNTIME_PROFILER.section('combat_ui_cache_build'):
                height = max(y + raw.get_height() for raw, _x, y in entries)
                raw = engine.create_surface((WINWIDTH, height), transparent=True)
                for name, x, y in entries:
                    raw.blit(name, (x, y))
                layer = _AndroidCombatUILayer(raw)
                cache[key] = layer
                while len(cache) > 4:
                    cache.popitem(last=False)
        else:
            cache.move_to_end(key)
        return layer

    def _android_layer_variant(self, layer, tint_phase):
        variant = layer.variants.get(tint_phase)
        if variant is None:
            section = 'combat_ui_tint_build' if tint_phase else 'combat_ui_cache_build'
            with RUNTIME_PROFILER.section(section):
                source = layer.raw if not tint_phase else layer.raw.copy()
                if tint_phase:
                    color = 255 - abs(tint_phase * 24)
                    engine.fill(source, (color, color, color), None, engine.BLEND_RGB_MULT)
                variant = self._android_prepare_cached_surface(source)
                layer.variants[tint_phase] = variant
        return variant

    @staticmethod
    def _android_prepare_cached_surface(source):
        """Prepare an immutable Android UI layer without changing its pixels.

        SDL's fast paths depend on the source format.  A SRCALPHA surface that
        happens to be fully opaque still takes the alpha path on Android, so
        copy it once to an opaque display surface.  Binary transparent pixels
        can use a non-conflicting colorkey and RLE.  Any semi-transparent or
        globally-alpha layer must stay on the exact alpha path.
        """
        if not source.get_flags() & pygame.SRCALPHA:
            colorkey = source.get_colorkey()
            if colorkey is None:
                return source
            prepared = source.copy()
            engine.set_colorkey(prepared, tuple(colorkey)[:3], rleaccel=True)
            return prepared

        if source.get_alpha() not in (None, 255):
            return source

        visible_colors = set()
        has_transparent_pixels = False
        for y in range(source.get_height()):
            for x in range(source.get_width()):
                pixel = source.get_at((x, y))
                if pixel.a not in (0, 255):
                    return source
                if pixel.a:
                    visible_colors.add((pixel.r, pixel.g, pixel.b))
                else:
                    has_transparent_pixels = True

        if not has_transparent_pixels:
            prepared = engine.create_surface(source.get_size())
            prepared.blit(source, (0, 0))
            return prepared

        for colorkey in (COLORKEY, (255, 0, 255), (0, 255, 0), (1, 2, 3)):
            if colorkey not in visible_colors:
                prepared = engine.create_surface(source.get_size())
                engine.fill(prepared, colorkey)
                prepared.blit(source, (0, 0))
                engine.set_colorkey(prepared, colorkey, rleaccel=True)
                return prepared
        return source

    def _draw_android_advantage_arrows(self, surf, left_x, left_y, right_x, crit, tint_phase):
        if self.left_item:
            layer = self._android_advantage_arrow_layer(self.left, self.right, self.left_item, self.right_item)
            if layer:
                surf.blit(self._android_layer_variant(layer, tint_phase), (left_x + 56, left_y + 10 + crit))
        if self.right_item:
            layer = self._android_advantage_arrow_layer(self.right, self.left, self.right_item, self.left_item)
            if layer:
                surf.blit(self._android_layer_variant(layer, tint_phase), (right_x + 12, left_y + 10 + crit))

    def _android_advantage_arrow_layer(self, attacker, defender, weapon, def_weapon):
        direction = self._android_advantage_direction(attacker, defender, weapon, def_weapon)
        if direction is None:
            return None
        cache = getattr(self, '_android_arrow_layers', None)
        if cache is None:
            cache = self._android_arrow_layers = OrderedDict()
        key = (direction, ANIMATION_COUNTERS.arrow_counter.count)
        layer = cache.get(key)
        if layer is None:
            with RUNTIME_PROFILER.section('combat_ui_cache_build'):
                y = 0 if direction == 'up' else 10
                raw = engine.subsurface(SPRITES.get('arrow_advantage'), (key[1] * 7, y, 7, 10)).copy()
                layer = _AndroidCombatUILayer(raw)
                cache[key] = layer
                while len(cache) > 6:
                    cache.popitem(last=False)
        else:
            cache.move_to_end(key)
        return layer

    @staticmethod
    def _android_advantage_direction(attacker, defender, weapon, def_weapon):
        if not skill_system.check_enemy(attacker, defender):
            return None
        if item_system.show_weapon_advantage(attacker, weapon, defender, def_weapon):
            return 'up'
        if item_system.show_weapon_disadvantage(attacker, weapon, defender, def_weapon):
            return 'down'
        advantage = combat_calcs.compute_advantage(attacker, defender, weapon, def_weapon)
        disadvantage = combat_calcs.compute_advantage(attacker, defender, weapon, def_weapon, False)
        if advantage and advantage.modification > 0:
            return 'up'
        if advantage and advantage.modification < 0:
            return 'down'
        if disadvantage and disadvantage.modification > 0:
            return 'down'
        if disadvantage and disadvantage.modification < 0:
            return 'up'
        return None

    def draw_item(self, surf, item, other_item, unit, other, topleft):
        self._draw_item_icon(surf, item, other_item, unit, other, topleft)

        if skill_system.check_enemy(unit, other):
            game.ui_view.draw_adv_arrows(surf, unit, other, item, other_item, (topleft[0] + 11, topleft[1] + 8))

    @staticmethod
    def _draw_item_icon(surf, item, other_item, unit, other, topleft):
        icon = icons.get_icon(item)
        if icon:
            icon = item_system.item_icon_mod(unit, item, other, other_item, icon)
            surf.blit(icon, (topleft[0] + 2, topleft[1] + 4))

    def draw_stats(self, surf, stats, topright):
        right, top = topright

        hit = '--'
        damage = '--'
        crit = '--'
        if stats is not None:
            if stats[0] is not None:
                hit = str(utils.clamp(stats[0], 0, 100))
            if stats[1] is not None:
                damage = str(stats[1])
            if DB.constants.value('crit') and stats[2] is not None:
                crit = str(utils.clamp(stats[2], 0, 100))
        FONT['number_small2'].blit_right(hit, surf, (right, top))
        FONT['number_small2'].blit_right(damage, surf, (right, top + 8))
        if DB.constants.value('crit'):
            FONT['number_small2'].blit_right(crit, surf, (right, top + 16))

    def clean_up0(self):
        """
        This clean up function is called within the update loop (so while still showing combat)
        Handles combat death, miracle, etc.
        """
        all_units = self._all_units()

        # Handle death
        for unit in all_units:
            if unit.get_hp() <= 0:
                game.death.should_die(unit)

        self._delay_death = self.combat_death_should_trigger(all_units)

    def clean_up1(self):
        """
        This clean up function is called within the update loop (so while still showing combat)
        Handles exp, & wexp, etc.
        """
        all_units = self._all_units()

        # Handle changing the sprite back
        for unit in all_units:
            if unit.get_hp() > 0:
                unit.sprite.change_state('normal')

        self.cleanup_combat()

        self.handle_unusable_items()
        self.handle_broken_items()
        
        # handle wexp & skills
        if not self.attacker.is_dying:
            self.handle_wexp(self.attacker, self.main_item, self.defender)

        if DB.constants.value('pairup') and self.main_item:
            if self.attacker.strike_partner:
                self.handle_wexp(self.attacker.strike_partner, self.main_item, self.defender)
            if self.attacker.traveler:
                self.handle_wexp(game.get_unit(self.attacker.traveler), self.main_item, self.defender)

        if self.defender and self.def_item and not self.defender.is_dying:
            self.handle_wexp(self.defender, self.def_item, self.attacker)

        if DB.constants.value('pairup') and self.def_item:
            if self.defender and self.defender.strike_partner:
                self.handle_wexp(self.defender.strike_partner, self.def_item, self.attacker)
            if self.defender and self.defender.traveler:
                self.handle_wexp(game.get_unit(self.defender.traveler), self.def_item, self.attacker)

        self.handle_mana(all_units)
        self.handle_exp(self)

        game.events.trigger(triggers.BeforeCombatEnd(self.attacker, self.defender, self.attacker.position, self.main_item, self.full_playback))

    def clean_up2(self):
        """
        This clean up function handles updates done after combat stops being shown.
        """
        all_units = self._all_units()
        
        game.state.back()

        # attacker has attacked
        action.do(action.HasAttacked(self.attacker))
        
        self.handle_records(self.full_playback, all_units)

        self.handle_messages()
        self.turnwheel_death_messages(all_units)

        self.handle_state_stack()

        game.events.trigger(triggers.CombatEnd(self.attacker, self.defender, self.attacker.position, self.main_item, self.full_playback))

        self.handle_item_gain(all_units)

        pairs = self.handle_supports(all_units)
        self.handle_support_pairs(pairs)

        self.end_combat()

        self.handle_death(all_units)

        self.attacker.built_guard = True
        if self.defender:
            self.defender.built_guard = True

        # Clean up battle anims so we can re-use them later
        self.left_battle_anim.reset_unit()
        if self.lp_battle_anim:
            self.lp_battle_anim.reset_unit()
        self.right_battle_anim.reset_unit()
        if self.rp_battle_anim:
            self.rp_battle_anim.reset_unit()

    def handle_state_stack(self):
        """
        Map combat has the implementation I want of this, so let's just use it
        """
        MapCombat.handle_state_stack(self)

    def handle_support_pairs(self, pairs):
        """
        Map combat has the implementation I want of this, so let's just use it
        """
        MapCombat.handle_support_pairs(self, pairs)

    def combat_death_should_trigger(self, units) -> bool:
        """
        Check if combat_death trigger should trigger on any units dying
        """
        for unit in units:
            if unit.is_dying:
                # Find the killer
                marks = [mark for mark in self.full_playback if mark.nid in ('mark_miss', 'mark_hit', 'mark_crit')]
                killer = None
                for mark in marks:
                    if mark.defender == unit:
                        killer = mark.attacker
                        break
                if game.events.should_trigger(triggers.CombatDeath(unit, killer, unit.position)):
                    return True
        return False
