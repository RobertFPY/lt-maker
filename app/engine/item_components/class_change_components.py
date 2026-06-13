from app.data.database.database import DB

from app.data.database.item_components import ItemComponent, ItemTags
from app.data.database.components import ComponentType

from app.engine.game_state import game

class Promote(ItemComponent):
    nid = 'promote'
    desc = "Promotes the targeted unit (most often the user) into whatever promotions their class has available to them."
    tag = ItemTags.CLASS_CHANGE

    _did_hit = False
    _will_show_choice = False

    def _check_show_choice(self, target) -> bool:
        # Whether using this item presents a cancellable promotion choice
        # (multiple options) rather than a forced, single promotion.
        if not target:
            return False
        klass = DB.classes.get(target.klass)
        return len(klass.turns_into) >= 2

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        self._did_hit = True
        self._will_show_choice = self._check_show_choice(target)

    def menu_after_combat(self, unit, item):
        # When the item will present a cancellable promotion choice, return to
        # the unit's menu instead of finalizing the turn, so the choice can be
        # backed out of cleanly. The turn is finalized on confirm instead
        # (see PromotionState in promotion.py).
        return self._will_show_choice

    def end_combat(self, playback, unit, item, target, item2, mode):
        if self._did_hit and target:
            klass = DB.classes.get(target.klass)
            if len(klass.turns_into) == 0:
                return
            elif len(klass.turns_into) == 1:
                new_klass = klass.turns_into[0]
            else:
                new_klass = None
            game.memory['current_unit'] = target
            game.memory['combat_item'] = item
            game.memory['can_go_back'] = True
            if new_klass:
                game.memory['next_class'] = new_klass
                game.memory['next_state'] = 'promotion'
                game.state.change('transition_to')
            else:
                game.memory['next_state'] = 'promotion_choice'
                game.state.change('transition_to')
        self._did_hit = False
        self._will_show_choice = False

class ForcePromote(Promote):
    nid = 'force_promote'
    desc = "Forcibly promotes the targeted unit into the class specified in the component."
    tag = ItemTags.CLASS_CHANGE

    expose = ComponentType.Class

    def _check_show_choice(self, target) -> bool:
        return False  # Forced promotion is never a cancellable choice

    def end_combat(self, playback, unit, item, target, item2, mode):
        if self._did_hit and target:
            game.memory['current_unit'] = target
            game.memory['next_class'] = self.value
            game.state.change('promotion')
            game.state.change('transition_out')
        self._did_hit = False

class ClassChange(Promote):
    nid = 'class_change'
    desc = "Item allows target to change class after hit. Define reclass options on the unit's unit screen."
    tag = ItemTags.CLASS_CHANGE

    def _check_show_choice(self, target) -> bool:
        if not target or target.generic:
            return False
        unit_prefab = DB.units.get(target.nid)
        if not unit_prefab or not unit_prefab.alternate_classes:
            return False
        return len(unit_prefab.alternate_classes) >= 2

    def end_combat(self, playback, unit, item, target, item2, mode):
        if self._did_hit and target:
            unit_prefab = DB.units.get(target.nid)
            if target.generic or not unit_prefab:
                return
            if not unit_prefab.alternate_classes:
                return
            elif len(unit_prefab.alternate_classes) == 1:
                new_klass = unit_prefab.alternate_classes[0]
            else:
                new_klass = None
            game.memory['current_unit'] = target
            game.memory['combat_item'] = item
            game.memory['can_go_back'] = True
            if new_klass:
                game.memory['next_class'] = new_klass
                game.state.change('class_change')
                game.state.change('transition_out')
            else:
                game.state.change('class_change_choice')
                game.state.change('transition_out')
        self._did_hit = False
        self._will_show_choice = False

class ForceClassChange(Promote):
    nid = 'force_class_change'
    desc = "Item forcibly changes target's class after hit"
    tag = ItemTags.CLASS_CHANGE

    expose = ComponentType.Class

    def _check_show_choice(self, target) -> bool:
        return False  # Forced class change is never a cancellable choice

    def end_combat(self, playback, unit, item, target, item2, mode):
        if self._did_hit and target:
            game.memory['current_unit'] = target
            game.memory['next_class'] = self.value
            game.state.change('class_change')
            game.state.change('transition_out')
        self._did_hit = False
