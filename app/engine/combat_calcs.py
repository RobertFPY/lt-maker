from dataclasses import dataclass
from functools import reduce
from operator import mul
from typing import List, Optional, Tuple
from app.engine.utils.ltcache import ltcached
from app.engine.combat_calcs_utils import resolve_defensive_formula, resolve_offensive_formula
from app.engine.game_state import game
from app.utilities import utils
from app.data.database.database import DB
from app.data.database import weapons
from app.engine import equations, item_system, item_funcs, skill_system, line_of_sight
from app.engine.combat.utils import resolve_weapon

def _get_weapon_rank_requirement(unit, item) -> int:
    if not unit or not item:
        return -1
    weapon_type = item_system.weapon_type(unit, item)
    if not weapon_type:
        return -1
    rank = DB.weapon_ranks.get_rank_from_wexp(unit.wexp.get(weapon_type, 0))
    return rank.requirement if rank else -1

def get_weapon_rank_bonus(unit, item, target=None, target_item=None):
    weapon_type = item_system.weapon_type(unit, item)
    if not weapon_type:
        return None
    weapon = DB.weapons.get(weapon_type)
    if not weapon:
        return None

    wexp = unit.wexp.get(weapon_type, 0)
    if target is not None:
        unit_rank = _get_weapon_rank_requirement(unit, item)
        target_rank = _get_weapon_rank_requirement(target, target_item)
        if unit_rank <= target_rank:
            return None

    rank_bonus = weapon.rank_bonus
    best_combat_bonus = None
    highest_requirement = -1
    for combat_bonus in rank_bonus:
        if combat_bonus.weapon_rank == 'All':
            return combat_bonus
        req = DB.weapon_ranks.get(combat_bonus.weapon_rank).requirement
        if wexp >= req and req > highest_requirement:
            highest_requirement = req
            best_combat_bonus = combat_bonus
    return best_combat_bonus

def get_support_rank_bonus(unit, target=None):
    from app.engine.game_state import game

    if not unit.position:
        return [], []
    # _supports gates the whole feature; without it combat would leak support bonuses
    # even before the developer enables supports (matches info screen / point accumulation)
    if not game.game_vars.get('_supports'):
        return [], []
    # If target, only check for when can attack same unit
    if target and DB.support_constants.value('bonus_range') != 0:
        return [], []
    pairs = game.supports.get_bonus_pairs(unit.nid)
    bonuses = []
    for pair in pairs:
        if not pair.unlocked_ranks:
            continue
        prefab = DB.support_pairs.get(pair.nid)
        if unit.nid == prefab.unit1:
            other_unit = game.get_unit(prefab.unit2)
        else:
            other_unit = game.get_unit(prefab.unit1)
        if not (other_unit and other_unit.position):
            continue
        # If unit has already been counted
        if other_unit in [_[1] for _ in bonuses]:
            continue
        if target and target.position:
            # Unit and other unit can both attack target
            if target.position in game.target_system.get_attackable_positions(other_unit, force=True):
                pass
            else:
                continue
        elif not game.supports.check_bonus_range(unit, other_unit):
            continue
        if not pair.unlocked_ranks:
            continue
        highest_rank = pair.unlocked_ranks[-1]
        support_rank_bonus = game.supports.get_bonus(unit, other_unit, highest_rank)
        bonuses.append((support_rank_bonus, other_unit, highest_rank))
    num_allies_allowed = DB.support_constants.value('bonus_ally_limit')
    if num_allies_allowed and len(bonuses) > num_allies_allowed:
        # Get the X highest bonuses
        bonuses = sorted(bonuses, key=lambda x: DB.support_ranks.index(x[2]), reverse=True)
        bonuses = bonuses[:num_allies_allowed]
    allies = [_[1] for _ in bonuses]
    bonuses = [_[0] for _ in bonuses]
    return bonuses, allies

