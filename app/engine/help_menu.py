from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

import app.engine.config as cf
from app.constants import WINHEIGHT, WINWIDTH
from app.data.database.database import DB
from app.engine import (base_surf, engine, icons, item_funcs,
                        item_system, skill_system, text_funcs)
from app.engine.fonts import FONT
from app.engine.game_state import game
from app.engine.graphics.text.text_renderer import (fix_tags, font_height, render_text,
                                                    text_width)
from app.engine.sprites import SPRITES
from app.utilities import utils
from app.utilities.enums import HAlignment
from app.utilities.typing import NID

if TYPE_CHECKING:
    from app.engine.objects.skill import SkillObject
    from app.engine.objects.unit import UnitObject
    from app.engine.objects.item import ItemObject
    
MAX_TEXT_WIDTH = WINWIDTH - 40

def stretch_skill_bg(sprite, desired_width):
    """Stretch a skill info background sprite horizontally by tiling a 1px middle column.

    Preserves the left endcap (including left rivet + start of diagonal) and the
    right endcap (including right rivet + end of diagonal) while repeating a 1px
    column from the middle of the sprite to fill any extra width.

    If desired_width <= sprite width, returns the sprite unchanged.
    """
    base_w = sprite.get_width()
    base_h = sprite.get_height()

    if desired_width <= base_w:
        return sprite

    # Split point: take a 1px column from the geometric middle of the sprite.
    # Endcaps preserve everything to the left/right of that column.
    mid_x = base_w // 2
    left_w = mid_x
    right_w = base_w - mid_x - 1

    left = engine.subsurface(sprite, (0, 0, left_w, base_h))
    middle = engine.subsurface(sprite, (mid_x, 0, 1, base_h))
    right = engine.subsurface(sprite, (mid_x + 1, 0, right_w, base_h))

    surf = engine.create_surface((desired_width, base_h), transparent=True)
    surf.blit(left, (0, 0))
    middle_end = desired_width - right_w
    for x in range(left_w, middle_end):
        surf.blit(middle, (x, 0))
    surf.blit(right, (middle_end, 0))

    return surf

