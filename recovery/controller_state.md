# Recovery Controller State

> This file is the live controller-gate state for the recovery program.
> `plan.md` remains authoritative for architecture, task definitions, model assignments, escalation conditions, invariants, and acceptance criteria.
> This file overrides only the stale/static `CURRENT EXECUTION STATE` section in `plan.md` when they disagree.

## Current authorization

- Current phase: Phase 0
- Last reviewed task: `P0-T01`
- Last reviewed commit: `2f43d80ece1e3a3db9d9de18ac85c458a5b25012`
- Review result: **ACCEPTED**
- Next authorized task: **`P0-T02` only**
- P0-T02 primary: `GPT-5.6 Terra / medium`
- P0-T02 escalation target: `GPT-5.6 Sol / high`
- Escalation pre-authorized: **NO**
- Controller gate after P0-T02: **YES — STOP FOR CONTROLLER REVIEW**

## P0-T01 controller review

Accepted evidence:

- Commit `2f43d80ece1e3a3db9d9de18ac85c458a5b25012` adds only `recovery/baseline.md`.
- No engine, test, project-content, or gameplay behavior changes were made.
- Baseline records the local runtime/dependency environment.
- Full-suite observation was recorded as 311 `ok`, 8 `FAIL`, 1 `ERROR`, followed by abnormal process exit `-1073740791` (`0xC0000409`).
- Existing failures were categorized and not repaired during P0-T01.
- Android/runtime flags and profiling controls were inventoried.
- The baseline lists 81 `app/engine` files changed between the PC reference and recovery starting HEAD.
- No model escalation was used.

Non-blocking note:

- The report labels the timezone as `Asia/Bangkok`; the project/controller timezone is `Asia/Ho_Chi_Minh`. Both are UTC+7 for this date, so this does not invalidate baseline evidence. Use `Asia/Ho_Chi_Minh` in future recovery reports.

## P0-T02 execution constraints

Codex must execute only the P0-T02 task definition in `plan.md`.

Do not fix the baseline test failures during P0-T02. They are evidence, not the task scope.

The P0-T02 deliverable is `recovery/change_inventory.md` and must classify correctness-critical post-reference engine/runtime changes using the plan classification system. Uncertain semantic cases must be marked `NEEDS-CONTROLLER-DECISION` rather than guessed.

Escalate only under the P0-T02 conditions defined in `plan.md` (ESC-01, ESC-02, ESC-04, ESC-09). Do not self-escalate.