def _weapon_triangle_modifier_sources(unit, item):
    """Return direct-item and skill-override triangle multipliers separately."""
    item_values = [
        component.modify_weapon_triangle(unit, item)
        for component in getattr(item, 'components', [])
        if component.defines('modify_weapon_triangle')]
    override_components = (skill_system.item_override(unit, item)
                           if hasattr(unit, 'skills') else [])
    skill_values = [
        component.modify_weapon_triangle(unit, item)
        for component in override_components
        if component.defines('modify_weapon_triangle')]
    return (reduce(mul, item_values, 1),
            reduce(mul, skill_values, 1))


@ltcached
def compute_advantage(unit1, unit2, item1, item2, advantage=True) -> Optional[weapons.CombatBonus]:
    if not item1 or not item2:
        return None
    item1_weapontype = item_system.weapon_triangle_override(unit1, item1) or item_system.weapon_type(unit1, item1)
    item2_weapontype = item_system.weapon_triangle_override(unit2, item2) or item_system.weapon_type(unit2, item2)
    if not item1_weapontype or not item2_weapontype:
        return None
    if item_system.ignore_weapon_advantage(unit1, item1) or \
            item_system.ignore_weapon_advantage(unit2, item2):
        return None

    item_mod1, skill_mod1 = _weapon_triangle_modifier_sources(unit1, item1)
    item_mod2, skill_mod2 = _weapon_triangle_modifier_sources(unit2, item2)
    item_final_w_mod = (utils.sign(item_mod1) * utils.sign(item_mod2)
                        * max(abs(item_mod1), abs(item_mod2)))
    has_disadvantage = ((1 if advantage else -1)
                        * utils.sign(item_final_w_mod) < 0)
    multiplier_override = None
    if hasattr(unit1, 'skills'):
        multiplier_override = skill_system.weapon_triangle_multiplier_override(
            unit1, item1, unit2, item2, has_disadvantage,
            skill_mod1, skill_mod2)
    if multiplier_override is not None:
        skill_mod1, skill_mod2 = multiplier_override

    w_mod1 = item_mod1 * skill_mod1
    w_mod2 = item_mod2 * skill_mod2
    final_w_mod = utils.sign(w_mod1) * utils.sign(w_mod2) * max(abs(w_mod1), abs(w_mod2))

    if advantage:
        bonus = DB.weapons.get(item1_weapontype).advantage
    else:
        bonus = DB.weapons.get(item1_weapontype).disadvantage
    # bonus is a CombatBonusList
    highest_requirement_met = -1
    new_adv = None
    for adv in bonus:
        if adv.weapon_type == 'All' or adv.weapon_type == item2_weapontype:
            if adv.weapon_rank == 'All':
                new_adv = weapons.CombatBonus.copy(adv)
                new_adv.modify(final_w_mod)
                return new_adv
            # Figure out which Weapon Rank Bonus is highest that we meet
            requirement = DB.weapon_ranks.get(adv.weapon_rank).requirement
            if unit1.wexp[item1_weapontype] >= requirement and requirement > highest_requirement_met:
                highest_requirement_met = requirement
                new_adv = weapons.CombatBonus.copy(adv)
                new_adv.modify(final_w_mod)
    return new_adv

def compute_advantage_attr(attacker, defender, weapon, def_weapon, attribute: str) -> int:
    adv = compute_advantage(attacker, defender, weapon, def_weapon)
    disadv = compute_advantage(attacker, defender, weapon, def_weapon, False)
    mod = 0
    if adv:
        mod += int(getattr(adv, attribute))
    if disadv:
        mod += int(getattr(disadv, attribute))
    return mod


def _can_be_countered_sources(unit, item) -> Tuple[bool, bool]:
    """Return counterability from the item itself and skill overrides."""
    if not hasattr(unit, 'skills') or not hasattr(item, 'components'):
        return item_system.can_be_countered(unit, item), True

    base_values = [
        component.can_be_countered(unit, item)
        for component in item.components
        if component.defines('can_be_countered')]
    override_values = [
        component.can_be_countered(unit, item)
        for component in skill_system.item_override(unit, item)
        if component.defines('can_be_countered')]
    return (bool(base_values) and all(base_values), all(override_values))

