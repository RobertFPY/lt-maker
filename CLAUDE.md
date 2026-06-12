# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Lex Talionis** is a Fire Emblem fangame engine (pygame runtime) plus **LT-maker**, a PyQt5 graphical editor built on top of it. A game is a `.ltproj` directory of JSON data + resources; the engine loads one and plays it, the editor mutates one. Two sample projects ship in-repo: `default.ltproj` (Sacred Stones) and `lion_throne.ltproj`.

## Commands

- Run the editor: `python run_editor.py`
- Run the engine on a project: `python run_engine.py` (auto-finds a `*.ltproj` in the repo root)
- Run the map maker: `python run_map_maker.py`
- Run all tests: `python -m unittest discover -s app/tests -p 'test*.py'` (wrapper: `./utilities/build_tools/run_tests.sh`)
- Run one test module: `python -m unittest app.tests.test_engine`
- Type check: `mypy app/` — config in `mypy.ini`, `strict = True`, **excludes** `app/editor`, `app/extensions`, `app/map_maker`, `app/tests`. New non-editor code is expected to pass strict typing.
- Build docs: `./docs/make.bat html` (output in `_build/html`)
- Install dev deps: `pip install -r requirements_dev.txt` (engine-only: `requirements_engine.txt`, editor: `requirements_editor.txt`). Python + PyQt5 + pygame-ce.

`LT_PROFILE=1` env var enables per-frame timing prints in `driver.py`; `LT_PROFILE_THRESHOLD=<ms>` only prints slow frames.

## Codegen — read this before editing components or event commands

`app/engine/codegen/source_generator.py::generate_all()` runs at startup (both entry points) when not a built release. It generates source files; **do not hand-edit generated files**, edit the inputs:

- `compile_item_system()` / `compile_skill_system()` scan `app/engine/item_components/*` and `app/engine/skill_components/*` and emit the big dispatch modules `app/engine/item_system.py` and `app/engine/skill_system.py`.
- `generate_event_command_python_wrappers()` emits Python wrappers for event commands.

If you add or change a component hook method and the engine doesn't pick it up, the generated dispatch file is stale — rerun `python -m app.engine.codegen.source_generator`.

## Architecture

Three top-level halves under `app/`:

- **`app/engine/`** — the runtime game (pygame). Entry: `driver.start()` then `driver.run(game)`, a fixed loop pulling input → `game.state.update()` → blit. The whole game is a singleton `GameState` (`game_state.py`) holding every registry (units, items, skills, regions, parties, teams, vars). Control flow is a **stack-based state machine** (`state_machine.py`, `state.py`); states are registered by string nid in `StateMachine.load_states` and pushed/popped (`game.state.change/back`). Combat lives in `app/engine/combat/` driven by a `solver` producing a `playback` log that map/animation combat replay. Live game objects are in `app/engine/objects/` (UnitObject, ItemObject, SkillObject, etc.) — these wrap the static DB prefabs with per-playthrough state.

- **`app/data/`** — the project data model and (de)serialization. Two global singletons: `DB` (`app/data/database/database.py`) for game design data and `RESOURCES` (`app/data/resources/resources.py`) for assets. Both `.load(path, version)` a `.ltproj`. On-disk format is versioned JSON; migration logic is in `app/data/serialization/` (`versions.py`, `migrators/`, `loaders/`). `CURRENT_SERIALIZATION_VERSION` gates load behavior. Validation in `app/data/validation/`; a project with `has_fatal_errors` refuses to launch.

- **`app/editor/`** — PyQt5 editor. One sub-package per data type (e.g. `item_editor/`, `class_editor/`, `event_editor/`), each typically a `*_tab.py` (Qt view), `*_model.py` (Qt model over the DB), and `*_properties.py` (the edit form). `main_editor.py` is the window. Editor state lives in `app/editor/lib/state_editor/`. The editor edits `DB`/`RESOURCES` in memory and serializes back to the `.ltproj`.

Also: **`app/events/`** — the eventing/scripting system, including a custom Python-eventing compiler under `app/events/python_eventing/` (analyzer → compiler → postcomp) that turns user event scripts into runnable code. Event triggers are defined in `app/events/triggers.py` (chapter start/end, unit death, talk, level up, etc.) and matched against `EventPrefab.triggers` at runtime. **`app/map_maker/`** — a separate procedural tile-map tool, with its own palette pipeline (see `app/map_maker/README.md`). **`app/engine/roam/`** — a free-roam exploration mode (town menus, NPC interactions) that runs as its own state machine alongside but separate from tactical map states; **`app/engine/overworld/`** — the node-based overworld graph (map selection, cinematics, route branching).

### Save / restart system

