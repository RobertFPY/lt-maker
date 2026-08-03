from __future__ import annotations

import logging
from typing import List, Optional, Tuple, TYPE_CHECKING

from app.constants import WINHEIGHT, WINWIDTH
from app.data.database.database import DB
from app.data.resources.portraits import INFO_PORTRAIT_WIDTH, INFO_PORTRAIT_HEIGHT
from app.data.resources.resources import RESOURCES
from app.engine import (background, combat_calcs, engine, equations, gui,
                        help_menu, icons, image_mods, item_funcs, item_system,
                        skill_system, text_funcs, unit_funcs)
from app.engine.fluid_scroll import FluidScroll
from app.engine.android_runtime import is_android_render_optimization_enabled
from app.engine.game_menus.icon_options import BasicItemOption, BasicCostumeOption
from app.engine.game_menus.uses_display_config import ItemOptionModes
from app.engine.game_state import game
from app.engine.graphics.ingame_ui.build_groove import build_groove
from app.engine.graphics.text.text_renderer import render_text, text_width
from app.engine.info_menu.info_graph import InfoGraph, info_states
from app.engine.info_menu.info_menu_portrait import InfoMenuPortrait
from app.engine.input_manager import get_input_manager
from app.engine.objects.unit import UnitObject
from app.engine.performance import RUNTIME_PROFILER
from app.engine.sound import get_sound_thread
from app.engine.sprites import SPRITES
from app.engine.state import State
from app.engine.text_evaluator import TextEvaluator
from app.utilities import utils
from app.utilities.enums import HAlignment
from app.engine.fonts import FONT
from app.engine.info_menu.multi_desc import PageType, build_dialog_list
from app.events import triggers

if TYPE_CHECKING:
    from app.engine.objects.item import ItemObject