def can_counterattack(attacker, aweapon, defender, dweapon) -> bool:
    if not dweapon:
        return False
    if not item_funcs.available(defender, dweapon):
        return False
    base_can_be_countered, override_can_be_countered = _can_be_countered_sources(
        attacker, aweapon)
    if not base_can_be_countered:
        return False
    if (not override_can_be_countered
            and not skill_system.negate_cannot_be_countered(defender)):
        return False
    if not item_system.can_counter(defender, dweapon):
        return False
    if not skill_system.can_counter(defender):
        return False
    if DB.constants.value('line_of_sight'):
        if not item_system.ignore_line_of_sight(defender, dweapon) and len(line_of_sight.line_of_sight([defender.position], [attacker.position], 99)) == 0:
            return False

    if not attacker.position:
        return True
    valid_targets = game.target_system.targets_in_range(defender, dweapon)
    if attacker.position in valid_targets:
        return True
    if skill_system.distant_counter(defender):
        return True
    if skill_system.close_counter(defender) and utils.calculate_distance(attacker.position, defender.position) == 1:
        return True
    return False

def accuracy(unit, item=None, target=None, target_item=None):
    if not item:
        item = unit.get_weapon()
    if not item:
        return None

    accuracy = item_system.hit(unit, item)
    if accuracy is None:
        return None

    equation = resolve_offensive_formula(
        unit, item,
        item_system.accuracy_formula, skill_system.accuracy_formula,
        item_system.accuracy_formula_override, skill_system.accuracy_formula_override,
        skill_system.Defaults.accuracy_formula)
    accuracy += equations.parser.get(equation, unit)

    weapon_rank_bonus = get_weapon_rank_bonus(unit, item, target, target_item)
    if weapon_rank_bonus:
        accuracy += int(weapon_rank_bonus.accuracy)

    support_rank_bonuses, support_allies = get_support_rank_bonus(unit)
    for bonus in support_rank_bonuses:
        accuracy += float(bonus.accuracy)
    accuracy = int(accuracy)

    if DB.constants.value('lead'):
        stars = sum(u.get_stat('LEAD') for u in game.get_all_units() if u.team == unit.team)
        accuracy += stars * equations.parser.get('LEAD_HIT', unit)

    accuracy += item_system.modify_accuracy(unit, item)
    accuracy += skill_system.modify_accuracy(unit, item)

    return accuracy

def avoid(unit, item, item_to_avoid=None):
    equation = resolve_defensive_formula(
        unit, item, None, item_to_avoid,
        item_system.avoid_formula, skill_system.avoid_formula,
        item_system.avoid_formula_override, skill_system.avoid_formula_override,
        skill_system.Defaults.avoid_formula)
    avoid = equations.parser.get(equation, unit)

    weapon_rank_bonus = get_weapon_rank_bonus(unit, item)
    if weapon_rank_bonus:
        avoid += int(weapon_rank_bonus.avoid)

    support_rank_bonuses, support_allies = get_support_rank_bonus(unit)
    for bonus in support_rank_bonuses:
        avoid += float(bonus.avoid)
    avoid = int(avoid)

    if DB.constants.value('lead'):
        target_stars = sum(u.get_stat('LEAD') for u in game.get_all_units() if u.team == unit.team)
        avoid += target_stars * equations.parser.get('LEAD_AVOID', unit)

    if item:
        avoid += item_system.modify_avoid(unit, item)
    avoid += skill_system.modify_avoid(unit, item)
    return avoid

