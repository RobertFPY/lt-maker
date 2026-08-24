from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from app.engine.state import State

import logging

from app.engine.performance import RUNTIME_PROFILER


class SimpleStateMachine():
    def __init__(self, starting_state):
        self.state = []
        self.state.append(starting_state)

    def change(self, new_state):
        self.state.append(new_state)

    def back(self):
        self.state.pop()

    def get_state(self):
        if self.state:
            return self.state[-1]
        return None

    def clear(self):
        self.state.clear()

class StateMachine():
    def __init__(self):
        self.state: List[State] = []
        self.temp_state: List[str] = []
        self.prev_state: State = None
        self.prior_state: State = None
        self._presentation_request: str | None = None
        self._presentation_barrier_drawn = False
        # Recovery tracing is test-injected.  Normal runtime has no recorder.
        self.trace_recorder = None

    def set_trace_recorder(self, recorder):
        self.trace_recorder = recorder

    def _new_state(self, state_name: str) -> State:
        """Create a state with explicit lifecycle flags.

        Many engine states do not call ``State.__init__``.  Keeping these
        flags on every instance here makes lifecycle and draw safety uniform
        for all state implementations.
        """
        state = self.all_states[state_name](state_name)
        state.started = False
        state.processed = False
        return state

    def load_states(self, starting_states=None, temp_state=None):
        from app.engine import (android_debugger, base, chapter_title, debug_mode, dialog_log,
                                feat_choice, game_over, general_states,
                                level_up, minimap, objective_menu,
                                player_choice, prep, prep_gba, promotion,
                                settings, status_upkeep, text_entry,
                                title_screen, trade, transitions, turnwheel,
                                victory_screen, party_transfer, credit_state)
        from app.engine.game_menus.menu_states import unit_menu_state
        from app.engine.info_menu import info_menu_state
        from app.engine.overworld import overworld_states
        from app.engine.roam import free_roam_state, free_roam_rationalize
        from app.events import event_state, event_test, mock_event_state
        self.all_states = \
            {'title_start': title_screen.TitleStartState,
             'title_main': title_screen.TitleMainState,
             'title_load': title_screen.TitleLoadState,
             'title_load_job': title_screen.TitleLoadJobState,
             'title_restart': title_screen.TitleRestartState,
             'title_mode': title_screen.TitleModeState,
             'title_new': title_screen.TitleNewState,
             'title_new_child': title_screen.TitleNewChildState,
             'title_extras': title_screen.TitleExtrasState,
             'title_all_saves': title_screen.TitleAllSavesState,
             'title_wait': title_screen.TitleWaitState,
             'title_save': title_screen.TitleSaveState,
             'in_chapter_save': title_screen.TitleSaveState,
             'transition_in': transitions.TransitionInState,
             'transition_out': transitions.TransitionOutState,
             'transition_pop': transitions.TransitionPopState,
             'transition_double_pop': transitions.TransitionDoublePopState,
             'transition_to': transitions.TransitionToState,
             'transition_to_with_pop': transitions.TransitionToWithPopState,
             'start_level_asset_loading': general_states.LoadingState,
             'turn_change': general_states.TurnChangeState,
             'initiative_upkeep': general_states.InitiativeUpkeep,
             'free': general_states.FreeState,
             'option_menu': general_states.OptionMenuState,
             'option_child': general_states.OptionChildState,
             'in_chapter_load': general_states.InChapterLoadState,
             'in_chapter_load_job': general_states.InChapterLoadJobState,
             'settings_menu': settings.SettingsMenuState,
             'android_controls_editor': settings.AndroidControlsEditorState,
             'objective_menu': objective_menu.ObjectiveMenuState,
             'unit_menu': unit_menu_state.UnitMenuState,
             'info_menu': info_menu_state.InfoMenuState,
             'phase_change': general_states.PhaseChangeState,
             'move': general_states.MoveState,
             'movement': general_states.MovementState,
             'wait': general_states.WaitState,
             'canto_wait': general_states.CantoWaitState,
             'move_camera': general_states.MoveCameraState,
             'dying': general_states.DyingState,
             'menu': general_states.MenuState,
             'item': general_states.ItemState,
             'subitem_child': general_states.SubItemChildState,
             'item_child': general_states.ItemChildState,
             'item_discard': general_states.ItemDiscardState,
             'targeting': general_states.TargetingState,
             'trade': trade.TradeState,
             'combat_trade': trade.CombatTradeState,
             'weapon_choice': general_states.WeaponChoiceState,
             'spell_choice': general_states.SpellChoiceState,
             'spell_loadout_choice': general_states.SpellLoadoutChoiceState,
             'ability_multi_item_choice': general_states.AbilityMultiItemChoiceState,
             'ability_submenu_choice': general_states.AbilitySubmenuChoiceState,
             'combat_targeting': general_states.CombatTargetingState,
             'item_targeting': general_states.ItemTargetingState,
             'combat': general_states.CombatState,
             'alert': general_states.AlertState,
             'ai': general_states.AIState,
             'shop': general_states.ShopState,
             'repair_shop': general_states.RepairShopState,
             'unlock_select': general_states.UnlockSelectState,
             'exp': level_up.ExpState,
             'bonus_exp': level_up.ExpState,
             'promotion_choice': promotion.PromotionChoiceState,
             'class_change_choice': promotion.ClassChangeChoiceState,
             'promotion': promotion.PromotionState,
             'class_change': promotion.ClassChangeState,
             'feat_choice': feat_choice.FeatChoiceState,
             'turnwheel': turnwheel.TurnwheelState,
             'game_over': game_over.GameOverState,
             'chapter_title': chapter_title.ChapterTitleState,
             'event': event_state.EventState,
             'event_test_exit': event_test.EventTestExitState,
             'mock_event': mock_event_state.MockEventState,
             'player_choice': player_choice.PlayerChoiceState,
             'text_entry': text_entry.TextEntryState,
             'text_confirm': text_entry.TextConfirmState,
             'victory': victory_screen.VictoryState,
             'minimap': minimap.MinimapState,
             'status_upkeep': status_upkeep.StatusUpkeepState,
             'status_endstep': status_upkeep.StatusUpkeepState,
             'prep_main': prep.PrepMainState,
             'prep_pick_units': prep.PrepPickUnitsState,
             'prep_formation': prep.PrepFormationState,
             'prep_formation_select': prep.PrepFormationSelectState,
             'prep_formation_menu': prep.PrepFormationMenuState,
             'prep_manage': prep.PrepManageState,
             'prep_manage_select': prep.PrepManageSelectState,
             'optimize_all_choice': prep.OptimizeAllChoiceState,
             'base_manage': prep.PrepManageState,
             'base_manage_select': prep.PrepManageSelectState,
             'prep_trade_select': prep.PrepTradeSelectState,
             'prep_trade': trade.PrepTradeState,
             'prep_items': prep.PrepItemsState,
             'base_items': prep.PrepItemsState,
             'supply_items': prep.PrepItemsState,
             'prep_costume': prep.PrepCostumeState,
             'base_costume': prep.PrepCostumeState,
             'prep_restock': prep.PrepRestockState,
             'prep_use': prep.PrepUseState,
             'prep_market': prep.PrepMarketState,
             'prep_gba_main': prep_gba.PrepGBAMainState,
             'prep_gba_map': prep_gba.PrepGBAMapState,
             'base_main': base.BaseMainState,
             'base_market_select': base.BaseMarketSelectState,
             'base_bexp_select': base.BaseBEXPSelectState,
             'base_bexp_allocate': base.BaseBEXPAllocateState,
             'base_convos_child': base.BaseConvosChildState,
             'base_supports': base.BaseSupportsState,
             'base_codex_child': base.BaseCodexChildState,
             'base_library': base.BaseLibraryState,
             'base_guide': base.BaseGuideState,
             'base_records': base.BaseRecordsState,
             'base_achievement': base.BaseAchievementState,
             'base_sound_room': base.BaseSoundRoomState,
             'event_sound_room': base.BaseSoundRoomState,
             'extras_sound_room': base.BaseSoundRoomState,
             'extras_supports': base.BaseSupportsState,
             'free_roam': free_roam_state.FreeRoamState,
             'free_roam_rationalize': free_roam_rationalize.FreeRoamRationalizeState,
             'debug': debug_mode.DebugState,
             'android_debugger': android_debugger.AndroidDebuggerState,
             'debug_pick_position': debug_mode.DebugPositionPickerState,
             'debug_console': debug_mode.DebugConsoleState,
             'overworld': overworld_states.OverworldFreeState,
             'overworld_movement': overworld_states.OverworldMovementState,
             'overworld_game_option_menu': overworld_states.OverworldGameOptionMenuState,
             'overworld_party_option_menu': overworld_states.OverworldPartyOptionMenu,
             'overworld_on_node': overworld_states.OverworldNodeTransition,
             'overworld_next_level': overworld_states.OverworldLevelTransition,
             'dialog_log': dialog_log.DialogLogState,
             'party_transfer': party_transfer.PartyTransferState,
             'party_transfer_confirm': party_transfer.PartyTransferConfirmState,
             'credit': credit_state.CreditState
             }

        if starting_states:
            for state_name in starting_states:
                self.state.append(self._new_state(state_name))
        if temp_state:
            self.temp_state = temp_state

    def state_names(self):
        return [s.name for s in self.state]

    def change(self, new_state):
        self.temp_state.append(new_state)

    def back(self):
        self.temp_state.append('pop')

    def clear(self):
        self.temp_state.append('clear')

    def refresh(self):
        # Clears all states except the top one
        self.state = self.state[-1:]

    def current(self):
        if self.state:
            return self.state[-1].name

    def current_state(self) -> State:
        if self.state:
            return self.state[-1]

    def get_prev_state(self) -> State:
        """returns the state which precedes the current state on the stack"""
        if self.state and len(self.state) > 1:
            return self.state[-2]

    def get_prior_state(self) -> State:
        """return the state the state machine was just in. contrast with `get_prev_state`"""
        return self.prior_state

    def exit_state(self, state):
        if state.processed:
            state.processed = False
            if RUNTIME_PROFILER.enabled:
                with RUNTIME_PROFILER.section('state_end:' + state.name):
                    state.end()
            else:
                state.end()
        if RUNTIME_PROFILER.enabled:
            with RUNTIME_PROFILER.section('state_finish:' + state.name):
                state.finish()
        else:
            state.finish()

    def from_transition(self):
        return self.prev_state in ('transition_out', 'transition_to', 'transition_pop', 'transition_double_pop')

    def process_temp_state(self):
        committed = bool(self.temp_state)
        if self.temp_state:
            logging.debug("Temp State: %s", self.temp_state)
        for transition in self.temp_state:
            if transition == 'pop':
                if self.state:
                    state = self.state[-1]
                    self.exit_state(state)
                    self.prior_state = state
                    self.state.pop()
            elif transition == 'clear':
                self.prior_state = self.current_state()
                for state in reversed(self.state):
                    self.exit_state(state)
                self.state.clear()
            else:
                new_state = self._new_state(transition)
                self.prior_state = self.state[-1] if self.state else None
                self.state.append(new_state)
        if self.temp_state:
            logging.debug("State: %s", self.state_names())
        self.temp_state.clear()
        if committed and self.trace_recorder is not None:
            self.trace_recorder.state_transition_committed(self)

    def visible_states(self) -> List[State]:
        """Return the state stack segment that composes the current scene."""
        if not self.state:
            return []
        # Handles transparency of states
        idx = -1
        while True:
            if self.state[idx].transparent and len(self.state) >= (abs(idx) + 1):
                idx -= 1
            else:
                break
        return self.state[idx:]

    def update_visuals(self):
        """Advance every state that is visible, including paused underlays."""
        # Several transparent UI states inherit MapState. They compose the
        # same map behind them, so advancing each would make cursor/weather/
        # warp effects run twice in one simulation step.
        from app.engine.state import MapState
        map_visuals_updated = False
        for visible_state in self.visible_states():
            if isinstance(visible_state, MapState):
                if map_visuals_updated:
                    continue
                map_visuals_updated = True
            update_visuals = getattr(visible_state, 'update_visuals', None)
            if update_visuals:
                if RUNTIME_PROFILER.enabled:
                    with RUNTIME_PROFILER.section('state_visual:' + visible_state.name):
                        update_visuals()
                else:
                    update_visuals()

    def request_present(self, reason: str):
        """Ensure a newly-created visual cue reaches the next display update."""
        if self._presentation_request is None:
            self._presentation_request = reason

    def consume_presentation_barrier(self) -> bool:
        """Return whether this update forced a render, then clear the marker."""
        was_drawn = self._presentation_barrier_drawn
        self._presentation_barrier_drawn = False
        return was_drawn

    def draw(self, surf):
        """Draw the visible state stack at the normal state-machine draw point.

        A state below a transparent overlay may have been paused with
        ``end()`` and therefore no longer be ``processed``.  It is still part
        of the visible scene and must be allowed to draw.
        """
        for visible_state in self.visible_states():
            if RUNTIME_PROFILER.enabled:
                with RUNTIME_PROFILER.section('state_draw:' + visible_state.name):
                    surf = visible_state.draw(surf)
            else:
                surf = visible_state.draw(surf)
        return surf

    def update(self, event, surf, draw=True):
        if not self.state:
            return None, False
        state = self.state[-1]
        repeat_flag = False  # Whether we run the state machine again in the same frame
        profile_enabled = RUNTIME_PROFILER.enabled
        # Start
        if not state.started:
            state.started = True
            if profile_enabled:
                with RUNTIME_PROFILER.section('state_start:' + state.name):
                    start_output = state.start()
            else:
                start_output = state.start()
            if start_output == 'repeat':
                repeat_flag = True
            self.prev_state = state.name
        # Begin
        if not repeat_flag and not state.processed:
            state.processed = True
            if profile_enabled:
                with RUNTIME_PROFILER.section('state_begin:' + state.name):
                    begin_output = state.begin()
            else:
                begin_output = state.begin()
            if begin_output == 'repeat':
                repeat_flag = True
        # Take Input
        if not repeat_flag:
            if profile_enabled:
                with RUNTIME_PROFILER.section('state_input:' + state.name):
                    input_output = state.take_input(event)
            else:
                input_output = state.take_input(event)
            if input_output == 'repeat':
                repeat_flag = True
        # Update
        if not repeat_flag:
            if profile_enabled:
                with RUNTIME_PROFILER.section('state_update:' + state.name):
                    update_output = state.update()
            else:
                update_output = state.update()
            if update_output == 'repeat':
                repeat_flag = True
        # Rendering is deferred during fast-forward, but visible simulation
        # visuals must still advance once for this logical substep.  Skip it
        # for a repeat chain: that chain runs at the same timestamp and should
        # not make frame-based effects advance twice.
        force_draw = self._presentation_request is not None
        if not repeat_flag or force_draw:
            self.update_visuals()

        # A presentation request is a lightweight fence for a cue such as a
        # briefly shown cursor.  It forces this otherwise deferred substep to
        # compose one frame; the driver will stop remaining substeps.
        # Draw.  ``draw`` defaults to True to preserve the desktop sequence.
        # An event command batch can yield after mutating the map but before
        # its next transition command.  Retain the already-presented surface
        # for that one host frame rather than exposing the intermediate map.
        should_draw = (draw or force_draw) and (not repeat_flag or force_draw)
        defer_render = bool(getattr(state, 'should_defer_render', lambda: False)())
        if should_draw and (force_draw or not defer_render):
            surf = self.draw(surf)
            if force_draw:
                self._presentation_request = None
                self._presentation_barrier_drawn = True
        elif should_draw and defer_render and profile_enabled:
            RUNTIME_PROFILER.count('event_budget_deferred_draw')
        # End
        if self.temp_state and state.processed:
            state.processed = False
            if profile_enabled:
                with RUNTIME_PROFILER.section('state_end:' + state.name):
                    state.end()
            else:
                state.end()
        # Finish
        if profile_enabled:
            with RUNTIME_PROFILER.section('state_transition_commit'):
                self.process_temp_state()  # This is where FINISH is taken care of
        else:
            self.process_temp_state()  # This is where FINISH is taken care of
        return surf, repeat_flag

    def save(self):
        return [state.name for state in self.state], self.temp_state[:]  # Needs to be a copy!!!