class HelpDialog():
    help_logo = SPRITES.get('help_logo')
    font: NID = 'convo'

    def __init__(self, desc:str='', name:str=''):
        self.name = name
        self.last_time = self.start_time = 0
        self.transition_in = False
        self.transition_out = 0

        desc = text_funcs.translate(desc)
        lines = self.build_lines(desc)
        num_lines = len(lines)

        if lines:
            self.greatest_line_len = text_funcs.get_max_width(self.font, lines)
        else:
            self.greatest_line_len = 8
        if self.name:
            self.greatest_line_len = max(self.greatest_line_len, text_width(self.font, self.name))
            num_lines += 1

        self.create_dialog(desc)

        height = font_height(self.font) * num_lines + 16
        self.help_surf = base_surf.create_base_surf(self.dlg.width, height, 'help_bg_base')
        self.h_surf = engine.create_surface((self.dlg.width, height + 3), transparent=True)

    def create_dialog(self, desc):
        from app.engine import dialog
        desc = desc.replace('\n', '{br}')
        self.dlg = \
            dialog.Dialog.from_style(game.speak_styles.get('__default_help'), desc,
                                     width=self.greatest_line_len + 16)
        self.dlg.position = (0, (16 if self.name else 0))

    def get_width(self):
        return self.help_surf.get_width()

    def get_height(self):
        return self.help_surf.get_height()

    def find_num_lines(self, desc: str) -> int:
        '''Returns the number of lines in the description'''
        # Split on \n, then go through each element in the list
        # and break it into further strings if too long
        desc = desc.replace('{br}', '\n')
        lines = desc.split("\n")
        total_lines = len(lines)
        for line in lines:
            desc_length = text_width(self.font, line)
            total_lines += desc_length // MAX_TEXT_WIDTH
        return total_lines

    def build_lines(self, desc: str) -> List[str]:
        # Hard set num lines if desc is very short
        if '\n' in desc:
            desc_lines = desc.splitlines()
            lines = []
            for line in desc_lines:
                num = self.find_num_lines(line)
                line = text_funcs.split(self.font, line, num, MAX_TEXT_WIDTH)
                lines.extend(line)
        else:
            num = self.find_num_lines(desc)
            lines = text_funcs.split(self.font, desc, num, MAX_TEXT_WIDTH)
        lines = fix_tags(lines)
        return lines

    def set_transition_in(self):
        self.transition_in = True
        self.transition_out = 0
        self.start_time = engine.get_time()

    def handle_transition_in(self, time, h_surf):
        if self.transition_in:
            progress = utils.clamp((time - self.start_time) / 130., 0, 1)
            if progress >= 1:
                self.transition_in = False
            else:
                h_surf = engine.transform_scale(h_surf, (int(progress * h_surf.get_width()), int(progress * h_surf.get_height())))
        return h_surf

    def set_transition_out(self):
        self.transition_out = engine.get_time()

    def handle_transition_out(self, time, h_surf):
        if self.transition_out:
            progress = 1 - (time - self.transition_out) / 100.
            if progress <= 0.1:
                self.transition_out = 0
                progress = 0.1
            h_surf = engine.transform_scale(h_surf, (int(progress * h_surf.get_width()), int(progress * h_surf.get_height())))
        return h_surf

    def top_left(self, pos, right=False):
        if right:
            pos = (pos[0] - self.help_surf.get_width(), pos[1])
        if pos[0] + self.help_surf.get_width() >= WINWIDTH:
            pos = (WINWIDTH - self.help_surf.get_width() - 8, pos[1])
        if pos[1] + self.help_surf.get_height() >= WINHEIGHT:
            pos = (pos[0], max(0, pos[1] - self.help_surf.get_height() - 16))
        if pos[0] < 0:
            pos = (0, pos[1])
        return pos

    def final_draw(self, surf, pos, time, help_surf):
        # Draw help logo
        h_surf = engine.copy_surface(self.h_surf)
        h_surf.blit(help_surf, (0, 3))
        h_surf.blit(self.help_logo, (9, 0))

        if self.transition_in:
            h_surf = self.handle_transition_in(time, h_surf)
        elif self.transition_out:
            h_surf = self.handle_transition_out(time, h_surf)

        surf.blit(h_surf, pos)
        return surf

    def draw(self, surf, pos, right=False):
        time = engine.get_time()
        if time > self.last_time + 1000:  # If it's been at least a second since last update
            self.start_time = time - 16
            self.transition_in = True
            self.transition_out = 0
            self.create_dialog(self.dlg.plain_text)
        self.last_time = time

        help_surf = engine.copy_surface(self.help_surf)
        if self.name:
            render_text(help_surf, [self.font], [self.name], [game.speak_styles.get('__default_help').font_color], (8, 8))

        self.dlg.update()
        self.dlg.draw(help_surf)
        surf = self.final_draw(surf, self.top_left(pos, right), time, help_surf)
        return surf

class StatDialog(HelpDialog):
    text_font: NID = 'text'

    def __init__(self, desc, bonuses):
        self.last_time = self.start_time = 0
        self.transition_in = False
        self.transition_out = 0

        desc = text_funcs.translate(desc)
        self.plain_desc = desc
        self.bonuses = bonuses

        self.lines = fix_tags(text_funcs.line_wrap(self.font, desc, 144))
        height = font_height(self.font) * (len(self.lines) + len(self.bonuses)) + 16

        self.create_dialog(desc)

        self.help_surf = base_surf.create_base_surf(self.dlg.width, height, 'help_bg_base')
        self.h_surf = engine.create_surface((self.dlg.width, height + 3), transparent=True)

    def create_dialog(self, desc):
        from app.engine import dialog
        desc = desc.replace('\n', '{br}')

        bonuses = sorted(self.bonuses.items(), key=lambda x: x[0] != 'Base Value')
        color = game.speak_styles.get('__default_help').font_color
        for idx, (bonus, val) in enumerate(bonuses):
            if idx == 0:
                width = text_width(self.text_font, str(val))
                desc += '{br}<%s><%s>%s</></>' % (self.text_font, color, str(val))
            elif val > 0:
                width = text_width(self.text_font, '+' + str(val))
                desc += '{br}<%s><green>%s</></>' % (self.text_font, '+' + str(val))
            elif val < 0:
                width = text_width(self.text_font, str(val))
                desc += '{br}<%s><red>%s</></>' % (self.text_font, str(val))
            else:
                width = text_width(self.font, str(val))
                desc += '{br}<%s><%s>%s</></>' % (self.font, color, str(val))
            desc += '{max_speed}' + ('﹘' * (24 - width)) + '{starting_speed}<%s><%s>%s</></>' % (self.font, color, bonus)

        self.dlg = \
            dialog.Dialog.from_style(game.speak_styles.get('__default_help'), desc,
                                     width=160)
        self.dlg.position = (0, 0)

    def draw(self, surf, pos, right=False):
        time = engine.get_time()
        if time > self.last_time + 1000:  # If it's been at least a second since last update
            self.start_time = time - 16
            self.transition_in = True
            self.transition_out = 0
            self.create_dialog(self.plain_desc)
        self.last_time = time

        help_surf = engine.copy_surface(self.help_surf)

        if self.dlg:
            self.dlg.update()
            self.dlg.draw(help_surf)

        surf = self.final_draw(surf, self.top_left(pos, right), time, help_surf)
        return surf