def crit_accuracy(unit, item=None, allow_without_item_crit=False):
    if not item:
        item = unit.get_weapon()
    if not item:
        return None

    crit_accuracy = item_system.crit(unit, item)
    if crit_accuracy is None:
        if not allow_without_item_crit:
            return None
        crit_accuracy = 0

    equation = resolve_offensive_formula(
        unit, item,
        item_system.crit_accuracy_formula, skill_system.crit_accuracy_formula,
        item_system.crit_accuracy_formula_override, skill_system.crit_accuracy_formula_override,
        skill_system.Defaults.crit_accuracy_formula)
    crit_accuracy += equations.parser.get(equation, unit)

    weapon_rank_bonus = get_weapon_rank_bonus(unit, item)
    if weapon_rank_bonus:
        crit_accuracy += int(weapon_rank_bonus.crit)

    support_rank_bonuses, support_allies = get_support_rank_bonus(unit)
    for bonus in support_rank_bonuses:
        crit_accuracy += float(bonus.crit)
    crit_accuracy = int(crit_accuracy)

    crit_accuracy += item_system.modify_crit_accuracy(unit, item)
    crit_accuracy += skill_system.modify_crit_accuracy(unit, item)

    return crit_accuracy

def crit_avoid(unit, item, item_to_avoid=None):
    equation = resolve_defensive_formula(
        unit, item, None, item_to_avoid,
        item_system.crit_avoid_formula, skill_system.crit_avoid_formula,
        item_system.crit_avoid_formula_override, skill_system.crit_avoid_formula_override,
        skill_system.Defaults.crit_avoid_formula)
    avoid = equations.parser.get(equation, unit)

    weapon_rank_bonus = get_weapon_rank_bonus(unit, item)
    if weapon_rank_bonus:
        avoid += int(weapon_rank_bonus.dodge)

    support_rank_bonuses, support_allies = get_support_rank_bonus(unit)
    for bonus in support_rank_bonuses:
        avoid += float(bonus.dodge)
    avoid = int(avoid)

    if item:
        avoid += item_system.modify_crit_avoid(unit, item)
    avoid += skill_system.modify_crit_avoid(unit, item)
    return avoid

def damage(unit, item=None, target=None, target_item=None):
    if not item:
        item = unit.get_weapon()
    if not item:
        return None

    might = item_system.damage(unit, item)
    if might is None:
        return None

    equation = resolve_offensive_formula(
        unit, item,
        item_system.damage_formula, skill_system.damage_formula,
        item_system.damage_formula_override, skill_system.damage_formula_override,
        skill_system.Defaults.damage_formula)
    might += equations.parser.get(equation, unit)

    weapon_rank_bonus = get_weapon_rank_bonus(unit, item, target, target_item)
    if weapon_rank_bonus:
        might += int(weapon_rank_bonus.damage)

    support_rank_bonuses, support_allies = get_support_rank_bonus(unit)
    for bonus in support_rank_bonuses:
        might += float(bonus.damage)
    might = int(might)

    might += item_system.modify_damage(unit, item)
    might += skill_system.modify_damage(unit, item)

    return might

def defense(atk_unit, def_unit, item, item_to_avoid=None):
    low_prio_item_formula = item_system.resist_formula
    if skill_system.adaptive_damage(atk_unit) and skill_system.neutralize_foe_adaptive_damage(def_unit):
        def low_prio_item_formula(unit, weapon):
            formula = item_system.resist_formula(unit, weapon)
            return None if formula == 'WORSE_DEFENSE' else formula

    equation = resolve_defensive_formula(
        def_unit, item, atk_unit, item_to_avoid,
        low_prio_item_formula, skill_system.resist_formula,
        item_system.resist_formula_override, skill_system.resist_formula_override,
        skill_system.Defaults.resist_formula
    )
    res = equations.parser.get(equation, def_unit)

    weapon_rank_bonus = get_weapon_rank_bonus(def_unit, item)
    if weapon_rank_bonus:
        res += int(weapon_rank_bonus.resist)

    support_rank_bonuses, support_allies = get_support_rank_bonus(def_unit)
    for bonus in support_rank_bonuses:
        res += float(bonus.resist)
    res = int(res)

    if item:
        res += item_system.modify_resist(def_unit, item)
    res += skill_system.modify_resist(def_unit, item)
    return res