`app/engine/save.py` keeps **two parallel slot listings**: `SAVE_SLOTS` (the Load Game menu) and `RESTART_SLOTS` (the Restart Level menu). They are different files — `-{N}.p` vs `-restart{N}.p` — so a save can appear in one menu but not the other. Restart files are **slot-keyed** and seeded only at new game (the lone `kind=='start'` save in `title_screen.build_new_game`); every later save in `save_io` just **copies the restart file forward** from the slot you loaded into (`old_slot`) to the slot you save into. There is no per-chapter 'start' save.

Gotcha: **"Test Chapter"** (editor → engine via `game_state.start_level()`) bypasses new game entirely — it writes no 'start' save and leaves `current_save_slot = None`. So a first in-session save (e.g. a base/prep save) has no restart file to carry forward; `save_io` falls back to seeding the restart from that save, which is *not* a pristine chapter start. Preload saves (also `kind=='start'` only) are likewise never produced in a Test Chapter session.

### Component system

Items and skills are composed of **components**, not subclasses. A component (e.g. in `app/engine/item_components/formula_components.py`) declares `nid`, `tag`, an `expose` type for its editor field, and implements named **hook methods** like `damage_formula(unit, item)` or `on_hit(...)`. The codegen step collects all components and builds `item_system`/`skill_system` dispatch functions that fan a hook call out across whatever components an item/skill carries. To add a behavior: add a component class with the right hook method name, then regenerate. `item_component_access.py` / `skill_component_access.py` expose the catalogs.

Each hook method has a **resolution policy** controlling how multiple components' return values combine: `ALL_DEFAULT_FALSE` (any False → False; e.g., `is_weapon`), `UNIQUE` (last-defined wins; e.g., `damage_formula`), `NUMERIC_ACCUM` (sum all numerics; e.g., `modify_damage`), `UNION` (merge all returned sets; e.g., `target_icon`). The policy is declared alongside the hook in the codegen templates — pick the right one when adding a new hook.

### Aura system

An aura is a parent skill (carrying the Aura component) plus a shared **subskill** object that gets applied to every affected unit — one `SkillObject` instance, one uid, sitting in many units' skill lists at once. Affected units are tracked **only** by board bookkeeping (`game_board.known_auras` / `aura_grid`), never an explicit "who has my aura" list. `aura_funcs.py` is the whole system: `propagate_aura`/`release_aura` (source moves/leaves), `pull_auras` (a unit arrives), `repopulate_aura` (board rebuild on load).

Teardown must be **authoritative**, not board-derived. When a unit leaves the map it drops *all* its AURA-sourced skills (`aura_funcs.remove_all_auras`, called from `game.leave`) by walking its own skill list — a board-position lookup is fragile because `reset_aura` clears board state but not unit skill lists, so re-propagation / teardown ordering / save-load can desync the two and orphan a child skill. AURA `source_type` is non-removable and non-displaceable ([source_type.py](app/engine/source_type.py)): removable only via its exact source uid (the live parent skill instance). Aura children are therefore **not serialized** (`UnitObject.save`/`restore` filter `SourceType.AURA`); they're re-derived from the live board after units arrive on load (`game.load_level` → `pull_auras`) so each child's source points at the current parent. Skip this and a game-over restart restores children with a stale parent uid → unremovable forever (the "permanent aura skill" bug).

## Conventions

- Objects are referenced by string ids: **NID** (named id, design-time, stable across a project) and **UID** (unique id, runtime instance). Types in `app/utilities/typing.py`.
- Shared, framework-agnostic helpers live in `app/utilities/` (no Qt, no pygame deps) — prefer reusing `utils.py`, `str_utils.py`, `static_random.py` (deterministic RNG for turnwheel/replays) over rolling your own.
- The engine must stay importable without PyQt5 (it ships as a standalone executable); keep editor-only imports out of `app/engine`.
- A MAJOR_FEATURES DB constant (e.g. `support`, `fatigue`) is usually **not** the runtime gate — it enables the feature in the editor/UI. The actual runtime switch is a `_`-prefixed game var (`_supports`, `_fatigue`, `_convoy`, `_turnwheel`) set via an event command (e.g. `game_var;_supports;True`), often deliberately deferred to a story beat. When gating engine behavior on a feature, check the game var, and check it in **every** path (combat, info menu, accumulation, etc.) — a missing check in one path leaks the feature inconsistently.
- Tests live in `app/tests/`, mostly engine/data/event coverage (the editor is largely untested). Several tests load the sample `.ltproj`s, so don't break their data integrity (`test_base_project_integrity.py`).
- Tests share the **global `game` singleton** (`game_state.py::game`); its state leaks across tests within a run. A test that touches `game` must seed everything it reads (e.g. `game.game_vars = PrimitiveCounter()`, `game.target_system = …`) in `setUp` or its helper — never rely on what a prior test left behind, or you get order-dependent pass/fail that only shows up in the full suite, not when the test runs alone.