ITEM_HELP_WIDTH = 160

class ItemHelpDialog(HelpDialog):
    text_font: NID = 'text'

    def __init__(self, item: ItemObject, first: bool = True, unit_override: Optional[UnitObject]=None):
        self.last_time = self.start_time = 0
        self.transition_in = False
        self.transition_out = 0
            
        self.item = item
        self.unit = self._resolve_unit(self.item, unit_override)
        
        show_name: bool = item_system.show_item_name_in_help_dlg(self.unit, self.item)
        self.name_override: Optional[str] = None
        self.v_offset: int = 0
        if not first or show_name:
            self.name_override = item_system.multi_desc_name_override(self.unit, self.item)
            if self.name_override is None:
                self.name_override = self.item.name # We still want to show the name, so just show the default.
            else:
                # maintain parity with item evals allowing reference to the item object via the 'item' name
                self.name_override = text_funcs.translate_and_text_evaluate(self.name_override, self.unit, self=self.item, local_args={'item': self.item})
            self.v_offset += 16

        weapon_rank = item_system.weapon_rank(self.unit, self.item)
        if not weapon_rank:
            if item.prf_unit or item.prf_class or item.prf_tag:
                weapon_rank = 'Prf'
            else:
                weapon_rank = '--'

        might = item_system.damage(self.unit, self.item)
        hit = item_system.hit(self.unit, self.item)
        if DB.constants.value('crit'):
            crit = item_system.crit(self.unit, self.item)
        else:
            crit = None
        weight = self.item.weight.value if self.item.weight else None
        # Get range
        rng = item_funcs.get_range_string(self.unit, self.item)

        self.vals = [weapon_rank, rng, weight, might, hit, crit]

        # Build color list for each stat. Compare raw `component.value` between the
        # current item instance and its prefab in DB.items to detect modifications by
        # the `modify_item_component` event command (which mutates the live item but
        # leaves the prefab untouched). This avoids comparing post-bonus values from
        # item_system.* hooks, which would otherwise color stats based on skill /
        # terrain bonuses rather than the actual modify_item_component change.
        # - blue : unchanged or no prefab to compare against
        # - green: increased (or for weight: decreased, since lower weight is better)
        # - red  : decreased (or for weight: increased)
        self.val_colors = ['blue']  # weapon_rank: no prefab comparison

        prefab = DB.items.get(self.item.nid)

        def _get_raw(item_or_prefab, comp_nid):
            """Return raw `component.value` for a given component nid, or None."""
            if not item_or_prefab:
                return None
            comps = getattr(item_or_prefab, 'components', None)
            if not comps:
                return None
            for c in comps:
                if c.nid == comp_nid:
                    return c.value
            return None

        def _color_for(current, original, lower_is_better=False):
            if current is None or original is None or current == original:
                return 'blue'
            if lower_is_better:
                return 'green' if current < original else 'red'
            return 'green' if current > original else 'red'

        # Range: green if max increased OR min decreased, red for the opposite.
        cur_min = _get_raw(self.item, 'min_range')
        cur_max = _get_raw(self.item, 'max_range')
        pre_min = _get_raw(prefab, 'min_range')
        pre_max = _get_raw(prefab, 'max_range')
        rng_color = 'blue'
        if None not in (cur_min, cur_max, pre_min, pre_max):
            if cur_max > pre_max or cur_min < pre_min:
                rng_color = 'green'
            elif cur_max < pre_max or cur_min > pre_min:
                rng_color = 'red'
        self.val_colors.append(rng_color)

        # Weight (lower is better)
        self.val_colors.append(_color_for(_get_raw(self.item, 'weight'),
                                          _get_raw(prefab, 'weight'),
                                          lower_is_better=True))
        # Might (damage component)
        self.val_colors.append(_color_for(_get_raw(self.item, 'damage'),
                                          _get_raw(prefab, 'damage')))
        # Hit
        self.val_colors.append(_color_for(_get_raw(self.item, 'hit'),
                                          _get_raw(prefab, 'hit')))
        # Crit
        self.val_colors.append(_color_for(_get_raw(self.item, 'crit'),
                                          _get_raw(prefab, 'crit')))

        desc = text_funcs.translate_and_text_evaluate(
            self.item.desc,
            unit=self.unit,
            self=self.item)

        self.num_present = len([v for v in self.vals if v is not None])

        self.dlg = self.create_dialog(desc)
        fake_dlg = self.create_dialog(desc)
        if fake_dlg:
            fake_dlg.warp_speed()
            num_lines = len(fake_dlg.text_indices)
        else:
            num_lines = 0

        if self.num_present > 3:
            height = 48 + font_height(self.font) * num_lines
        else:
            height = 32 + font_height(self.font) * num_lines
            
        height += self.v_offset

        self.help_surf = base_surf.create_base_surf(ITEM_HELP_WIDTH, height, 'help_bg_base')
        self.h_surf = engine.create_surface((ITEM_HELP_WIDTH, height + 3), transparent=True)

    def _resolve_unit(self, item: ItemObject, unit: Optional[UnitObject]) -> Optional[UnitObject]:
        if unit:
            return unit
        if item.owner_nid:
            return game.get_unit(item.owner_nid)
        return None
            
    def create_dialog(self, desc: str):
        if desc:
            from app.engine import dialog
            desc = desc.replace('\n', '{br}')
            dlg: dialog.Dialog = \
                dialog.Dialog.from_style(game.speak_styles.get('__default_help'), desc,
                                         width=ITEM_HELP_WIDTH)
            y_height = 32 if self.num_present > 3 else 16
            dlg.position = (0, y_height + self.v_offset)
        else:
            dlg = None
        return dlg

    def build_lines(self, desc, width):
        if not desc:
            desc = ''
        # Hard set num lines if desc is very short
        if '\n' in desc:
            lines = desc.splitlines()
            self.lines = []
            for line in lines:
                line = text_funcs.line_wrap(self.font, line, width)
                self.lines.extend(line)
        else:
            self.lines = text_funcs.line_wrap(self.font, desc, width)
        self.lines = fix_tags(self.lines)

    def draw(self, surf, pos, right=False):
        time = engine.get_time()
        if time > self.last_time + 1000:  # If it's been at least a second since last update
            self.start_time = time - 16
            self.transition_in = True
            self.transition_out = 0
            if self.dlg:
                self.create_dialog(self.dlg.plain_text)
        self.last_time = time

        help_surf = engine.copy_surface(self.help_surf)
        weapon_type = item_system.weapon_type(self.unit, self.item)
        if weapon_type:
            icons.draw_weapon(help_surf, weapon_type, (8, 8 + self.v_offset))
        # Weapon rank uses val_colors[0] (always blue)
        render_text(help_surf, [self.text_font], [str(self.vals[0])], [self.val_colors[0]], (50, 8 + self.v_offset), HAlignment.RIGHT)

        if self.name_override is not None:
            render_text(help_surf, ['text'], [self.name_override], ['blue'], (8, 6))
            
        name_positions = [(56, 8), (106, 8), (8, 24), (56, 24), (106, 24)]
        name_positions.reverse()
        val_positions = [(100, 8), (144, 8), (50, 24), (100, 24), (144, 24)]
        val_positions.reverse()
        names = ['Rng', 'Wt', 'Mt', 'Hit', 'Crit']

        # Use val_colors[1:] for stats after weapon_rank (rng, weight, might, hit, crit)
        for idx, (v, n) in enumerate(zip(self.vals[1:], names)):
            if v is not None:
                name_pos = name_positions.pop()
                render_text(help_surf, [self.text_font], [n], ['yellow'], (name_pos[0], name_pos[1] + self.v_offset))
                val_pos = val_positions.pop()
                # idx+1 because val_colors[0] is weapon_rank, so val_colors[1] is for first stat (rng)
                color = self.val_colors[idx + 1] if idx + 1 < len(self.val_colors) else 'blue'
                render_text(help_surf, [self.text_font], [str(v)], [color], (val_pos[0], val_pos[1] + self.v_offset), HAlignment.RIGHT)

        if self.dlg:
            self.dlg.update()
            self.dlg.draw(help_surf)

        surf = self.final_draw(surf, self.top_left(pos, right), time, help_surf)
        return surf