def attack_speed(unit, item=None):
    if not item:
        item = unit.get_weapon()
    if not item:
        return defense_speed(unit, item)

    equation = resolve_offensive_formula(
        unit, item,
        item_system.attack_speed_formula, skill_system.attack_speed_formula,
        item_system.attack_speed_formula_override, skill_system.attack_speed_formula_override,
        skill_system.Defaults.attack_speed_formula
    )
    attack_speed = equations.parser.get(equation, unit)

    weapon_rank_bonus = get_weapon_rank_bonus(unit, item)
    if weapon_rank_bonus:
        attack_speed += int(weapon_rank_bonus.attack_speed)

    support_rank_bonuses, support_allies = get_support_rank_bonus(unit)
    for bonus in support_rank_bonuses:
        attack_speed += float(bonus.attack_speed)
    attack_speed = int(attack_speed)

    attack_speed += item_system.modify_attack_speed(unit, item)
    attack_speed += skill_system.modify_attack_speed(unit, item)

    if not DB.constants.value('allow_negative_as') and attack_speed < 0:
        attack_speed = 0

    return attack_speed

def defense_speed(unit, item, item_to_avoid=None):
    equation = resolve_defensive_formula(
        unit, item, None, item_to_avoid,
        item_system.defense_speed_formula, skill_system.defense_speed_formula,
        item_system.defense_speed_formula_override, skill_system.defense_speed_formula_override,
        skill_system.Defaults.defense_speed_formula
    )
    speed = equations.parser.get(equation, unit)

    weapon_rank_bonus = get_weapon_rank_bonus(unit, item)
    if weapon_rank_bonus:
        speed += int(weapon_rank_bonus.defense_speed)

    support_rank_bonuses, support_allies = get_support_rank_bonus(unit)
    for bonus in support_rank_bonuses:
        speed += float(bonus.defense_speed)
    speed = int(speed)

    if item:
        speed += item_system.modify_defense_speed(unit, item)
    speed += skill_system.modify_defense_speed(unit, item)

    if not DB.constants.value('allow_negative_as') and speed < 0:
        speed = 0

    return speed

def compute_hit(unit, target, item, def_item, mode, attack_info, *, clamp_hit=True):
    if not item:
        return None

    hit = accuracy(unit, item, target, def_item)
    if hit is None:
        return 10000

    # Handles things like effective accuracy
    hit += item_system.dynamic_accuracy(unit, item, target, resolve_weapon(target), mode, attack_info, hit)

    # Weapon Triangle
    triangle_bonus = 0
    triangle_bonus += compute_advantage_attr(unit, target, item, def_item, 'accuracy')
    triangle_bonus -= compute_advantage_attr(target, unit, def_item, item, 'avoid')
    hit += triangle_bonus

    # Three Houses style support bonus (only works on attack)
    if mode in ('attack', 'splash'):
        # Attacker's accuracy bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(unit, target)
        for bonus in support_rank_bonuses:
            hit += float(bonus.accuracy)
    if mode == 'defense':
        # Attacker's avoid bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(target, unit)
        for bonus in support_rank_bonuses:
            hit -= float(bonus.avoid)
    hit = int(hit)

    hit -= avoid(target, def_item, item)

    hit += skill_system.dynamic_accuracy(unit, item, target, resolve_weapon(target), mode, attack_info, hit)
    hit -= skill_system.dynamic_avoid(target, resolve_weapon(target), unit, item, mode, attack_info, hit)

    if clamp_hit:
        return utils.clamp(hit, 0, 100)
    else:
        return max(hit, 0)