class InfoMenuState(State):
    name = 'info_menu'
    in_level = False
    show_map = False 

    def _init(self):
        """
        Determines which stats are left stats, right stats, and/or hidden stats
        for use when drawing within this state.

        Necessary to wrap this in a function that's called when the info menu starts up
        because otherwise starting up the info menu, then changing the stat nids, and then
        starting up the info menu again will break which stats are actually available
        """
        left_stats = [stat.nid for stat in DB.stats if stat.position == 'left']
        if len(left_stats) >= 7:
            _extra_stat_row = True
            # If we have 7 or more left stats, use 7 rows
            right_stats = left_stats[7:]
        else:  # Otherwise, just use the 6 rows
            _extra_stat_row = False
            right_stats = left_stats[6:]
        right_stats += [stat.nid for stat in DB.stats if stat.position == 'right']
        # Make sure we only display up to 6 or 7 on each
        if _extra_stat_row:
            left_stats = left_stats[:7]
            right_stats = right_stats[:7]
        else:
            left_stats = left_stats[:6]
            right_stats = right_stats[:6]
        self._extra_stat_row = _extra_stat_row
        self.left_stats = left_stats
        self.right_stats = right_stats

    def create_background(self):
        self.unit: UnitObject = game.memory.get('current_unit')
        if self.unit.team == 'player':
            panorama = RESOURCES.panoramas.get('info_menu_background')
        elif self.unit.team == 'enemy':
            panorama = RESOURCES.panoramas.get('info_menu_background_enemy')
        elif self.unit.team == 'other':
            panorama = RESOURCES.panoramas.get('info_menu_background_npc')
        if not panorama:
            panorama = RESOURCES.panoramas.get('default_background')
        if panorama:
            self.bg = background.PanoramaBackground(panorama)
        else:
            self.bg = None

    def start(self):
        self._init()
        self.mouse_indicator = gui.MouseIndicator()
        self.create_background()

        # Unit to be displayed
        self.unit: UnitObject = game.memory.get('current_unit')
        self.scroll_units = game.memory.get('scroll_units')
        if self.scroll_units is None:
            self.scroll_units = [unit for unit in game.units if not unit.dead and unit.team == self.unit.team and unit.party == self.unit.party]
            if self.unit.position:
                self.scroll_units = [unit for unit in self.scroll_units if unit.position and game.board.in_vision(unit.position)]
        self.scroll_units = [unit for unit in self.scroll_units if 'Tile' not in unit.tags]
        game.memory['scroll_units'] = None

        self.state = game.memory.get('info_menu_state', info_states[0])
        if self.state == 'notes' and not (DB.constants.value('unit_notes') and self.unit.notes):
            self.state = 'personal_data'
        self.growth_flag = False
        self.equipment_section = item_funcs.InventorySection.WEAPON
        self.support_skills_section = 'weapon'

        self.fluid = FluidScroll(200, 1)

        self.build_arrows()

        self.logo = None
        self.switch_logo(self.state)

        self.info_graph = InfoGraph()
        self.info_flag = False
        self.info_graph.set_current_state(self.state)
        self.reset_surfs()

        # For transitions between states
        self.rescuer = None  # Keeps track of the rescuer if we are looking at the traveler
        self.next_unit = None
        self.next_state = None
        self.scroll_offset_x = 0
        self.scroll_offset_y = 0
        self.transition = None
        self.transition_counter = 0
        self.transparency = 0

        # Fire the on_info_menu_start event trigger once the menu is interactive.
        self._info_start_triggered = False

        game.state.change('transition_in')
        return 'repeat'

    def begin(self):
        self.fluid.reset_on_change_state()
        # Fire on_info_menu_start once the open transition has finished.
        if not self._info_start_triggered and not self.transition:
            self._info_start_triggered = True
            game.events.trigger(triggers.OnInfoMenuStart(self.unit, self.state))

    def reset_surfs(self, keep_last_info_graph_aabb=False):
        self.info_graph.clear(keep_last_aabb=keep_last_info_graph_aabb)
        self.portrait_surf = None
        self.current_portrait = None
        self._android_portrait_cache = None
        self._android_portrait_cache_key = None

        self.personal_data_surf: engine.Surface = None
        self.growths_surf: engine.Surface = None
        self.wexp_surf: engine.Surface = None
        self.equipment_surf: engine.Surface = None
        self.support_surf: engine.Surface = None
        self.skill_surf: engine.Surface = None
        self.skill_icon_layout = []
        self.class_skill_surf: engine.Surface = None
        self.fatigue_surf: engine.Surface = None
        self.notes_surf: engine.Surface = None
        self.spellbook_surf: engine.Surface = None

    def build_arrows(self):
        self.left_arrow = gui.ScrollArrow('left', (103, 3))
        self.right_arrow = gui.ScrollArrow('right', (217, 3), 0.5)

    def switch_logo(self, name):
        if name == 'personal_data':
            image = SPRITES.get('info_title_personal_data')
        elif name == 'equipment':
            image = SPRITES.get('info_title_items')
        elif name == 'support_skills':
            image = SPRITES.get('info_title_weapon')
        elif name == 'skills':
            image = SPRITES.get('info_title_skills')
        elif name == 'notes':
            image = SPRITES.get('info_title_notes')
        elif name == 'spellbook':
            # Custom title sprite for the spell loadout page; fall back to the
            # items title if the dedicated sprite has not been added yet.
            image = SPRITES.get('info_title_spellbook') or SPRITES.get('info_title_items')
        else:
            return
        if self.logo:
            self.logo.switch_image(image)
        else:
            self.logo = gui.Logo(image, (164, 10))

    def back(self):
        get_sound_thread().play_sfx('Select 4')
        game.memory['info_menu_state'] = self.state
        game.memory['current_unit'] = self.unit
        if self.unit.position and not game.is_roam():
            # Move camera to the new character unless it's a free roam, in which case we just stay on the free roamer
            game.cursor.set_pos(self.unit.position)
        game.state.change('transition_pop')

    def take_input(self, event):
        first_push = self.fluid.update()
        directions = self.fluid.get_directions()

        self.handle_mouse()
        if self.info_flag:
            if event in ('INFO', 'BACK'):
                get_sound_thread().play_sfx('Info Out')
                self.info_graph.set_transition_out()
                self.info_flag = False
                return
            
            if event == 'AUX':
                self.info_graph.switch_info()
                get_sound_thread().play_sfx('Select 6')

            if 'RIGHT' in directions:
                if self.info_graph.move_right():
                    get_sound_thread().play_sfx('Select 6')
            elif 'LEFT' in directions:
                if self.info_graph.move_left():
                    get_sound_thread().play_sfx('Select 6')
            elif 'UP' in directions:
                if self.info_graph.move_up():
                    get_sound_thread().play_sfx('Select 6')
            elif 'DOWN' in directions:
                if self.info_graph.move_down():
                    get_sound_thread().play_sfx('Select 6')

        elif not self.transition:  # Only takes input when not transitioning
            if event == 'INFO':
                get_sound_thread().play_sfx('Info In')
                self.info_graph.set_transition_in()
                self.info_flag = True
                return
            elif event == 'AUX':
                if self.state == 'personal_data' and self.unit.team == 'player' and DB.constants.value('growth_info'):
                    get_sound_thread().play_sfx('Select 3')
                    self.growth_flag = not self.growth_flag
                    if self.growth_flag:
                        self.info_graph.set_current_state('growths')
                    else:
                        self.info_graph.set_current_state('personal_data')
                elif self.state == 'equipment' and item_funcs.split_inventory_enabled():
                    get_sound_thread().play_sfx('Select 3')
                    self.equipment_section = (
                        item_funcs.InventorySection.ITEM
                        if self.equipment_section == item_funcs.InventorySection.WEAPON
                        else item_funcs.InventorySection.WEAPON)
                    self.reset_surfs()
                    self.info_graph.set_current_state('equipment')
                elif self.state == 'support_skills' and game.game_vars.get('_supports'):
                    get_sound_thread().play_sfx('Select 3')
                    self.support_skills_section = (
                        'support'
                        if self.support_skills_section == 'weapon'
                        else 'weapon')
                    self.reset_surfs()
                    self.info_graph.set_current_state('support_skills')
            elif event == 'BACK':
                if self.rescuer:
                    self.move_up()
                else:
                    self.back()
                    return
            elif event == 'SELECT':
                mouse_position = get_input_manager().get_mouse_position()
                if mouse_position:
                    mouse_x, mouse_y = mouse_position
                    if mouse_x <= 16:
                        self.move_left()
                    elif mouse_x >= WINWIDTH - 16:
                        self.move_right()
                    elif mouse_y <= 16:
                        self.move_up()
                    elif mouse_y >= WINHEIGHT - 16:
                        self.move_down()
                if not self.transition:  # Some of the above move commands could cause transition
                    if self.unit.traveler:
                        self.move_traveler()

            if 'RIGHT' in directions:
                self.move_right()
            elif 'LEFT' in directions:
                self.move_left()
            elif 'DOWN' in directions:
                self.move_down()
            elif 'UP' in directions:
                self.move_up()

    def _get_spell_loadout_items(self, unit) -> List['ItemObject']:
        """Materialize the spell items stored in the unit's 'spell_loadout' field.

        Reuses the same loadout machinery as the Attack/Spell menus (target_system)
        so the items here are the exact same ItemObjects, and are never duplicated.
        """
        if not hasattr(unit, 'get_field'):
            return []
        loadout = unit.get_field('spell_loadout')
        if not loadout:
            return []
        catalog = DB.raw_data.get('MariSpell')
        spell_nids = {row.nid for row in catalog} if catalog else None
        loadout_nids = [nid for nid in loadout if (spell_nids is None or nid in spell_nids)]
        return game.target_system._get_mari_loadout_items(unit, loadout_nids)

    def _has_spell_loadout(self, unit=None) -> bool:
        """The spellbook page is only available when the unit has a non-empty spell loadout."""
        unit = unit or self.unit
        return bool(self._get_spell_loadout_items(unit))

    def get_available_states(self) -> List[str]:
        """The pages reachable for the current unit.

        'notes' is only shown when the unit actually has notes (matching the page
        counter), and 'spellbook' is only shown when the unit has a spell loadout.
        """
        states = []
        for state in info_states:
            if state == 'notes':
                if DB.constants.value('unit_notes') and self.unit.notes:
                    states.append(state)
            elif state == 'spellbook':
                if self._has_spell_loadout():
                    states.append(state)
            else:
                states.append(state)
        return states

    def move_left(self):
        states = self.get_available_states()
        if len(states) > 1:
            get_sound_thread().play_sfx('Status_Page_Change')
            index = states.index(self.state) if self.state in states else 0
            new_index = (index - 1) % len(states)
            self.next_state = states[new_index]
            self.info_graph.last_bb = None
            self.transition = 'LEFT'
            self.left_arrow.pulse()
            self.switch_logo(self.next_state)

    def move_right(self):
        states = self.get_available_states()
        if len(states) > 1:
            get_sound_thread().play_sfx('Status_Page_Change')
            index = states.index(self.state) if self.state in states else 0
            new_index = (index + 1) % len(states)
            self.next_state = states[new_index]
            self.info_graph.last_bb = None
            self.transition = 'RIGHT'
            self.right_arrow.pulse()
            self.switch_logo(self.next_state)

    def move_down(self):
        get_sound_thread().play_sfx('Status_Character')
        if self.rescuer:
            new_index = self.scroll_units.index(self.rescuer)
            self.rescuer = None
        elif len(self.scroll_units) > 1:
            index = self.scroll_units.index(self.unit)
            new_index = (index + 1) % len(self.scroll_units)
        else:
            return
        self.next_unit = self.scroll_units[new_index]
        self.transition = 'UP'

    def move_up(self):
        get_sound_thread().play_sfx('Status_Character')
        if self.rescuer:
            new_index = self.scroll_units.index(self.rescuer)
            self.rescuer = None
        elif len(self.scroll_units) > 1:
            index = self.scroll_units.index(self.unit)
            new_index = (index - 1) % len(self.scroll_units)
        else:
            return
        self.next_unit = self.scroll_units[new_index]
        self.transition = 'DOWN'

    def move_traveler(self):
        get_sound_thread().play_sfx('Status_Character')
        self.rescuer = self.unit
        self.next_unit = game.get_unit(self.unit.traveler)
        if self.state == 'notes' and not (DB.constants.value('unit_notes') and self.next_unit.notes):
            self.state = 'personal_data'
            self.switch_logo('personal_data')
        self.transition = 'DOWN'

    def handle_mouse(self):
        mouse_position = get_input_manager().get_mouse_position()
        if not mouse_position:
            return
        if self.info_flag:
            self.info_graph.handle_mouse(mouse_position)

    def update(self):
        if self.info_flag:
            self.info_graph.update()
        # Up and Down
        if self.next_unit:
            self.transition_counter += 1
            # Transition in
            if self.next_unit == self.unit:
                if self.transition_counter == 1:
                    self.transparency = .75
                    self.scroll_offset_y = -80 if self.transition == 'DOWN' else 80
                elif self.transition_counter == 2:
                    self.transparency = .6
                    self.scroll_offset_y = -32 if self.transition == 'DOWN' else 32
                elif self.transition_counter == 3:
                    self.transparency = .48
                    self.scroll_offset_y = -16 if self.transition == 'DOWN' else 16
                elif self.transition_counter == 4:
                    self.transparency = .15
                    self.scroll_offset_y = -4 if self.transition == 'DOWN' else 4
                elif self.transition_counter == 5:
                    self.scroll_offset_y = 0
                else:
                    self.transition = None
                    self.transparency = 0
                    self.next_unit = None
                    self.transition_counter = 0
            # Transition out
            else:
                if self.transition_counter == 1:
                    self.transparency = .15
                elif self.transition_counter == 2:
                    self.transparency = .48
                elif self.transition_counter == 3:
                    self.transparency = .6
                    self.scroll_offset_y = 8 if self.transition == 'DOWN' else -8
                elif self.transition_counter == 4:
                    self.transparency = .75
                    self.scroll_offset_y = 16 if self.transition == 'DOWN' else -16
                elif self.transition_counter < 8: # (5, 6, 7, 8):  # Pause for a bit
                    self.transparency = 1.
                    self.scroll_offset_y = 160 if self.transition == 'DOWN' else -160
                else:
                    self.unit = self.next_unit  # Now transition in
                    self.reset_surfs(keep_last_info_graph_aabb=True)
                    self.transition_counter = 0
                    # The new unit may not have the current page (e.g. spellbook
                    # or notes), so fall back to a page that is always available.
                    if self.state not in self.get_available_states():
                        self.state = 'personal_data'
                        self.info_graph.set_current_state(self.state)
                        self.switch_logo(self.state)

        # Left and Right
        elif self.next_state is not None:
            self.transition_counter += 1
            # Transition in
            if self.next_state == self.state:
                idxs = (104, 72, 56, 40, 24, 8)
                counter = self.transition_counter - 1
                if 0 <= counter < len(idxs):
                    self.scroll_offset_x = idxs[counter] if self.transition == 'RIGHT' else -idxs[counter]
                else:
                    self.transition = None
                    self.scroll_offset_x = 0
                    self.next_state = None
                    self.transition_counter = 0
                    game.events.trigger(triggers.OnInfoMenuOn(self.unit, self.state))
            else:
                idxs = (-32, -56, -80, -96, -112)
                counter = self.transition_counter - 1
                if 0 <= counter < len(idxs):
                    self.scroll_offset_x = idxs[counter] if self.transition == 'RIGHT' else -idxs[counter]
                else:
                    self.scroll_offset_x = -140 if self.transition == 'RIGHT' else 140
                    self.state = self.next_state
                    self.info_graph.set_current_state(self.state)
                    self.transition_counter = 0

    def draw(self, surf):
        with RUNTIME_PROFILER.section('info_background'):
            if self.bg:
                self.bg.draw(surf)
            else:
                # info menu shouldn't be transparent
                surf.blit(SPRITES.get('bg_black'), (0, 0))

        # Image flashy thing at the top of the InfoMenu
        with RUNTIME_PROFILER.section('info_flash'):
            num_frames = 8
            # 8 frames long, 8 different frames
            blend_perc = abs(num_frames - ((engine.get_time()/134) % (num_frames * 2))) / float(num_frames)
            sprite = SPRITES.get('info_menu_flash')
            im = image_mods.make_translucent_blend(sprite, 128. * blend_perc)
            surf.blit(im, (98, 0), None, engine.BLEND_RGB_ADD)

        with RUNTIME_PROFILER.section('info_portrait'):
            self.draw_portrait(surf)
        with RUNTIME_PROFILER.section('info_slide'):
            self.draw_slide(surf)

        if self.info_graph.current_bb:
            with RUNTIME_PROFILER.section('info_graph'):
                self.info_graph.draw(surf)

        if not self.transition:
            with RUNTIME_PROFILER.section('info_mouse'):
                self.mouse_indicator.draw(surf)

        return surf

    def draw_portrait(self, surf):
        # Only create if we don't have one in memory
        if not self.portrait_surf:
            self.portrait_surf = self.create_portrait_section()
        steady = not self.transparency and not self.scroll_offset_y
        if steady:
            portrait_surf = None
        else:
            portrait_surf = self.portrait_surf.copy()

        # If no portrait for this unit, either create one or default to class card using icons.get_portrait
        if not self.current_portrait:
            portrait = RESOURCES.portraits.get(self.unit.portrait_nid)
            if portrait:
                self.current_portrait = InfoMenuPortrait(portrait, DB.constants.value('info_menu_blink'))
            else:
                im, offset = icons.get_portrait(self.unit)
        # We do have a portrait, so update...
        if self.current_portrait:
            self.current_portrait.update()
            im = self.current_portrait.create_image()
            offset = self.current_portrait.portrait.get_info_coord()
        if steady and not im:
            # Class-card fallback may deliberately return no portrait image;
            # retain the static left panel in that case.
            surf.blit(self.portrait_surf, (0, 0))

        # Draw portrait onto the portrait surf
        if im:
            im_surf = engine.subsurface(im, (*offset, INFO_PORTRAIT_WIDTH, INFO_PORTRAIT_HEIGHT))
            portrait_pos = (
                8 + (INFO_PORTRAIT_WIDTH - im_surf.get_width()) // 2,
                8 + (INFO_PORTRAIT_HEIGHT - im_surf.get_height()) // 2,
            )
            if steady:
                if is_android_render_optimization_enabled():
                    cache_key = (id(self.portrait_surf), id(im), portrait_pos)
                    if cache_key != getattr(self, '_android_portrait_cache_key', None):
                        self._android_portrait_cache = self.portrait_surf.copy()
                        self._android_portrait_cache.blit(im_surf, portrait_pos)
                        self._android_portrait_cache_key = cache_key
                    surf.blit(self._android_portrait_cache, (0, 0))
                else:
                    surf.blit(self.portrait_surf, (0, 0))
                    surf.blit(im_surf, portrait_pos)
            else:
                portrait_surf.blit(im_surf, portrait_pos)

        # Stick it on the surface
        if steady:
            pass
        elif self.transparency:
            im = image_mods.make_translucent(portrait_surf, self.transparency)
            surf.blit(im, (0, self.scroll_offset_y))
        else:
            surf.blit(portrait_surf, (0, self.scroll_offset_y))

        # Blit the unit's active/focus map sprite
        if not self.transparency:
            active_sprite = self.unit.sprite.create_image('active', copy=False)
            x_pos = 81 - active_sprite.get_width()//2
            y_pos = WINHEIGHT - 61
            surf.blit(active_sprite, (x_pos, y_pos + self.scroll_offset_y))

    def growth_colors(self, value):
        color = 'yellow'
        if value >= 0 and value <= 20:
            color = 'red-orange'
        elif value > 20 and value <= 30:
            color = 'light-red'
        elif value > 30 and value <= 40:
            color = 'pink-orange'
        elif value > 40 and value <= 50:
            color = 'light-orange'
        elif value > 50 and value <= 60:
            color = 'corn-yellow'
        elif value > 60 and value <= 70:
            color = 'light-green'
        elif value > 70 and value <= 80:
            color = 'olive-green'
        elif value > 80 and value <= 90:
            color = 'soft-green'
        else:  # > 90
            color = 'yellow-green'
        return color

    def create_portrait_section(self):
        def create_item_option(idx, item):
            return BasicCostumeOption.from_item(idx, item, width=120, mode=ItemOptionModes.FULL_USES, text_color=item_system.text_color(None, item))
        surf = engine.create_surface((96, WINHEIGHT), transparent=True)
        surf.blit(SPRITES.get('info_unit'), (8, 122))

        accessory = self.unit.get_accessory()

        render_text(surf, ['text'], [self.unit.name], ['white'], (48, 80), HAlignment.CENTER)
        unit_desc = text_funcs.translate_and_text_evaluate(self.unit.desc, self=self.unit, unit=self.unit)
        self.info_graph.register((24, 80, 52, 24), unit_desc, 'all')
        class_obj = DB.classes.get(self.unit.klass)
        render_text(surf, ['text'], [class_obj.name], ['white'], (8, 104))
        class_desc = text_funcs.translate_and_text_evaluate(class_obj.desc, self=class_obj, unit=self.unit)
        self.info_graph.register((8, 104, 72, 16), class_desc, 'all')
        render_text(surf, ['text'], [str(self.unit.level)], ['blue'], (39, 120), HAlignment.RIGHT)
        desc = text_funcs.translate_and_text_evaluate('Level_desc', unit=self.unit)
        self.info_graph.register((8, 120, 30, 16), desc, 'all')
        render_text(surf, ['text'], [str(self.unit.exp)], ['blue'], (63, 120), HAlignment.RIGHT)
        desc = text_funcs.translate_and_text_evaluate('Exp_desc', unit=self.unit)
        self.info_graph.register((38, 120, 30, 16), desc, 'all')
        
        # Draw HP
        current_hp = str(self.unit.get_hp())
        max_hp = str(self.unit.get_max_hp())
        # 14 pixels is width of space available to draw current_hp or max_hp
        if text_width('text', current_hp) > 14 or text_width('text', max_hp) > 14:
            hp_font = 'narrow'
        else:
            hp_font = 'text'
        render_text(surf, [hp_font], [current_hp], ['blue'], (39, 136), HAlignment.RIGHT)
        desc = text_funcs.translate_and_text_evaluate('HP_desc', unit=self.unit)
        self.info_graph.register((8, 136, 72, 16), desc, 'all')
        render_text(surf, [hp_font], [str(max_hp)], ['blue'], (63, 136), HAlignment.RIGHT)

        # Blit the white status platform
        surf.blit(SPRITES.get('status_platform'), (66, 131))
        # Blit affinity
        affinity = DB.affinities.get(self.unit.affinity)
        if affinity:
            icons.draw_item(surf, affinity, (78, 81))
            affinity_desc = text_funcs.translate_and_text_evaluate(affinity.desc, self=affinity, unit=self.unit)
            self.info_graph.register((76, 80, 16, 16), affinity_desc, 'all')

        # Blit accessories
        if accessory:
            for idx, item in enumerate(self.unit.accessories):
                aidx = item_funcs.get_num_weapons(self.unit) + item_funcs.get_num_items(self.unit) + idx
                y_pos = 81
                equipped_subitem: Optional[ItemObject] = None
                if item.multi_item and any(subitem is accessory for subitem in item.subitems):
                    for subitem in item.subitems:
                        if subitem is accessory:
                            equipped_subitem = subitem
                            item_option = create_item_option(aidx, subitem)
                            break
                    else:  # Shouldn't happen
                        item_option = create_item_option(aidx, item)
                else:
                    item_option = create_item_option(aidx, item)
                item_option.draw(surf, 5, y_pos)
                first = (idx == 0 and not self.unit.nonaccessories)
                help_dlg = build_dialog_list(equipped_subitem if equipped_subitem else item, PageType.ITEM, unit=self.unit)
                self.info_graph.register((5, y_pos, 120, 16), help_dlg, 'all', first=first)
        else:
            self.info_graph.register((5, 81, 120, 16), 'Costume', 'all')

        return surf

    def draw_top_arrows(self, surf):
        self.left_arrow.draw(surf)
        self.right_arrow.draw(surf)

    def _draw_slide_header(self, surf):
        # Blit title of menu
        surf.blit(SPRITES.get('info_title_background'), (112, 8))
        if self.logo:
            self.logo.update()
            self.logo.draw(surf)
        # Blit page numbers
        states = self.get_available_states()
        num_states = len(states)
        current_index = states.index(self.state) if self.state in states else 0
        page = str(current_index + 1) + '/' + str(num_states)
        typeface = 'number_small4' if 'number_small4' in FONT else 'small'
        render_text(surf, [typeface], [page], [], (236, 13), HAlignment.RIGHT)

        if num_states > 1:
            self.draw_top_arrows(surf)

    def draw_slide(self, surf):
        steady = (
            not self.transparency and not self.scroll_offset_x
            and not self.scroll_offset_y
        )
        if steady:
            # The background and portrait have already refreshed the final
            # frame. Draw cached page pieces directly onto it. This avoids two
            # full-screen SRCALPHA surfaces and their alpha blits every frame.
            main_surf = surf
            top_surf = None
        else:
            top_surf = engine.create_surface((WINWIDTH, WINHEIGHT), transparent=True)
            main_surf = engine.copy_surface(top_surf)
            self._draw_slide_header(top_surf)

        if self.state == 'personal_data':
            if self.growth_flag:
                if not self.growths_surf:
                    self.growths_surf = self.create_personal_data_surf(growths=True)
                self.draw_growths_surf(main_surf)
            else:
                if not self.personal_data_surf:
                    self.personal_data_surf = self.create_personal_data_surf()
                with RUNTIME_PROFILER.section('info_stats'):
                    self.draw_stat_surf(self.personal_data_surf)
                self.draw_personal_data_surf(main_surf)
            if DB.constants.value('fatigue') and self.unit.team == 'player' and \
                    game.game_vars.get('_fatigue'):
                if not self.fatigue_surf:
                    self.fatigue_surf = self.create_fatigue_surf()
                self.draw_fatigue_surf(main_surf)

        elif self.state == 'equipment':
            if not self.equipment_surf:
                self.equipment_surf = self.create_equipment_surf()
            self.draw_equipment_surf(main_surf)

        elif self.state == 'support_skills':
            main_surf.blit(SPRITES.get('status_logo'), (100, WINHEIGHT - 42))
            self.draw_support_skills_tabs(main_surf)
            if not self.skill_surf:
                self.skill_surf = self.create_skill_surf()
            self.draw_skill_surf(main_surf)
            if self.support_skills_section == 'support' and game.game_vars.get('_supports'):
                if not self.support_surf:
                    self.support_surf = self.create_support_surf()
                self.draw_support_surf(main_surf)
            else:
                if not self.wexp_surf:
                    self.wexp_surf = self.create_wexp_surf()
                self.draw_wexp_surf(main_surf)

        elif self.state == 'skills':
            if not self.class_skill_surf:
                self.class_skill_surf = self.create_class_skill_surf()
            self.draw_class_skill_surf(main_surf)

        elif self.state == 'notes':
            if not self.notes_surf:
                self.notes_surf = self.create_notes_surf()
            self.draw_notes_surf(main_surf)
        elif self.state == 'spellbook':
            if not self.spellbook_surf:
                self.spellbook_surf = self.create_spellbook_surf()
            self.draw_spellbook_surf(main_surf)

        if steady:
            # Header is the topmost layer in the established composition order.
            self._draw_slide_header(surf)
            return

        # Now put it in the right place
        offset_x = max(96, 96 - self.scroll_offset_x)
        main_surf = engine.subsurface(main_surf, (offset_x, 0, main_surf.get_width() - offset_x, WINHEIGHT))
        surf.blit(main_surf, (max(96, 96 + self.scroll_offset_x), self.scroll_offset_y))
        if self.transparency:
            top_surf = image_mods.make_translucent(top_surf, self.transparency)
        surf.blit(top_surf, (0, self.scroll_offset_y)) 

    def draw_stat_surf(self, surf):
        for idx, stat_nid in enumerate(self.left_stats):
            icons.draw_stat(surf, stat_nid, self.unit, (47, 16 * idx + 24))

        for idx, stat_nid in enumerate(self.right_stats):
            icons.draw_stat(surf, stat_nid, self.unit, (111, 16 * idx + 24))

    def create_personal_data_surf(self, growths=False):
        if growths:
            state = 'growths'
        else:
            state = 'personal_data'

        menu_size = WINWIDTH - 96, WINHEIGHT
        surf = engine.create_surface(menu_size, transparent=True)

        for idx, stat_nid in enumerate(self.left_stats):
            curr_stat = DB.stats.get(stat_nid)
            # Value
            if growths:
                icons.draw_growth(surf, stat_nid, self.unit, (47, 16 * idx + 24))
            else:
                highest_stat = curr_stat.maximum
                max_stat = self.unit.get_stat_cap(stat_nid)
                if max_stat > 0:
                    total_length = min(42, int(max_stat / highest_stat * 42))
                    base_value = self.unit.stats.get(stat_nid, 0)
                    subtle_stat_bonus = self.unit.subtle_stat_bonus(stat_nid)
                    base_value += subtle_stat_bonus
                    frac = utils.clamp(base_value / max_stat, 0, 1)
                    build_groove(surf, (27, 16 * idx + 32), total_length, frac)

            # Name
            name = curr_stat.name
            color = 'yellow'
            if DB.stats.get(stat_nid).growth_colors and self.unit.team == 'player':
                color = self.growth_colors(unit_funcs.growth_rate(self.unit, stat_nid))
            render_text(surf, ['text'], [name], [color], (8, 16 * idx + 24))
            if growths:
                contribution = unit_funcs.growth_contribution(self.unit, stat_nid)
            else:
                base_value = self.unit.stats.get(stat_nid, 0)
                subtle_stat_bonus = self.unit.subtle_stat_bonus(stat_nid)
                base_value += subtle_stat_bonus
                contribution = self.unit.stat_contribution(stat_nid)
                contribution['Base Value'] = base_value
            desc_text = text_funcs.translate_and_text_evaluate(curr_stat.desc, self=curr_stat, unit=self.unit)
            help_box = help_menu.StatDialog(desc_text or ('%s_desc' % stat_nid), contribution)
            self.info_graph.register((96 + 8, 16 * idx + 24, 64, 16), help_box, state, first=(idx == 0))

        for idx, stat_nid in enumerate(self.right_stats):
            curr_stat = DB.stats.get(stat_nid)

            # Name
            name = curr_stat.name
            color = 'yellow'
            if DB.stats.get(stat_nid).growth_colors and self.unit.team == 'player':
                color = self.growth_colors(unit_funcs.growth_rate(self.unit, stat_nid))
            render_text(surf, ['text'], [name], [color], (72, 16 * idx + 24))
            if growths:
                icons.draw_growth(surf, stat_nid, self.unit, (111, 16 * idx + 24))
                contribution = unit_funcs.growth_contribution(self.unit, stat_nid)
            else:
                base_value = self.unit.stats.get(stat_nid, 0)
                subtle_stat_bonus = self.unit.subtle_stat_bonus(stat_nid)
                base_value += subtle_stat_bonus
                contribution = self.unit.stat_contribution(stat_nid)
                contribution['Base Value'] = base_value
            desc_text = text_funcs.translate_and_text_evaluate(curr_stat.desc, self=curr_stat, unit=self.unit)
            help_box = help_menu.StatDialog(desc_text or ('%s_desc' % stat_nid), contribution)
            self.info_graph.register((96 + 72, 16 * idx + 24, 64, 16), help_box, state)

        other_stats = []
        if DB.constants.value('enable_rating'):
            other_stats.append('RAT')
        if DB.constants.value('talk_display'):
            other_stats.insert(0, 'TALK')
        if DB.constants.value('pairup') and DB.constants.value('attack_stance_only'):
            pass
        else:
            other_stats.insert(0, 'AID')
            other_stats.insert(0, 'TRV')
        if self.unit.get_max_mana() > 0:
            other_stats.insert(0, 'MANA')
        if DB.constants.value('pairup') and not DB.constants.value('attack_stance_only'):
            other_stats.insert(2, 'GAUGE')
        if DB.constants.value('lead'):
            other_stats.append('LEAD')

        other_stats = other_stats[:8 - len(self.right_stats)]

        for idx, stat in enumerate(other_stats):
            true_idx = idx + len(self.right_stats)

            if stat == 'TRV':
                if self.unit.traveler:
                    trav = game.get_unit(self.unit.traveler)
                    render_text(surf, ['text'], [trav.name], ['blue'], (96, 16 * true_idx + 24))
                else:
                    render_text(surf, ['text'], ['--'], ['blue'], (111, 16 * true_idx + 24), HAlignment.RIGHT)
                render_text(surf, ['text'], [text_funcs.translate('Trv')], ['yellow'], (72, 16 * true_idx + 24))
                desc = text_funcs.translate_and_text_evaluate('Trv_desc', unit=self.unit)
                self.info_graph.register((96 + 72, 16 * true_idx + 24, 64, 16), desc, state)

            elif stat == 'AID':
                if growths:
                    icons.draw_growth(surf, 'HP', self.unit, (111, 16 * true_idx + 24))
                    color = 'yellow'
                    if DB.stats.get('HP').growth_colors and self.unit.team == 'player':
                        color = self.growth_colors(unit_funcs.growth_rate(self.unit, 'HP'))
                    render_text(surf, ['text'], [text_funcs.translate('HP')], [color], (72, 16 * true_idx + 24))
                    desc = text_funcs.translate_and_text_evaluate('HP_desc', unit=self.unit)
                    self.info_graph.register((96 + 72, 16 * true_idx + 24, 64, 16), desc, state)
                else:
                    aid = equations.parser.rescue_aid(self.unit)
                    render_text(surf, ['text'], [str(aid)], ['blue'], (111, 16 * true_idx + 24), HAlignment.RIGHT)

                    # Mount Symbols
                    for tag in self.unit.tags:
                        if ('aid_icon_%s' % tag) in SPRITES:
                            aid_surf = SPRITES.get('aid_icon_%s' % tag)
                            break
                    else:
                        if 'Dragon' in self.unit.tags:
                            aid_surf = engine.subsurface(SPRITES.get('aid_icons'), (0, 48, 16, 16))
                        elif 'Flying' in self.unit.tags:
                            aid_surf = engine.subsurface(SPRITES.get('aid_icons'), (0, 32, 16, 16))
                        elif 'Mounted' in self.unit.tags:
                            aid_surf = engine.subsurface(SPRITES.get('aid_icons'), (0, 16, 16, 16))
                        else:
                            aid_surf = engine.subsurface(SPRITES.get('aid_icons'), (0, 0, 16, 16))
                    surf.blit(aid_surf, (112, 16 * true_idx + 24))
                    render_text(surf, ['text'], [text_funcs.translate('Aid')], ['yellow'], (72, 16 * true_idx + 24))
                    desc = text_funcs.translate_and_text_evaluate('Aid_desc', unit=self.unit)
                    self.info_graph.register((96 + 72, 16 * true_idx + 24, 64, 16), desc, state)

            elif stat == 'RAT':
                rat = str(equations.parser.rating(self.unit))
                render_text(surf, ['text'], [rat], ['blue'], (111, 16 * true_idx + 24), HAlignment.RIGHT)
                render_text(surf, ['text'], [text_funcs.translate('Rat')], ['yellow'], (72, 16 * true_idx + 24))
                desc = text_funcs.translate_and_text_evaluate('Rating_desc', unit=self.unit)
                self.info_graph.register((96 + 72, 16 * true_idx + 24, 64, 16), desc, state)

            elif stat == 'MANA':
                mana = str(self.unit.current_mana)
                render_text(surf, ['text'], [mana], ['blue'], (111, 16 * true_idx + 24), HAlignment.RIGHT)
                render_text(surf, ['text'], [text_funcs.translate('MANA')], ['yellow'], (72, 16 * true_idx + 24))
                desc = text_funcs.translate_and_text_evaluate('MANA_desc', unit=self.unit)
                self.info_graph.register((96 + 72, 16 * true_idx + 24, 64, 16), desc, state)

            elif stat == 'GAUGE':
                gge = str(self.unit.get_guard_gauge())
                render_text(surf, ['text'], [gge], ['blue'], (111, 16 * true_idx + 24), HAlignment.RIGHT)
                render_text(surf, ['text'], [text_funcs.translate('GAUGE')], ['yellow'], (72, 16 * true_idx + 24))
                desc = text_funcs.translate_and_text_evaluate('GAUGE_desc', unit=self.unit)
                self.info_graph.register((96 + 72, 16 * true_idx + 24, 64, 16), desc, state)

            elif stat == 'TALK':
                if (len([talk for talk in game.talk_options if talk[0] == self.unit.nid and talk not in game.talk_hidden]) != 0):
                    talkee = [talk for talk in game.talk_options if talk[0] == self.unit.nid][0][1]
                    render_text(surf, ['text'], [game.get_unit(talkee).name], ['blue'], (96, 16 * true_idx + 24))
                else:
                    render_text(surf, ['text'], ['--'], ['blue'], (111, 16 * true_idx + 24), HAlignment.RIGHT)
                render_text(surf, ['text'], [text_funcs.translate('Talk')], ['yellow'], (72, 16 * true_idx + 24))
                desc = text_funcs.translate_and_text_evaluate('Talk_desc', unit=self.unit)
                self.info_graph.register((96 + 72, 16 * true_idx + 24, 64, 16), desc, state)

            elif stat == 'LEAD':
                render_text(surf, ['text'], [text_funcs.translate('Lead')], ['yellow'], (72, 16 * true_idx + 24))
                desc = text_funcs.translate_and_text_evaluate('Lead_desc', unit=self.unit)
                self.info_graph.register((96 + 72, 16 * true_idx + 24, 64, 16), desc, state)

                if growths:
                    icons.draw_growth(surf, 'LEAD', self.unit, (111, 16 * true_idx + 24))
                else:
                    icons.draw_stat(surf, 'LEAD', self.unit, (111, 16 * true_idx + 24))
                    lead_surf = engine.subsurface(SPRITES.get('lead_star'), (0, 0, 16, 16))
                    surf.blit(lead_surf, (111, 16 * true_idx + 24))

        return surf

    def draw_personal_data_surf(self, surf):
        surf.blit(self.personal_data_surf, (96, 0))

    def draw_growths_surf(self, surf):
        surf.blit(self.growths_surf, (96, 0))

    def draw_support_skills_tabs(self, surf):
        tab_texts = ['Weapon Rank', ' / ', 'Support']
        tab_colors = [
            ('yellow' if self.support_skills_section == 'weapon' else 'grey'),
            'white',
            ('yellow' if self.support_skills_section == 'support' else 'grey'),
        ]
        render_text(
            surf, ['narrow'] * len(tab_texts), tab_texts, tab_colors,
            (96 + (WINWIDTH - 96) // 2, 20), HAlignment.CENTER)

    def _weapon_rank_help(self, weapon: str, value: int) -> str:
        weapon_prefab = DB.weapons.get(weapon)
        weapon_name = weapon_prefab.name if weapon_prefab else weapon
        weapon_rank = DB.weapon_ranks.get_rank_from_wexp(value)
        next_weapon_rank = DB.weapon_ranks.get_next_rank_from_wexp(value)
        rank_name = weapon_rank.nid if weapon_rank else '--'
        if next_weapon_rank:
            wexp_text = '%d/%d' % (value, next_weapon_rank.requirement)
        else:
            wexp_text = 'MAX'
        return '%s Rank: %s\nWEXP: %s' % (weapon_name, rank_name, wexp_text)

    def create_wexp_surf(self):
        wexp_to_draw: List[Tuple[str, int]] = []
        for weapon, wexp in self.unit.wexp.items():
            if wexp > 0 and weapon in unit_funcs.usable_wtypes(self.unit) \
                and weapon in DB.weapons.get_visible_weapon_types():
                wexp_to_draw.append((weapon, wexp))

        surf = engine.create_surface((WINWIDTH - 96, 84), transparent=True)
        if not wexp_to_draw:
            render_text(
                surf, ['text'], ['--'], ['blue'],
                ((WINWIDTH - 96) // 2, 32), HAlignment.CENTER)
            return surf

        # Preserve the original detailed presentation while it fits in four
        # rows. Only inventories with more than eight weapon ranks switch to
        # the compact 4x5 grid.
        if len(wexp_to_draw) <= 8:
            panel_width = WINWIDTH - 96
            content_height = 80
            row_height = 16
            width = (WINWIDTH - 102) // 2
            visual_width = width - 6
            row_count = (len(wexp_to_draw) + 1) // 2
            vertical_gap = (
                (content_height - row_count * row_height) /
                (row_count + 1))
            for counter, (weapon, value) in enumerate(wexp_to_draw):
                x, y = counter % 2, counter // 2
                items_in_row = min(2, len(wexp_to_draw) - y * 2)
                if items_in_row == 1:
                    offset = (panel_width - visual_width) // 2
                    help_x = (panel_width - width) // 2
                else:
                    pair_width = visual_width + width
                    pair_left = (panel_width - pair_width) // 2
                    offset = pair_left + x * width
                    help_x = (panel_width - width * 2) // 2 + x * width
                y_offset = int(round(
                    (y + 1) * vertical_gap + y * row_height))

                weapon_rank = DB.weapon_ranks.get_rank_from_wexp(value)
                next_weapon_rank = DB.weapon_ranks.get_next_rank_from_wexp(value)
                if not weapon_rank:
                    perc = 0
                elif not next_weapon_rank:
                    perc = 1
                else:
                    perc = (value - weapon_rank.requirement) / (next_weapon_rank.requirement - weapon_rank.requirement)

                icons.draw_weapon(surf, weapon, (offset, y_offset))

                # Build groove
                build_groove(surf, (offset + 18, y_offset + 6), width - 24, perc)
                # Add text
                pos = (offset + 7 + width//2, y_offset)
                rank_name = weapon_rank.nid if weapon_rank else '--'
                if FONT.get('rank'):
                    render_text(surf, ['rank'], [rank_name], ['blue'], pos, HAlignment.CENTER)
                else:
                    render_text(surf, ['text'], [rank_name], ['blue'], pos, HAlignment.CENTER)
                self.info_graph.register(
                    (96 + help_x, 36 + y_offset, width, row_height),
                    self._weapon_rank_help(weapon, value),
                    'support_skills',
                    first=(counter == 0))
        else:
            panel_width = WINWIDTH - 96
            content_height = 80
            row_height = 16
            cell_width = (panel_width - 4) // 4
            visible_wexp = wexp_to_draw[:20]
            row_count = (len(visible_wexp) + 3) // 4
            vertical_gap = (
                (content_height - row_count * row_height) /
                (row_count + 1))
            for counter, (weapon, value) in enumerate(visible_wexp):
                x, y = counter % 4, counter // 4
                items_in_row = min(4, len(visible_wexp) - y * 4)
                row_width = items_in_row * cell_width
                row_left = (panel_width - row_width) // 2
                x_offset = row_left + x * cell_width
                y_offset = int(round(
                    (y + 1) * vertical_gap + y * row_height))
                weapon_rank = DB.weapon_ranks.get_rank_from_wexp(value)
                rank_name = weapon_rank.nid if weapon_rank else '--'

                icons.draw_weapon(surf, weapon, (x_offset + 1, y_offset))
                rank_font = 'rank' if FONT.get('rank') else 'text'
                render_text(
                    surf, [rank_font], [rank_name], ['blue'],
                    (x_offset + cell_width - 2, y_offset),
                    HAlignment.RIGHT)
                self.info_graph.register(
                    (96 + x_offset, 36 + y_offset, cell_width, row_height),
                    self._weapon_rank_help(weapon, value),
                    'support_skills',
                    first=(counter == 0))

        return surf

    def draw_wexp_surf(self, surf):
        surf.blit(self.wexp_surf, (96, 36))

    def create_equipment_surf(self):
        def create_item_option(idx, item):
            return BasicItemOption.from_item(idx, item, width=120, mode=ItemOptionModes.FULL_USES, text_color=item_system.text_color(None, item))

        surf = engine.create_surface((WINWIDTH - 96, WINHEIGHT), transparent=True)

        weapon = self.unit.get_weapon()
        accessory = self.unit.get_accessory()
        split_inventory = item_funcs.split_inventory_enabled()
        if split_inventory:
            weapon_items = item_funcs.get_section_items(
                self.unit, item_funcs.InventorySection.WEAPON)
            regular_items = item_funcs.get_section_items(
                self.unit, item_funcs.InventorySection.ITEM)
            inventory_items = (
                weapon_items
                if self.equipment_section == item_funcs.InventorySection.WEAPON
                else regular_items)
            list_top = 40
            weapon_count = '%d/%d' % (
                len(weapon_items),
                item_funcs.get_inventory_capacity(
                    self.unit, item_funcs.InventorySection.WEAPON))
            item_count = '%d/%d' % (
                len(regular_items),
                item_funcs.get_inventory_capacity(
                    self.unit, item_funcs.InventorySection.ITEM))
            tab_texts = [
                'Wpn', ' ', weapon_count, ' / ',
                'Item', ' ', item_count]
            tab_colors = [
                ('yellow' if self.equipment_section == item_funcs.InventorySection.WEAPON else 'grey'),
                'white',
                'blue',
                'white',
                ('yellow' if self.equipment_section == item_funcs.InventorySection.ITEM else 'grey'),
                'white',
                'blue',
            ]
            tab_font = 'text'
            tab_text_width = sum(
                text_width(tab_font, text) for text in tab_texts)
            if tab_text_width > (WINWIDTH - 96 - 8):
                tab_font = 'narrow'
            render_text(
                surf, [tab_font] * len(tab_texts), tab_texts, tab_colors,
                (72, 22), HAlignment.CENTER)
        else:
            inventory_items = self.unit.nonaccessories
            list_top = 24
        if split_inventory:
            # Four rows leave the lower 56 px for the GBA-sized battle stat panel.
            visible_inventory_items = inventory_items[:4]
        else:
            visible_inventory_items = inventory_items

        # Blit items
        for idx, item in enumerate(visible_inventory_items):
            equipped_subitem: Optional[ItemObject] = None
            if item.multi_item and any(subitem is weapon for subitem in item.subitems):
                surf.blit(SPRITES.get('equipment_highlight'), (8, idx * 16 + list_top + 8))
                for subitem in item.subitems:
                    if subitem is weapon:
                        equipped_subitem = subitem
                        item_option = create_item_option(idx, subitem)
                        break
                else:  # Shouldn't happen
                    item_option = create_item_option(idx, item)
            else:
                if item is weapon:
                    surf.blit(SPRITES.get('equipment_highlight'), (8, idx * 16 + list_top + 8))
                item_option = create_item_option(idx, item)
            item_option.draw(surf, 8, idx * 16 + list_top)
            help_dlg = build_dialog_list(equipped_subitem if equipped_subitem else item, PageType.ITEM, unit=self.unit)
            self.info_graph.register((96 + 8, idx * 16 + list_top, 120, 16), help_dlg, 'equipment', first=(idx == 0))

        if split_inventory and self.equipment_section == item_funcs.InventorySection.ITEM:
            if not inventory_items:
                FONT['text-grey'].blit('Nothing', surf, (16, list_top))

        # Battle stats
        battle_surf = SPRITES.get('battle_info')
        top, left = 104, 12
        surf.blit(battle_surf, (left, top))
        # Populate battle info
        surf.blit(SPRITES.get('equipment_logo'), (14, top + 4))
        render_text(surf, ['text'], [text_funcs.translate('Rng')], ['yellow'], (78, top))
        rng_desc = text_funcs.translate_and_text_evaluate('Rng_desc', unit=self.unit)
        self.info_graph.register((96 + 78, top, 56, 16), rng_desc, 'equipment')
        render_text(surf, ['text'], [text_funcs.translate('Atk')], ['yellow'], (22, top + 16))
        atk_desc = text_funcs.translate_and_text_evaluate('Atk_desc', unit=self.unit)
        self.info_graph.register((96 + 14, top + 16, 64, 16), atk_desc, 'equipment')
        render_text(surf, ['text'], [text_funcs.translate('Hit')], ['yellow'], (22, top + 32))
        hit_desc = text_funcs.translate_and_text_evaluate('Hit_desc', unit=self.unit)
        self.info_graph.register((96 + 14, top + 32, 64, 16), hit_desc, 'equipment')
        if DB.constants.value('crit'):
            render_text(surf, ['text'], [text_funcs.translate('Crit')], ['yellow'], (78, top + 16))
            crit_desc = text_funcs.translate_and_text_evaluate('Crit_desc', unit=self.unit)
            self.info_graph.register((96 + 78, top + 16, 56, 16), crit_desc, 'equipment')
        else:
            render_text(surf, ['text'], [text_funcs.translate('AS')], ['yellow'], (78, top + 16))
            AS_desc = text_funcs.translate_and_text_evaluate('AS_desc', unit=self.unit)
            self.info_graph.register((96 + 78, top + 16, 56, 16), AS_desc, 'equipment')
        render_text(surf, ['text'], [text_funcs.translate('Avoid')], ['yellow'], (78, top + 32))
        avoid_desc = text_funcs.translate_and_text_evaluate('Avoid_desc', unit=self.unit)
        self.info_graph.register((96 + 78, top + 32, 56, 16), avoid_desc, 'equipment')

        if weapon:
            rng = item_funcs.get_range_string(self.unit, weapon)
            dam = str(combat_calcs.damage(self.unit, weapon))
            acc = str(combat_calcs.accuracy(self.unit, weapon))
            crt = combat_calcs.crit_accuracy(self.unit, weapon)
            if crt is None:
                crt = '--'
            else:
                crt = str(crt)
        else:
            rng, dam, acc, crt = '--', '--', '--', '--'

        avo = str(combat_calcs.avoid(self.unit, weapon))
        attack_speed = str(combat_calcs.attack_speed(self.unit, weapon))
        render_text(surf, ['text'], [rng], ['blue'], (127, top), HAlignment.RIGHT)
        render_text(surf, ['text'], [dam], ['blue'], (71, top + 16), HAlignment.RIGHT)
        render_text(surf, ['text'], [acc], ['blue'], (71, top + 32), HAlignment.RIGHT)
        if DB.constants.value('crit'):
            render_text(surf, ['text'], [crt], ['blue'], (127, top + 16), HAlignment.RIGHT)
        else:
            render_text(surf, ['text'], [attack_speed], ['blue'], (127, top + 16), HAlignment.RIGHT)
        render_text(surf, ['text'], [avo], ['blue'], (127, top + 32), HAlignment.RIGHT)

        return surf

    def draw_equipment_surf(self, surf):
        surf.blit(self.equipment_surf, (96, 0))

    def create_spellbook_surf(self):
        def create_item_option(idx, item):
            return BasicItemOption.from_item(idx, item, width=120, mode=ItemOptionModes.FULL_USES, text_color=item_system.text_color(None, item))

        surf = engine.create_surface((WINWIDTH - 96, WINHEIGHT), transparent=True)

        loadout_items = self._get_spell_loadout_items(self.unit)

        # The "currently equipped" spell whose battle stats we display: prefer the
        # unit's actual equipped weapon if it lives in the loadout, otherwise the
        # first loadout entry.
        weapon = self.unit.get_weapon()
        if weapon not in loadout_items:
            weapon = loadout_items[0] if loadout_items else None

        # Blit the loadout spells
        for idx, item in enumerate(loadout_items):
            if item.multi_item and any(subitem is weapon for subitem in item.subitems):
                surf.blit(SPRITES.get('equipment_highlight'), (8, idx * 16 + 24 + 8))
                for subitem in item.subitems:
                    if subitem is weapon:
                        item_option = create_item_option(idx, subitem)
                        break
                else:  # Shouldn't happen
                    item_option = create_item_option(idx, item)
            else:
                if item is weapon:
                    surf.blit(SPRITES.get('equipment_highlight'), (8, idx * 16 + 24 + 8))
                item_option = create_item_option(idx, item)
            item_option.draw(surf, 8, idx * 16 + 24)
            help_dlg = build_dialog_list(item, PageType.ITEM, unit=self.unit)
            self.info_graph.register((96 + 8, idx * 16 + 24, 120, 16), help_dlg, 'spellbook', first=(idx == 0))

        # Battle stats for the equipped spell
        battle_surf = SPRITES.get('battle_info')
        top, left = 104, 12
        surf.blit(battle_surf, (left, top))
        surf.blit(SPRITES.get('equipment_logo'), (14, top + 4))
        render_text(surf, ['text'], [text_funcs.translate('Rng')], ['yellow'], (78, top))
        rng_desc = text_funcs.translate_and_text_evaluate('Rng_desc', unit=self.unit)
        self.info_graph.register((96 + 78, top, 56, 16), rng_desc, 'spellbook')
        render_text(surf, ['text'], [text_funcs.translate('Atk')], ['yellow'], (22, top + 16))
        atk_desc = text_funcs.translate_and_text_evaluate('Atk_desc', unit=self.unit)
        self.info_graph.register((96 + 14, top + 16, 64, 16), atk_desc, 'spellbook')
        render_text(surf, ['text'], [text_funcs.translate('Hit')], ['yellow'], (22, top + 32))
        hit_desc = text_funcs.translate_and_text_evaluate('Hit_desc', unit=self.unit)
        self.info_graph.register((96 + 14, top + 32, 64, 16), hit_desc, 'spellbook')
        if DB.constants.value('crit'):
            render_text(surf, ['text'], [text_funcs.translate('Crit')], ['yellow'], (78, top + 16))
            crit_desc = text_funcs.translate_and_text_evaluate('Crit_desc', unit=self.unit)
            self.info_graph.register((96 + 78, top + 16, 56, 16), crit_desc, 'spellbook')
        else:
            render_text(surf, ['text'], [text_funcs.translate('AS')], ['yellow'], (78, top + 16))
            AS_desc = text_funcs.translate_and_text_evaluate('AS_desc', unit=self.unit)
            self.info_graph.register((96 + 78, top + 16, 56, 16), AS_desc, 'spellbook')
        render_text(surf, ['text'], [text_funcs.translate('Avoid')], ['yellow'], (78, top + 32))
        avoid_desc = text_funcs.translate_and_text_evaluate('Avoid_desc', unit=self.unit)
        self.info_graph.register((96 + 78, top + 32, 56, 16), avoid_desc, 'spellbook')

        if weapon:
            rng = item_funcs.get_range_string(self.unit, weapon)
            dam = str(combat_calcs.damage(self.unit, weapon))
            acc = str(combat_calcs.accuracy(self.unit, weapon))
            crt = combat_calcs.crit_accuracy(self.unit, weapon)
            if crt is None:
                crt = '--'
            else:
                crt = str(crt)
        else:
            rng, dam, acc, crt = '--', '--', '--', '--'

        avo = str(combat_calcs.avoid(self.unit, weapon))
        attack_speed = str(combat_calcs.attack_speed(self.unit, weapon))
        render_text(surf, ['text'], [rng], ['blue'], (127, top), HAlignment.RIGHT)
        render_text(surf, ['text'], [dam], ['blue'], (71, top + 16), HAlignment.RIGHT)
        render_text(surf, ['text'], [acc], ['blue'], (71, top + 32), HAlignment.RIGHT)
        if DB.constants.value('crit'):
            render_text(surf, ['text'], [crt], ['blue'], (127, top + 16), HAlignment.RIGHT)
        else:
            render_text(surf, ['text'], [attack_speed], ['blue'], (127, top + 16), HAlignment.RIGHT)
        render_text(surf, ['text'], [avo], ['blue'], (127, top + 32), HAlignment.RIGHT)

        return surf

    def draw_spellbook_surf(self, surf):
        surf.blit(self.spellbook_surf, (96, 0))

    def create_skill_surf(self):
        surf = engine.create_surface((WINWIDTH - 96, 24), transparent=True)
        skills = [skill for skill in self.unit.skills if not (skill.class_skill or skill_system.hidden(skill, self.unit))]
        # stacked skills appear multiple times, but should be drawn only once
        skill_counter = {}
        unique_skills = []
        for skill in skills:
            if skill.nid not in skill_counter:
                skill_counter[skill.nid] = 1
                unique_skills.append(skill)
            else:
                skill_counter[skill.nid] += 1

        panel_width = WINWIDTH - 96
        icon_width = 16
        normal_step = 24
        minimum_visible_width = 4
        left_margin = 8
        right_margin = 8
        max_icon_x = panel_width - right_margin - icon_width
        available_span = max_icon_x - left_margin
        num_skills = len(unique_skills)
        if num_skills <= 1:
            icon_positions = [left_margin] if num_skills else []
        elif num_skills < 6:
            icon_positions = [
                left_margin + idx * normal_step
                for idx in range(num_skills)]
        else:
            step = min(
                normal_step,
                available_span / (num_skills - 1))
            step = max(minimum_visible_width, step)
            icon_positions = [
                min(max_icon_x, int(round(left_margin + idx * step)))
                for idx in range(num_skills)]

        self.skill_icon_layout = []
        for idx, (skill, icon_x) in enumerate(
                zip(unique_skills, icon_positions)):
            count = skill_counter[skill.nid]
            self._draw_status_skill_icon(
                surf, skill, count, (icon_x, 4))
            help_dlg = build_dialog_list(skill, PageType.SKILL, unit=self.unit)
            if idx + 1 < len(icon_positions):
                visible_width = min(
                    icon_width,
                    max(
                        minimum_visible_width,
                        icon_positions[idx + 1] - icon_x))
            else:
                visible_width = icon_width
            skill_aabb = (
                96 + icon_x, WINHEIGHT - 28, visible_width, icon_width)
            self.info_graph.register(
                skill_aabb, help_dlg, 'support_skills')
            self.skill_icon_layout.append(
                (skill, count, icon_x, skill_aabb))

        return surf

    def _draw_status_skill_icon(self, surf, skill, count, pos):
        icons.draw_skill(
            surf, skill, pos, compact=False,
            grey=skill_system.is_grey(skill, self.unit))
        if count > 1:
            text = str(count)
            render_text(
                surf, ['small'], [text], ['white'],
                (pos[0] + 12 - 4 * len(text), pos[1] + 2))

    def draw_skill_surf(self, surf):
        surf.blit(self.skill_surf, (96, WINHEIGHT - 32))
        if not self.info_flag or not self.info_graph.current_bb:
            return
        current_aabb = self.info_graph.current_bb.aabb
        for skill, count, icon_x, skill_aabb in self.skill_icon_layout:
            if skill_aabb == current_aabb:
                self._draw_status_skill_icon(
                    surf, skill, count,
                    (96 + icon_x, WINHEIGHT - 28))
                break

    def create_class_skill_surf(self):
        import pygame
        surf = engine.create_surface((WINWIDTH - 96, WINHEIGHT), transparent=True)

        def pick_skill(skill_list):
            """Return the top-priority skill (deduped by nid) from the filtered list."""
            if not skill_list:
                return None
            best = None
            best_prio = -1
            for skill in skill_list:
                prio = skill.priority.int()
                if prio > best_prio:
                    best_prio = prio
                    best = skill
            return best

        char_skills = [s for s in self.unit.skills if s.class_skill and s.char_skill and not skill_system.hidden(s, self.unit)]
        class_skills = [s for s in self.unit.skills if s.class_skill and s.class_skill2 and not skill_system.hidden(s, self.unit)]
        # Weapon-granted skills (weapon_*_skill components) take precedence in their
        # respective category rows. If no weapon skill is present, fall back to the
        # regular class_skill in that category.
        special_skills = [s for s in self.unit.skills if s.weapon_special_skill and not skill_system.hidden(s, self.unit)] \
            or [s for s in self.unit.skills if s.class_skill and s.special_skill and not skill_system.hidden(s, self.unit)]
        slota_skills = [s for s in self.unit.skills if s.weapon_slota_skill and not skill_system.hidden(s, self.unit)] \
            or [s for s in self.unit.skills if s.class_skill and s.slota_skill and not skill_system.hidden(s, self.unit)]
        slotb_skills = [s for s in self.unit.skills if s.weapon_slotb_skill and not skill_system.hidden(s, self.unit)] \
            or [s for s in self.unit.skills if s.class_skill and s.slotb_skill and not skill_system.hidden(s, self.unit)]
        slotc_skills = [s for s in self.unit.skills if s.weapon_slotc_skill and not skill_system.hidden(s, self.unit)] \
            or [s for s in self.unit.skills if s.class_skill and s.slotc_skill and not skill_system.hidden(s, self.unit)]
        extra_skill = [s for s in self.unit.skills if s.weapon_assist_skill and not skill_system.hidden(s, self.unit)] \
            or [s for s in self.unit.skills if s.class_skill and s.extra_skill and not skill_system.hidden(s, self.unit)]

        # FEH-style pill layout: 7 horizontal pills, each with a category color,
        # the skill icon at the left, and the skill name in the middle.
        # (label, fill color, border color, top skill)
        rows = [
            ('Personal', (190, 60, 80),   (110, 30, 50),  pick_skill(char_skills),    'Personal'),
            ('Class',    (180, 70, 150),  (100, 35, 90),  pick_skill(class_skills),   'Class'),
            ('Special',  (200, 150, 40),  (120, 80, 20),  pick_skill(special_skills), 'Special'),
            ('A',        (70, 140, 90),   (35, 80, 50),   pick_skill(slota_skills),   'Slot A'),
            ('B',        (170, 60, 60),   (95, 30, 30),   pick_skill(slotb_skills),   'Slot B'),
            ('C',        (60, 130, 200),  (30, 70, 120),  pick_skill(slotc_skills),   'Slot C'),
            ('E',        (200, 170, 60),  (115, 95, 25),  pick_skill(extra_skill),   'Extra'),
        ]

        pill_x = 4
        pill_w = (WINWIDTH - 96) - 8  # 136 px
        pill_h = 18
        start_y = 14
        gap = 2

        for idx, (label, fill_color, border_color, skill, category) in enumerate(rows):
            y = start_y + idx * (pill_h + gap)

            # Draw rounded pill background (filled, with 1px darker border)
            pygame.draw.rect(surf, fill_color, (pill_x, y, pill_w, pill_h), border_radius=pill_h // 2)
            pygame.draw.rect(surf, border_color, (pill_x, y, pill_w, pill_h), width=1, border_radius=pill_h // 2)

            # Category badge (single letter, on the left side, inside a small circle)
            badge_cx = pill_x + 9
            badge_cy = y + pill_h // 2
            pygame.draw.circle(surf, border_color, (badge_cx, badge_cy), 7)
            badge_w = text_width('text', label[0])
            render_text(surf, ['text'], [label[0]], ['white'], ((badge_cx - badge_w // 2) - 1, y + 1))

            # Skill icon (16x16) right after the badge
            icon_x = pill_x + 18
            icon_y = y + 1
            if skill is not None:
                icons.draw_skill(surf, skill, (icon_x, icon_y), compact=False,
                                 grey=skill_system.is_grey(skill, self.unit))
                # Skill name, truncated to fit
                name = skill.name
                max_name_w = pill_w - (icon_x - pill_x) - 18 - 4
                truncated = name
                while truncated and text_width('text', truncated) > max_name_w:
                    truncated = truncated[:-1]
                if truncated != name and len(truncated) > 1:
                    truncated = truncated[:-1] + '.'
                name_x = icon_x + 18
                render_text(surf, ['text'], [truncated], ['white'], (name_x, y + 2))
                # Register the whole pill for info graph hover help
                self.info_graph.register((96 + pill_x, y, pill_w, pill_h),
                                         help_menu.SkillHelpDialog.build_pages(
                                             skill, category=category,
                                             max_body_lines=2), 'skills')
            else:
                # Empty slot indicator
                dash_x = icon_x + 18
                render_text(surf, ['text'], ['---'], ['white'], (dash_x, y + 2))

        return surf

    def draw_class_skill_surf(self, surf):
        surf.blit(self.class_skill_surf, (96, 0))

    def create_support_surf(self):
        surf = engine.create_surface((WINWIDTH - 96, WINHEIGHT), transparent=True)
        panel_width = WINWIDTH - 96

        pairs = game.supports.get_pairs(self.unit.nid)
        pairs = [pair for pair in pairs if pair.unlocked_ranks]

        partner_rows = []
        for pair in pairs:
            other_nid = pair.unit2 if pair.unit1 == self.unit.nid else pair.unit1
            # An unlocked partner can be absent from the current map. Fall
            # back to its database prefab so the Support page still lists it.
            other_unit = game.get_unit(other_nid) or DB.units.get(other_nid)
            if not other_unit:
                continue
            highest_rank = pair.unlocked_ranks[-1]
            partner_rows.append((other_unit, highest_rank))

        visible_partner_rows = partner_rows[:6]
        partner_columns = 2
        partner_column_gap = 4
        partner_outer_margin = 4
        partner_column_width = (
            panel_width - partner_column_gap -
            partner_outer_margin * 2) // partner_columns
        partner_area_top = 36
        partner_area_height = 50
        partner_row_height = 16
        partner_row_count = (len(visible_partner_rows) + 1) // 2
        partner_vertical_gap = (
            (partner_area_height - partner_row_count * partner_row_height) /
            (partner_row_count + 1)
            if partner_row_count else 0)
        for idx, (other_unit, highest_rank) in enumerate(visible_partner_rows):
            x, y = idx % partner_columns, idx // partner_columns
            items_in_row = min(
                partner_columns, len(visible_partner_rows) - y * partner_columns)
            row_width = (
                items_in_row * partner_column_width +
                max(0, items_in_row - 1) * partner_column_gap)
            row_left = (panel_width - row_width) // 2
            cell_x = x * (partner_column_width + partner_column_gap) + row_left
            row_y = partner_area_top + int(round(
                (y + 1) * partner_vertical_gap + y * partner_row_height))

            rank_width = text_width('narrow', highest_rank)
            rank_x = cell_x + partner_column_width - 2
            name_x = cell_x + 1
            max_name_width = max(8, partner_column_width - 5 - rank_width)
            display_name = other_unit.name
            while display_name and text_width('narrow', display_name) > max_name_width:
                display_name = display_name[:-1]
            if display_name != other_unit.name and len(display_name) > 1:
                display_name = display_name[:-1] + '.'

            render_text(surf, ['narrow'], [display_name], [], (name_x, row_y + 1))
            render_text(
                surf, ['narrow'], [highest_rank], ['yellow'],
                (rank_x, row_y), HAlignment.RIGHT)
            self.info_graph.register(
                (96 + cell_x, row_y, partner_column_width, 16),
                '%s Support Rank: %s' % (other_unit.name, highest_rank),
                'support_skills',
                first=(idx == 0))

        if not visible_partner_rows:
            render_text(
                surf, ['narrow'], ['--'], ['blue'],
                (panel_width // 2, partner_area_top + 17),
                HAlignment.CENTER)

        bonuses, _allies = combat_calcs.get_support_rank_bonus(self.unit)
        bonus_fields = (
            ('Atk', 'damage'),
            ('Def', 'resist'),
            ('Hit', 'accuracy'),
            ('Avo', 'avoid'),
            ('Crit', 'crit'),
            ('Ddg', 'dodge'),
            ('AS', 'attack_speed'),
            ('DS', 'defense_speed'),
        )
        stat_entries = []
        for label, attribute in bonus_fields:
            value = int(sum(
                getattr(bonus, attribute, 0) for bonus in bonuses))
            if value > 0:
                sign_text = '+'
                number_text = str(value)
            elif value < 0:
                sign_text = '-'
                number_text = str(abs(value))
            else:
                sign_text = ''
                number_text = '0'
            label_width = text_width('narrow', label)
            sign_width = text_width('narrow', sign_text)
            number_width = text_width('narrow', number_text)
            value_width = (
                sign_width + (1 if sign_text else 0) + number_width)
            stat_entries.append(
                (label, sign_text, number_text, label_width, value_width))

        stat_rows = (
            stat_entries[:4],
            stat_entries[4:],
        )
        stat_column_layouts = []
        for column in range(4):
            top_entry = stat_rows[0][column]
            bottom_entry = stat_rows[1][column]
            label_slot_width = max(top_entry[3], bottom_entry[3])
            value_slot_width = max(top_entry[4], bottom_entry[4])
            group_width = label_slot_width + 2 + value_slot_width
            stat_column_layouts.append(
                (label_slot_width, value_slot_width, group_width))

        total_group_width = sum(layout[2] for layout in stat_column_layouts)
        horizontal_gap = max(
            0, (panel_width - total_group_width) / 5)
        stat_group_xs = []
        consumed_width = 0
        for column, (_, _, group_width) in enumerate(stat_column_layouts):
            group_x = int(round(
                (column + 1) * horizontal_gap + consumed_width))
            stat_group_xs.append(group_x)
            consumed_width += group_width

        stat_area_top = 88
        stat_area_height = 29
        stat_row_height = 13
        vertical_gap = (
            (stat_area_height - stat_row_height * 2) / 3)
        for row, row_entries in enumerate(stat_rows):
            row_y = stat_area_top + int(round(
                (row + 1) * vertical_gap + row * stat_row_height))

            for column, (
                    label, sign_text, number_text, _label_width,
                    _value_width) in enumerate(row_entries):
                label_slot_width, _, group_width = stat_column_layouts[column]
                group_x = stat_group_xs[column]
                label_right = group_x + label_slot_width
                value_x = label_right + 2
                render_text(
                    surf, ['narrow'], [label], ['yellow'],
                    (label_right, row_y), HAlignment.RIGHT)
                if sign_text:
                    render_text(
                        surf, ['narrow'], [sign_text], ['blue'],
                        (value_x, row_y))
                    number_x = (
                        value_x + text_width('narrow', sign_text) + 1)
                else:
                    number_x = value_x
                render_text(
                    surf, ['narrow'], [number_text], ['blue'],
                    (number_x, row_y))
                self.info_graph.register(
                    (96 + group_x, row_y, group_width, stat_row_height),
                    '%s support bonus: %s%s' % (
                        label, sign_text, number_text),
                    'support_skills',
                    first=(not visible_partner_rows and row == 0 and column == 0))
        return surf

    def draw_support_surf(self, surf):
        surf.blit(self.support_surf, (96, 0))

    def create_fatigue_surf(self):
        surf = engine.create_surface((WINWIDTH - 96, WINHEIGHT), transparent=True)
        max_fatigue = max(1, self.unit.get_max_fatigue())
        fatigue = self.unit.get_fatigue()
        build_groove(surf, (27, WINHEIGHT - 9), 88, utils.clamp(fatigue / max_fatigue, 0, 1))
        x_pos = 27 + 88 // 2
        text = str(fatigue) + '/' + str(max_fatigue)
        x_pos -= text_width('text', text)//2
        render_text(surf, ['text'], [text], ['blue'], (x_pos, WINHEIGHT - 17))
        if fatigue >= max_fatigue:
            render_text(surf, ['text'], [str(fatigue)], ['red'], (x_pos, WINHEIGHT - 17))
        render_text(surf, ['text'], [text_funcs.translate('Ftg')], ['yellow'], (8, WINHEIGHT - 17))

        return surf

    def draw_fatigue_surf(self, surf):
        surf.blit(self.fatigue_surf, (96, 0))

    def create_notes_surf(self):
        # Menu background
        menu_surf = engine.create_surface((WINWIDTH - 96, WINHEIGHT), transparent=True)

        text_parser = TextEvaluator(logging.getLogger(), game, self.unit)
        my_notes = self.unit.notes

        if my_notes:
            total_height = 24
            help_offset = 0
            for idx, note in enumerate(my_notes):
                category = note[0]
                entries = note[1].split(',')
                render_text(menu_surf, ['text'], [category], ['blue'], (10, total_height))
                for entry in entries:
                    category_length = text_width('text', category)
                    left_pos = 64 if category_length <= 64 else (category_length + 8)
                    render_text(menu_surf, ['text'], [text_parser._evaluate_all(entry)], [], (left_pos, total_height))
                    total_height += 16
                self.info_graph.register((96, 16 * help_offset + 24, 64, 16), '%s_desc' % category, 'notes', first=(idx == 0))
                help_offset += len(entries)

        return menu_surf

    def draw_notes_surf(self, surf):
        surf.blit(self.notes_surf, (96, 0))