class SkillHelpDialog(HelpDialog):
    def __init__(self, skill: SkillObject, first:bool=True, unit_override:Optional[UnitObject]=None, category: str = ''):
        import re
        # Detect tier/rarity tag from the skill nid (T1/T2/T3/T4/Ultra). The
        # tag is inserted between the category label and the skill name so
        # players can tell apart upgrade tiers at a glance.
        tier_tag = ''
        nid_upper = (skill.nid or '').upper()
        for marker in ('ULTRA', 'T4', 'T3', 'T2', 'T1'):
            # Match as a delimited token so 'T1' inside 'TEST1' is not picked up.
            if re.search(r'(?:^|[^A-Z0-9])' + marker + r'(?:[^A-Z0-9]|$)', nid_upper):
                tier_tag = 'Ultra' if marker == 'ULTRA' else marker
                break
        # Skill name with optional tier tag prefix, truncated to fit.
        self.name = (skill.name + ' ' + tier_tag) if tier_tag else skill.name
        # old behavior where the charge is just shown next to the name
        self.name = ' ' + self.name + self._get_charge_str(skill)
        if category:
            self.name = self.name + ' (' + category + ')'
        self.last_time = self.start_time = 0
        self.transition_in = False
        self.transition_out = 0
        self.bg_sprite = 'skill_info'

        unit = self._resolve_unit(skill, unit_override)

        name_override: Optional[str] = skill_system.get_multi_desc_name_override(skill, unit)
        if not first and name_override is not None:
            # maintain parity with skill evals allowing access to the skill object via the 'skill' name
            self.name = text_funcs.translate_and_text_evaluate(name_override, unit, self=skill, local_args={'skill': skill})

        desc = skill.desc
        desc = text_funcs.translate_and_text_evaluate(desc, unit=unit_override, self=skill, local_args={'skill': skill})
        lines = self.build_lines(desc)
        num_lines = len(lines)

        if lines:
            self.greatest_line_len = text_funcs.get_max_width(self.font, lines)
        else:
            self.greatest_line_len = 8
        if self.name:
            self.greatest_line_len = max(self.greatest_line_len, text_width(self.font, self.name))
            num_lines += 1

        self.create_dialog(desc)

        # Pick vertical sprite based on number of lines (height tiers).
        if num_lines == 2:
            self.bg_sprite = 'skill_info_small'
        elif num_lines == 4:
            self.bg_sprite = 'skill_info_large'
        elif num_lines == 5:
            self.bg_sprite = 'skill_info_xlarge'
        elif num_lines >= 6:
            self.bg_sprite = 'skill_info_xxlarge'
        else:
            self.bg_sprite = 'skill_info'

        sprite = SPRITES.get(self.bg_sprite)
        base_width = sprite.get_width()
        height = sprite.get_height()

        # Horizontal: stretch if content needs more room than the base sprite provides.
        desired_width = self.greatest_line_len + 16
        width = max(base_width, desired_width)

        self.panel_width = width
        self.help_surf = stretch_skill_bg(sprite, width)
        self.h_surf = engine.create_surface((width, height + 3), transparent=True)

    def _get_charge_str(self, skill: SkillObject) -> str:
        if skill.data.get('total_charge'): # this is so programmer-coded
            charge = ' %d / %d' % (skill.data['charge'], skill.data['total_charge'])
        else:
            charge = ''
        return charge

    def _resolve_unit(self, skill: SkillObject, unit: Optional[UnitObject]) -> Optional[UnitObject]:
        if unit:
            return unit
        if skill.owner_nid:
            return game.get_unit(skill.owner_nid)
        return None