def compute_crit(unit, target, item, def_item, mode, attack_info):
    if not item:
        return None

    if skill_system.prevent_critical(unit, item, target):
        return 0
    crit = crit_accuracy(
        unit, item,
        allow_without_item_crit=skill_system.allow_critical(unit, item, target))
    if crit is None:
        return None

    # Handles things like effective accuracy
    crit += item_system.dynamic_crit_accuracy(unit, item, target, resolve_weapon(target), mode, attack_info, crit)

    # Weapon Triangle
    triangle_bonus = 0
    triangle_bonus += compute_advantage_attr(unit, target, item, def_item, 'crit')
    triangle_bonus -= compute_advantage_attr(target, unit, def_item, item, 'dodge')
    crit += triangle_bonus

    # Three Houses style support bonus (only works on attack)
    if mode in ('attack', 'splash'):
        # Attacker's crit bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(unit, target)
        for bonus in support_rank_bonuses:
            crit += float(bonus.crit)
    if mode == 'defense':
        # Attacker's dodge bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(target, unit)
        for bonus in support_rank_bonuses:
            crit -= float(bonus.dodge)
    crit = int(crit)

    crit -= crit_avoid(target, def_item, item)

    crit += skill_system.dynamic_crit_accuracy(unit, item, target, resolve_weapon(target), mode, attack_info, crit)
    crit -= skill_system.dynamic_crit_avoid(target, resolve_weapon(target), unit, item, mode, attack_info, crit)

    crit *= skill_system.crit_multiplier(unit, item, target, resolve_weapon(target), mode, attack_info, crit)
    crit = int(crit)

    return utils.clamp(crit, 0, 100)
    
def compute_damage_before_resist(unit, target, item, def_item, mode, attack_info, crit=False, assist=False):
    if not item:
        return None

    might = damage(unit, item, target, def_item)
    if might is None:
        return None

    # Handles things like effective damage
    might += item_system.dynamic_damage(unit, item, target, def_item, mode, attack_info, might)
    might += skill_system.dynamic_damage(unit, item, target, def_item, mode, attack_info, might)

    # Weapon Triangle
    triangle_bonus = 0
    triangle_bonus += compute_advantage_attr(unit, target, item, def_item, 'damage')
    triangle_bonus -= compute_advantage_attr(target, unit, def_item, item, 'resist')
    might += triangle_bonus

    # Three Houses style support bonus (only works on attack)
    if mode in ('attack', 'splash'):
        # Attacker's damage bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(unit, target)
        for bonus in support_rank_bonuses:
            might += float(bonus.damage)
    if mode == 'defense':
        # Attacker's resist bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(target, unit)
        for bonus in support_rank_bonuses:
            might -= float(bonus.resist)
    might = int(might)

    if assist:
        might //= 2

    might *= skill_system.damage_multiplier(unit, item, target, resolve_weapon(target), mode, attack_info, might)
    might *= skill_system.resist_multiplier(target, resolve_weapon(target), unit, item, mode, attack_info, might)
    
    return might
    
def compute_resist(unit, target, item, def_item, mode, attack_info, crit=False, assist=False):
    if not item:
        return None

    might = damage(unit, item, target, def_item)
    if might is None:
        return None

    # Handles things like effective damage
    might += item_system.dynamic_damage(unit, item, target, def_item, mode, attack_info, might)
    might += skill_system.dynamic_damage(unit, item, target, def_item, mode, attack_info, might)

    # Weapon Triangle
    triangle_bonus = 0
    triangle_bonus += compute_advantage_attr(unit, target, item, def_item, 'damage')
    triangle_bonus -= compute_advantage_attr(target, unit, def_item, item, 'resist')
    might += triangle_bonus

    # Three Houses style support bonus (only works on attack)
    if mode in ('attack', 'splash'):
        # Attacker's damage bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(unit, target)
        for bonus in support_rank_bonuses:
            might += float(bonus.damage)
    if mode == 'defense':
        # Attacker's resist bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(target, unit)
        for bonus in support_rank_bonuses:
            might -= float(bonus.resist)
    might = int(might)

    resist = defense(unit, target, def_item, item)
    resist += skill_system.dynamic_resist(target, resolve_weapon(target), unit, item, mode, attack_info, might)

    if assist:
        resist //= 2

    resist *= skill_system.damage_multiplier(unit, item, target, resolve_weapon(target), mode, attack_info, might)
    resist *= skill_system.resist_multiplier(target, resolve_weapon(target), unit, item, mode, attack_info, might)
    
    return resist

def compute_damage(unit, target, item, def_item, mode, attack_info, crit=False, assist=False):
    if not item:
        return None

    might = damage(unit, item, target, def_item)
    if might is None:
        return None

    # Handles things like effective damage
    might += item_system.dynamic_damage(unit, item, target, def_item, mode, attack_info, might)
    might += skill_system.dynamic_damage(unit, item, target, def_item, mode, attack_info, might)

    # Weapon Triangle
    triangle_bonus = 0
    triangle_bonus += compute_advantage_attr(unit, target, item, def_item, 'damage')
    triangle_bonus -= compute_advantage_attr(target, unit, def_item, item, 'resist')
    might += triangle_bonus

    # Three Houses style support bonus (only works on attack)
    if mode in ('attack', 'splash'):
        # Attacker's damage bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(unit, target)
        for bonus in support_rank_bonuses:
            might += float(bonus.damage)
    if mode == 'defense':
        # Attacker's resist bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(target, unit)
        for bonus in support_rank_bonuses:
            might -= float(bonus.resist)
    might = int(might)

    total_might = might

    def_value = defense(unit, target, def_item, item)
    def_value *= skill_system.defense_multiplier(unit, item, target, def_item, mode, attack_info, def_value)
    might -= def_value
    might -= skill_system.dynamic_resist(target, resolve_weapon(target), unit, item, mode, attack_info, might)

    if assist:
        might //= 2

    # So that crit can correctly multiply when the damage dealt would be less than min_damage
    might = int(max(DB.constants.value('min_damage'), might))

    if crit or skill_system.crit_anyway(unit):
        # Multiply Damage
        equation = skill_system.critical_multiplier_formula(unit)
        crit_mult = equations.parser.get(equation, unit)
        might *= crit_mult

        # Add damage
        equation = skill_system.critical_addition_formula(unit)
        crit_add = equations.parser.get(equation, unit)
        crit_add += item_system.modify_crit_damage(unit, item)
        crit_add += skill_system.modify_crit_damage(unit, item)
        might += crit_add

        # Thracia Crit
        equation = skill_system.thracia_critical_multiplier_formula(unit)
        thracia_crit = equations.parser.get(equation, unit)
        if thracia_crit:
            might += total_might * thracia_crit

    target_item = resolve_weapon(target)
    might *= skill_system.damage_multiplier(unit, item, target, target_item, mode, attack_info, might)
    if not skill_system.neutralize_foe_damage_reduction(unit):
        if not skill_system.reduce_resist_multiplier(unit, item, target, target_item, mode, attack_info, might):
            might *= skill_system.resist_multiplier(target, target_item, unit, item, mode, attack_info, might)
        else:
            might *= 1 - ((1 - skill_system.resist_multiplier(target, target_item, unit, item, mode, attack_info, might)) * skill_system.reduce_resist_multiplier(unit, item, target, target_item, mode, attack_info, might))
        might -= skill_system.flat_damage_reduction(target, target_item, unit, item, mode, attack_info, might)

    might += skill_system.raw_damage(unit, item, target, def_item, mode, attack_info, might)

    return int(max(int(DB.constants.get('min_damage').value), might))

def compute_assist_damage(unit, target, item, def_item, mode, attack_info, crit=False):
    return compute_damage(unit, target, item, def_item, mode, attack_info, crit, assist=True)

def compute_true_speed(unit, target, item, def_item, mode, attack_info) -> int:
    speed = attack_speed(unit, item)

    # Handles things like effective damage
    speed += item_system.dynamic_attack_speed(unit, item, target, resolve_weapon(target), mode, attack_info, speed)

    # Weapon Triangle
    triangle_bonus = 0
    triangle_bonus += compute_advantage_attr(unit, target, item, def_item, 'attack_speed')
    triangle_bonus -= compute_advantage_attr(target, unit, def_item, item, 'defense_speed')
    speed += triangle_bonus

    # Three Houses style support bonus (only works on attack)
    if mode in ('attack', 'splash'):
        # Attacker's attack_speed bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(unit, target)
        for bonus in support_rank_bonuses:
            speed += float(bonus.attack_speed)
    if mode == 'defense':
        # Attacker's defense_speed bonus
        support_rank_bonuses, support_allies = get_support_rank_bonus(target, unit)
        for bonus in support_rank_bonuses:
            speed -= float(bonus.defense_speed)
    speed = int(speed)

    speed -= defense_speed(target, def_item, item)

    speed += skill_system.dynamic_attack_speed(unit, item, target, resolve_weapon(target), mode, attack_info, speed)
    speed -= skill_system.dynamic_defense_speed(target, resolve_weapon(target), unit, item, mode, attack_info, speed)
    return speed

def outspeed(unit, target, item, def_item, mode, attack_info) -> int:
    if not item:
        return 0
    if not item_system.can_double(unit, item):
        return 0
    if skill_system.no_double(unit):
        return 0
    if skill_system.target_no_double(target) and not skill_system.negate_no_double(unit):
        return 0
    if mode == 'defense' and not (DB.constants.value('def_double') or skill_system.def_double(target)):
        return 0

    speed = compute_true_speed(unit, target, item, def_item, mode, attack_info)

    return 1 if speed >= equations.parser.speed_to_double(unit) else 0


@dataclass(frozen=True)
class AttackPhasePlan:
    total_phases: int
    early_phases: int
    # Proc grants are tracked separately so the solver can preserve a combat's
    # initial RNG result while still recalculating the non-RNG parts of a plan.
    proc_grants: int = 0


def compute_attack_phase_plan(unit, target, item, def_item, mode, attack_info,
                              proc_grants: Optional[int] = None) -> AttackPhasePlan:
    """Resolve additive follow-up phases while keeping early grants separately timed."""
    if not item:
        return AttackPhasePlan(0, 0)

    # These are hard limits.  Project data uses prevent_self_follow_up for
    # neutralizable effects; no_double remains for effects such as Bane.
    if not item_system.can_double(unit, item) or skill_system.no_double(unit):
        return AttackPhasePlan(1, 0)

    prevention = skill_system.prevent_self_follow_up(unit)
    if target:
        prevention = prevention or skill_system.prevent_foe_follow_up(target)
    if prevention and not skill_system.neutralize_follow_up_prevention(unit):
        return AttackPhasePlan(1, 0)

    base_phases = 1
    natural_phases = outspeed(unit, target, item, def_item, mode, attack_info) if target else 0
    natural_prevention = target and skill_system.prevent_foe_natural_follow_up(target)
    if natural_prevention and not skill_system.neutralize_follow_up_prevention(unit):
        natural_phases = 0

    legacy_dynamic_denied = target and skill_system.no_dynamic_attacks(target) \
        and not skill_system.negate_no_dynamic_attacks(unit)
    grants_neutralized = target and skill_system.neutralize_foe_follow_up_grants(target)
    if legacy_dynamic_denied or grants_neutralized:
        normal_grants = 0
        early_grants = 0
    else:
        target_item = resolve_weapon(target)
        normal_grants = item_system.dynamic_attacks(
            unit, item, target, target_item, mode, attack_info, base_phases)
        normal_grants += skill_system.dynamic_attacks(
            unit, item, target, target_item, mode, attack_info, base_phases)
        early_grants = skill_system.dynamic_early_attacks(
            unit, item, target, target_item, mode, attack_info, base_phases)

    eligible_phases = base_phases + natural_phases + normal_grants + early_grants
    if proc_grants is None:
        proc_grants = skill_system.dynamic_follow_up_proc_count(
            unit, item, target, def_item, mode, attack_info, eligible_phases)
    return AttackPhasePlan(
        eligible_phases + proc_grants,
        early_grants,
        proc_grants,
    )

def compute_attack_phases(unit, target, item, def_item, mode, attack_info) -> int:
    return compute_attack_phase_plan(unit, target, item, def_item, mode, attack_info).total_phases

def compute_multiattacks(unit, target, item, mode, attack_info):
    if not item:
        return None

    num_attacks = 1
    num_attacks += item_system.dynamic_multiattacks(unit, item, target, resolve_weapon(target), mode, attack_info, num_attacks)
    num_attacks += skill_system.dynamic_multiattacks(unit, item, target, resolve_weapon(target), mode, attack_info, num_attacks)

    return num_attacks
