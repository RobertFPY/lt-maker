# PC Core Semantics Recovery — Master Execution Plan

> **Status:** SEMANTIC RECOVERY COMPLETE — historical execution specification; no task is active
> **Plan owner / controller:** ChatGPT (planner, reviewer, gatekeeper)
> **Executor:** Codex (implementation agent only)
> **Recovery branch:** `recovery/pc-core-semantics`
> **PC behavioral reference:** `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`
> **Recovery starting HEAD:** `0821182a717de2baaf52a699ee325241ffaddd03`
> **Android introduction / mixed-change landmark:** `52bd040317f16b7973602dd78e769ed990501549`
> **Model policy:** GPT-5.6 token-optimized execution policy v2
> **Policy date:** 2026-08-08
> **Plan revision:** PLAN-V2-R3 executable-contract closure, 2026-08-12
> **Live authorization authority:** `recovery/controller_state.md`

---

# 0. PURPOSE AND AUTHORITY

This file is the authoritative execution plan for restoring the gameplay core to the original PC semantics while preserving later features, correctness fixes, safe shared optimizations, and Android-specific optimizations that do not alter gameplay behavior.

The original recovery execution is complete. PLAN-V2 strengthens the contract for audit, replay, or any controller-authorized reopening; it does not retroactively claim that the new requirements were used to accept the completed history. Accepted historical evidence remains recorded in `recovery/controller_state.md` and the committed recovery reports.

## 0.1 Current four-verdict status

These verdicts separate the accepted historical recovery result from evidence that the stricter PLAN-V2 contract still requires. They are informational and do not authorize work or retroactively invalidate a controller acceptance.

| Gate | Current disposition | Scope and limitation |
|---|---|---|
| **SEMANTIC RECOVERY** | **COMPLETE / PASS** | Historical controller acceptance covers PC semantics, shared-core invariants, feature preservation, and architecture contamination. |
| **ANDROID RUNTIME EQUIVALENCE** | **PASS — accepted WSA scope** | Current-provenance x86_64 WSA evidence covers the accepted runtime synchronization scenarios; it is not physical-device performance proof or exact on-device Trace V1. |
| **ANDROID PERFORMANCE QUALIFICATION** | **BLOCKED / NOT ESTABLISHED under PLAN-V2** | No qualifying physical `arm64-v8a` matrix, raw p99-equivalent dataset, release-equivalent device run, or same-device baseline/pre-locked absolute budget is recorded. |
| **MERGE / RELEASE** | **BLOCKED / AWAITING P9-T04-R3, P9-T05, AND EXPLICIT AUTHORIZATION under PLAN-V2-R3** | The completed semantic recovery does not authorize `master` mutation, merge, push, tag, or a claim of fully qualified Android performance; a future merge decision also requires fresh R3 validation and an accepted rehearsal against exact pinned tips. |

`recovery/controller_state.md` remains the authority for historical acceptance and live authorization. Any future controller-state update should preserve the four verdicts rather than collapsing them into one `PASS`.

PLAN-V2 operational readiness is separately **BLOCKED** until the controller accepts the authority/provenance lock, historical bootstrap, independently reviewed packet registry/validator, machine-readable dependency graph, Trace V2 migration, coverage matrix, and Trace V2 oracle lock required by Sections 7.1.0 through 7.1.4, 7.2, 7.4, and 7.9. This does not reopen or retroactively invalidate the accepted historical recovery.

## 0.2 Canonical live-status contract

Every future `recovery/controller_state.md` update must expose these fields independently and verbatim enough for humans and tooling to distinguish them:

```text
SEMANTIC RECOVERY: PASS | PASS WITH APPROVED EXCEPTIONS | PARTIAL | FAIL | BLOCKED
ANDROID RUNTIME EQUIVALENCE: PASS | PASS WITH APPROVED EXCEPTIONS | PARTIAL | FAIL | BLOCKED
ANDROID PERFORMANCE QUALIFICATION: PASS | PASS WITH APPROVED EXCEPTIONS | PARTIAL | FAIL | BLOCKED
MERGE / RELEASE: AUTHORIZED | AWAITING AUTHORIZATION | BLOCKED
AUTHORIZED TASK: <one task ID> | NONE
ACCEPTED SCOPE / DEVICE CLASS:
ACTIVE WAIVER IDS:
EVIDENCE MANIFEST:
CONTROLLER DECISION + DATE:
```

Status rules:

- a legacy label such as `full Android regression/performance matrix: PASS` proves only the exact scope stated by its accepted report;
- WSA/emulator runtime acceptance never implies physical-device performance qualification;
- if `ANDROID PERFORMANCE QUALIFICATION` is absent or only an old combined verdict exists, interpret qualification as `BLOCKED / NOT ESTABLISHED`, never PASS;
- `Release blockers: NONE` under a historical contract does not silently authorize merge/release or satisfy later PLAN-V2 performance evidence;
- a historical P9-T04/final review does not satisfy the fresh `P9-T04-R3` validation prerequisite or P9-T05 for a future merge;
- a controller-state migration is a separate controller-authorized documentation task. This plan-only revision does not mutate the current live state.

## 0.3 Target document topology

PLAN-V2-R3 defines the following target separation so live status, stable architecture, executable packets, and evidence do not drift inside one large document:

| Artifact | Single responsibility |
|---|---|
| `plan.md` | Stable recovery constitution, invariants, model policy, DAG, and artifact index. |
| `recovery/controller_state.md` | Mutable live authorization and the canonical four-verdict status only. |
| `recovery/tasks/<task-id>.md` | One executable Section 7.1 task packet per authorized task. |
| `recovery/task_index.json` | Packet identity, status, predecessor SHAs, and validator result. |
| `recovery/dependency_graph.json` | The single machine-readable task DAG, including global reopen gates and explicitly authorized emergency routes. |
| `recovery/evidence/<task-id>/manifest.json` | Immutable command, environment, raw-log, artifact, and result evidence. |
| `recovery/semantic_coverage_matrix.json` | Invariant-to-scenario-to-evidence coverage required by Section 7.9. |
| `recovery/transactions/<transaction-id>.json` | Linearization point, ordered side effects, compensation, cancellation, and fault-injection contract. |
| `recovery/presentation/<contract-id>.md` | Hash-registered child contract for visible-output correctness that remains separate from logical Trace equality. |
| `recovery/evidence/<task-id>/dirty_custody.json` | Pre/post identity for tracked, untracked, protected, and relevant ignored paths. |
| preservation ledger, waiver registry, and oracle lock | Durable semantic exceptions, supersession decisions, and oracle custody. |

Until the separately authorized document-topology migration in Section 7.1.3 is accepted, this file remains self-contained and authoritative; missing target files grant no authority. A split must be a semantic no-op, retain a hash-identified pre-split snapshot, update repository reading instructions in the same authorized task, and fail closed during any dual-read transition.

Codex is an **executor**, not the project architect. Codex must not redesign this plan, widen task scope, skip gates, accept behavioral divergence for performance, or decide that a workaround is acceptable without controller approval.

The controller is responsible for:

- architecture and semantic decisions;
- selecting the active task;
- selecting the primary model/effort and escalation target;
- approving phase transitions;
- reviewing diffs, tests, traces, benchmarks, and regressions;
- deciding whether an optimization is behavior-preserving;
- deciding whether Android-only specialization is acceptable;
- deciding whether a workaround is removed, retained, or rewritten;
- approving escalation when a task exceeds the primary model's safe scope.

Codex is responsible for:

- reading repository instructions and this plan before every task;
- executing exactly one authorized task packet;
- staying inside the authorized scope;
- writing tests/diagnostics required by that task;
- running the specified verification;
- reporting evidence and unresolved risks;
- stopping at controller or escalation gates.

The user is the bridge between Codex and the controller when review or model switching is required.

---

# 1. MANDATORY CODEX SESSION PROTOCOL

Before editing any file, Codex must:

1. Read root `AGENTS.md` in full.
2. Read root `AGENTS.override.md` in full if present.
3. Read this entire `plan.md`.
4. Read `recovery/controller_state.md` in full.
5. Identify the exact authorized task ID from live controller state or an explicit controller authorization that names the task, scope, model, effort, and Git restrictions.
6. Read the task's **PRIMARY MODEL**, **PRIMARY EFFORT**, **ESCALATION TARGET**, and approved task packet.
7. Detect and state the current model and reasoning effort using environment-provided metadata; self-assertion alone is insufficient when metadata is available.
8. Inspect `git status`, current branch, current HEAD, and the task's allowed-path diff.
9. Verify prerequisites, phase-exit manifest, controller gates, waivers, and required evidence inputs.
10. Refuse recovery work directly on `master`.
11. Enforce the primary model/effort gate unless the controller explicitly authorized escalation for the current task.
12. Fail closed if `plan.md`, `controller_state.md`, or the explicit controller authorization disagree beyond the exact scope of a later one-off authorization described in Section 1.5; report the mismatch and make no edits.

Before implementation, print:

```text
TASK: <ID>
AUTHORIZATION ID / ISSUER / EXPIRY: <identity>
PRIMARY MODEL: <model>
PRIMARY EFFORT: <effort>
CURRENT MODEL: <detected model>
CURRENT EFFORT: <detected effort>
ESCALATION TARGET: <model + effort or NONE>
ESCALATION AUTHORIZED: YES | NO
BRANCH: <branch>
HEAD: <sha>
SCOPE: <files/modules>
INVARIANTS: <INV ids>
PREREQUISITES: <task ids / controller approvals>
TASK PACKET: <path or inline controller authorization>
PLAN / CONTROLLER-STATE / DEPENDENCY-GRAPH HASHES: <identities>
ALLOWED PATHS: <exact allowlist>
BASE SHA: <pre-task sha>
DIRTY BASELINE: <pre-existing paths preserved>
DIRTY-CUSTODY MANIFEST: <path + sha256>
```

If the current model or effort cannot be detected, STOP before editing.

## 1.1 Primary model gate

The primary model is the **cheapest model judged sufficient to start the task safely**.

Codex must start with the exact primary model and exact primary effort unless the controller explicitly authorized an escalation for this task.

A stronger model is **not automatically authorized**. If the task says `GPT-5.6 Terra / medium` and Codex is running `GPT-5.6 Sol / max`, STOP and request the primary configuration. This prevents unnecessary token expenditure.

On mismatch:

```text
MODEL GATE FAILED
Task: <ID>
Required primary: <model / effort>
Current: <model / effort>
Action: switch to the required primary configuration, or provide explicit controller escalation authorization.
```

Then STOP without edits.

## 1.2 Escalation gate

Codex must never self-escalate.

If an escalation condition is reached:

1. stop editing;
2. preserve current work without expanding scope;
3. run any safe diagnostics already authorized;
4. report the exact evidence;
5. request the task's escalation target;
6. wait for the user/controller to authorize the new model/effort.

Required output:

```text
MODEL ESCALATION REQUIRED
TASK: <ID>
PRIMARY: <model / effort>
REQUESTED ESCALATION: <model / effort>
TRIGGER: <named escalation condition>
EVIDENCE:
- ...
SAFE WORK COMPLETED:
- ...
UNRESOLVED:
- ...
ACTION: switch model/effort only after controller authorization.
```

## 1.3 Global escalation conditions

Escalation is justified only when at least one of these is true:

- **ESC-01 Reference ambiguity:** PC reference behavior cannot be determined unambiguously from code/tests/traces.
- **ESC-02 Nonlocal root cause:** a failure crosses a second correctness-critical subsystem not in the original bounded implementation.
- **ESC-03 Trace divergence:** deterministic logical traces diverge after a locally correct implementation and the cause is not presentation-only.
- **ESC-04 Competing semantics:** two plausible implementations produce different gameplay semantics.
- **ESC-05 Invariant failure:** the first safe implementation exposes a deeper invariant violation rather than a local coding defect.
- **ESC-06 Save compatibility conflict:** preserving old/current save behavior requires a format or migration decision.
- **ESC-07 Android boundary conflict:** the desired performance gain appears to require partial live gameplay state or changed gameplay ordering.
- **ESC-08 Repeated local failure:** one bounded repair plus one bounded correction still cannot satisfy the task's acceptance tests.
- **ESC-09 Unplanned architecture:** implementation requires a new cross-cutting abstraction or architectural choice not already approved.
- **ESC-10 Release reconciliation:** final evidence from multiple subsystems conflicts and requires global prioritization.

Do not escalate merely because a task is large, test execution is slow, or a stronger model is available.

## 1.4 Availability rule

If the required primary or authorized escalation model/effort is unavailable in the current Codex environment, STOP and report it. Do not choose a substitute yourself.

## 1.5 Live authorization and status rule

`recovery/controller_state.md` is the only mutable live authorization source. This plan defines architecture and task contracts but must not contain an independently actionable "next task" assignment.

- If live state says `NONE`, no recovery implementation is authorized unless a later explicit controller authorization opens exactly one named task under the next rule.
- A stale status line in this file never authorizes work.
- A later one-off explicit controller authorization may supersede `NONE` only for its named task and must state authorization ID/issuer/report expiry, task, model/effort, escalation rule, exact writable scope, forbidden scope, base/plan hashes, protected dirty baseline, acceptance checks, and Git disposition. Its content hash is recorded before editing. It does not change any other controller-state fact and expires at task report.
- Any ambiguity or mismatch outside that exact later authorization fails closed before edits.

## 1.6 Branch rule

Recovery implementation must occur on:

`recovery/pc-core-semantics`

or a short-lived child branch explicitly authorized by the controller.

Never force-push, rewrite shared history, reset `master`, or perform a broad revert unless an active task explicitly authorizes it.

## 1.7 No autonomous phase advancement

Completing one task does not authorize another.

Every task requires a recorded controller acceptance before its successor may start. Codex must stop after every task report; the user/controller later supplies the next authorized task ID.

Task definitions use **REVIEW CLASS** only to select review depth:

- **ROUTINE** — deterministic collection, bounded implementation, or repetitive verification under a frozen contract;
- **ARCHITECTURE** — semantic, transactional, cross-class, platform-boundary, or phase-exit judgment;
- **FINAL** — release reconciliation and final controller disposition.

`REVIEW CLASS` never grants advancement authority. There is no ungated task and no `No` value that permits Codex to self-advance.

## 1.8 No silent substitutions

Codex must never silently:

- substitute a different model or effort;
- weaken a failing test;
- change acceptance criteria;
- update reference/golden behavior to match a regression;
- preserve an optimization merely because it improves FPS;
- remove a desired feature because recovery is difficult;
- modify project content/assets to make engine tests pass unless explicitly authorized;
- expand a local task into an architectural refactor.

---

# 2. GPT-5.6 TOKEN-OPTIMIZED MODEL POLICY

The allocation rule is:

```text
Luna  -> mechanical / deterministic / report / repetitive verification
Terra -> default coding workhorse for bounded engineering
Sol   -> semantic architecture, nonlocal debugging, high-blast-radius reconciliation
Ultra -> escalation only, not a default coding mode
```

Reasoning effort is a **budget**, not a prestige setting.

## 2.1 Luna

Use `GPT-5.6 Luna` when the task is deterministic, low-risk, and its desired output is already structurally known.

Typical use:

- baseline capture;
- running existing test matrices;
- report generation;
- profiler observer checks;
- repetitive tests following an approved pattern;
- mechanical documentation/cleanup.

Default efforts:

- `low` for deterministic collection/verification;
- `medium` when repository reasoning is needed but no semantic choice is allowed.

Luna must escalate rather than make architectural decisions.

## 2.2 Terra

Use `GPT-5.6 Terra` as the **default coder**.

Typical use:

- implementing an approved design;
- regression harnesses;
- compatibility audits;
- localized refactors with explicit contracts;
- feature preservation;
- Android adapters behind approved interfaces;
- performance/cache audits with clear invariants;
- semantic inventory where classification rules are already defined.

Default efforts:

- `medium` for routine bounded engineering;
- `high` for difficult bounded work or one sensitive subsystem.

Terra should be preferred over Sol whenever architecture is already frozen and the task can be verified by explicit tests/traces.

## 2.3 Sol

Use `GPT-5.6 Sol` only when the task requires semantic judgment with meaningful blast radius.

Typical use:

- authoritative `GameState` transaction semantics;
- combat lifecycle reconciliation;
- canonical load transaction semantics;
- ambiguous PC-vs-current behavior;
- Android scheduling boundaries that may leak partial state;
- nonlocal regression debugging;
- final architecture contamination/release reconciliation.

Default efforts:

- `high` for difficult cross-system implementation after architecture is known;
- `max` for architecture-critical reasoning/reconciliation;
- `ultra` only as an escalation target for unresolved, high-blast-radius conflicts.

## 2.4 Cost discipline

A task should be assigned to the lowest tier that can safely satisfy its acceptance tests.

Before upgrading model or effort, prefer:

1. narrowing scope;
2. using the existing behavioral trace;
3. adding a deterministic failing test;
4. comparing directly with `9314f54b`;
5. collecting targeted profiler or state evidence.

Only then escalate if a Section 1.3 condition applies.

---

# 3. NON-NEGOTIABLE SYSTEM INVARIANTS

These invariants override performance goals.

## INV-01 — One gameplay core

PC and Android share one authoritative gameplay implementation. Do not create separate gameplay engines.

## INV-02 — PC semantics are the behavioral reference

For systems that existed before Android work, `9314f54b` is the initial behavioral reference unless a later independent correctness fix or explicitly preserved feature supersedes it.

The reference is behavioral, not textual. Do not blindly copy old files.

## INV-03 — No observable partial gameplay state

Live gameplay code must never observe a half-restored or half-built state.

Forbidden examples include:

- restored map state while level/tilemap is missing;
- camera/map state active before the map is valid;
- board swapped before aura/fog/regions are valid;
- combat hooks split so unrelated logic observes an intermediate combat transaction.

## INV-04 — Android may optimize platform policy, not gameplay ordering

Android may differ in rendering, frame presentation, audio streaming, resource preload, memory/cache policy, filesystem/build integration, and background preparation that does not mutate authoritative gameplay state.

Android must not differ in combat solver semantics, action/event/RNG/hook ordering, logical state-machine transitions, or final logical state at synchronization points.

## INV-05 — Shared optimizations must be behavior-preserving

Shared optimizations require equivalent logical traces and output semantics.

## INV-06 — Fast-forward changes time, not outcomes

Identical seed/input with fast-forward ON and OFF must produce the same logical action trace and final game state. Only waits/presentation timing may differ.

## INV-07 — Debugger and profiler are observers

Enabling debugger/profiler without a mutating debug command must not change gameplay behavior, state ordering, RNG, or cache validity.

## INV-08 — Feature preservation

Preserve intended later features and legitimate fixes, including at minimum:

- fast-forward / speed controls;
- debugger functionality on PC and Android;
- runtime profiling;
- restart game/chapter functionality;
- save/load enhancements;
- later independent gameplay correctness fixes;
- Android build support;
- accepted Android audio/resource behavior.

## INV-09 — Project content is protected

Game data, resources, animations, portraits, levels, events, classes, items, skills, and unrelated editor improvements are not rollback targets.

## INV-10 — Evidence before optimization retention

A performance change that cannot demonstrate semantic equivalence remains disabled/rejected from shared core until proved safe.

---

# 4. RECOVERY CLASSIFICATION

Every post-reference engine change must be classified as one of:

- **KEEP-SHARED** — behavior-preserving optimization, feature, or bugfix useful on both platforms.
- **KEEP-PLATFORM** — platform-specific implementation preserving shared gameplay semantics.
- **REWRITE-PLATFORM** — Android goal is valid but implementation contaminates core semantics.
- **RESTORE-PC-SEMANTICS** — current implementation alters gameplay/lifecycle semantics.
- **REMOVE-WORKAROUND** — workaround exists only because an invalid staged/partial state was introduced.
- **KEEP-CORRECTNESS-FIX** — later fix repairs a real invariant independent of Android.

---

# 5. HIGH-RISK COMMIT / SUBSYSTEM MAP

Strong keep candidates:

- `7735ca29` — hierarchical runtime profiling.
- `6631e736` — debugger/render-panel performance work, subject to parity tests.
- `97c58a63` — difficulty setup correctness fix.
- `a566ae6d` — Windows editor workspace fix.
- `d2bbd026` — Android profiler thread isolation.
- `9004c67b` — Android streamed battle music as platform behavior.
- Android build/config/tooling that does not alter gameplay semantics.
- Project content/resource changes.

High-risk recovery cluster:

- `cdd4be2a` — staged tilemap board rebuild.
- `6b96e2f1` — batched tilemap transition state.
- `78acb08a` through `fff0145d` — staged combat sequence.
- `390638ac` — camera guard during staged restore.
- `6bd9da4b` — map-safety guards for staged loading.
- `8306e1a9` — deferred saved state until level restore completes.

`52bd0403` is a mixed commit. Never revert it wholesale.

---

# 6. SYNCHRONIZATION POINTS

PC and Android logical state must match at synchronization points regardless of presentation timing.

Examples:

- after level load fully commits;
- before player control begins;
- after movement commits;
- after combat cleanup/state-stack handling completes;
- after an event command transaction completes;
- after tilemap change commits;
- after save restore commits;
- after chapter restart reaches playable state;
- after phase transition completes.

Compare logical state at synchronization points, not arbitrary render frames.

---

# 7. CODEX TASK REPORT FORMAT

After each task:

```text
TASK RESULT: PASS | PASS WITH APPROVED EXCEPTIONS | PARTIAL | FAIL | BLOCKED
TASK PACKET ID/PATH + EXTERNAL INDEXED CONTENT SHA-256 / CONTROLLER AUTHORIZATION:
AUTHORIZATION ID / ISSUER / EXPIRY:
PLAN / CONTROLLER-STATE / DEPENDENCY-GRAPH HASHES:
TASK INDEX / VALIDATOR IDENTITY:
BASE SHA:
FINAL SHA:
PRE-EXISTING DIRTY PATHS:
DIRTY-CUSTODY MANIFEST + PRE/POST RESULT:
ALLOWED-PATH DIFF:
FILES CHANGED:
BEHAVIORAL CHANGES:
TESTS ADDED/UPDATED:
COMMANDS RUN:
EXIT CODES / TEST RESULTS:
REFERENCE COMPARISON:
PERFORMANCE IMPACT (if measured):
TRACE / COMPARATOR / MANIFEST IDENTITIES:
TRANSACTION-CONTRACT IDS:
PRESENTATION-CONTRACT IDS:
EVIDENCE MANIFEST + RAW LOG HASHES:
WAIVER IDS:
INDEPENDENT REVIEWER + HASH-PINNED INPUTS + VERDICT:
KNOWN RISKS:
UNRESOLVED QUESTIONS:
ESCALATION TRIGGERS ENCOUNTERED:
ROLLBACK ANCHOR / VERIFICATION:
COMMIT SHA(S) OR AUTHORIZED UNCOMMITTED DISPOSITION:
NEXT ACTION: CONTROLLER REVIEW | NONE
```

Never claim PASS if required tests were skipped, waived, blocked, or unavailable. Use PASS WITH APPROVED EXCEPTIONS only under Section 7.3.

## 7.1 Mandatory task packet contract

The phase descriptions below define intent. They are not independently executable. Before any production, test, Trace, performance, or recovery implementation starts, the controller must approve a packet at `recovery/tasks/<task-id>.md` containing every field below. A one-off inline authorization is permitted only for bounded documentation-only work, must contain the same authority fields, and expires at its report.

```text
TASK ID:
OBJECTIVE:
AUTHORIZATION ID / ISSUER / ISSUED-AT / EXPIRES-AFTER:
AUTHORIZATION TEXT SHA-256:
PRIMARY MODEL / EFFORT:
ESCALATION TARGET / TRIGGERS:
RISK:
PREDECESSOR TASKS + ACCEPTED SHAS:
PLAN SHA-256 / CONTROLLER-STATE SHA-256:
DEPENDENCY-GRAPH VERSION + SHA-256:
PACKET ID (stable identifier; not a content digest):
PHASE-EXIT MANIFEST:
IN SCOPE:
OUT OF SCOPE:
ALLOWED PATHS / SYMBOLS:
FORBIDDEN PATHS:
INPUT EVIDENCE + HASHES:
REQUIRED OUTPUT ARTIFACTS:
INVARIANTS:
EXACT COMMANDS + EXPECTED EXIT CODES:
TRACE / GOLDEN SCENARIO IDS:
NEGATIVE / FAULT-INJECTION TESTS:
TRANSACTION-CONTRACT IDS:
PRESENTATION-CONTRACT IDS:
PERFORMANCE WORKLOAD + LOCKED THRESHOLDS:
WAIVER IDS:
BASE SHA + DIRTY BASELINE:
DIRTY-CUSTODY MANIFEST PATH + INPUT SHA-256:
COMMIT / UNCOMMITTED DISPOSITION:
ROLLBACK PROCEDURE + ROLLBACK VERIFICATION:
PASS / PASS-WITH-EXCEPTIONS / PARTIAL / FAIL RULES:
INDEPENDENT REVIEWER / INPUT HASHES / REQUIRED VERDICT:
REVIEW CLASS: ROUTINE | ARCHITECTURE | FINAL
ADVANCE AUTHORITY: CONTROLLER ONLY
```

Rules:

- Missing, vague, or `TBD` fields block implementation unless the field is explicitly `NOT APPLICABLE` with controller rationale.
- Exact commands include working directory, environment variables, interpreter/tool path, selection filters, and expected exit code or expected failure signature.
- Allowed paths are an allowlist, not examples. Scope expansion requires a revised controller-approved packet.
- More than five files or more than one independent subsystem triggers an explicit task-sizing review; it does not force a file-count split. Split work into controller-approved vertical, invariant-preserving slices such as `P3-T03A`, `P3-T03B`, and `P3-T03C`. Every intermediate slice/commit must remain importable, keep its required focused suite green, publish no partial architecture, and have an independent rollback. When one coherent transaction necessarily crosses more than five files, the controller may approve one larger atomic packet and must record why splitting would create a less safe intermediate state.
- Every implementation task requires at least one test that fails for the broken semantic condition and passes for the recovered condition. Transactional/concurrent tasks also require fault-injection or cancellation coverage.
- Every packet must name the exact coverage-matrix row IDs it owns and the exact evidence-manifest output path.
- `recovery/task_index.json`, never the packet body, stores the packet content SHA-256. Before hashing, the validator requires the packet file to be UTF-8 without BOM with LF line endings, then hashes those exact bytes without transformation. A packet must not embed or interpolate its own digest; `PACKET ID` is only a stable lookup key. The index entry binds that ID, relative path, byte length, content SHA-256, authorization ID/hash, plan/controller/graph hashes, and independent validation result. Any byte or line-ending drift invalidates the indexed packet until reauthorization/revalidation.
- The packet validator and task index required by Section 7.1.2 must pass before implementation. A human-readable packet without a passing machine validation result is BLOCKED.
- Authorization identity is content-addressed. A copied prompt, stale conversation, expired one-off grant, or authorization whose plan/controller/base hashes do not match is not authority.
- The validator must check transitive dependency closure against the single machine-readable graph required by Section 7.2; scattered prose or heading order never supplies a missing edge.
- Bootstrap exception: because `P-V2-O01` creates the registry/validator, `P-V2-S00`, `P-V2-B00`, `P-V2-O01`, and `P-V2-D00` may start from complete inline controller authorizations under Section 1.5. They have documentation/evidence/tooling authority only. Before `P-V2-O01` runs, its authorization must freeze the bootstrap schema, authorization identity, expected positive/negative fixture outcomes, base/plan/controller hashes, and independent reviewer. `P-V2-O01` may index its final packet only after the independent bootstrap review passes; it must never use a validator it authored as the sole evidence that the validator itself is correct. No production task may use this exception.
- Historical accepted tasks are not retroactively invalidated by PLAN-V2. Any replay, correction, or reopening must satisfy this packet contract.

## 7.1.0 PLAN-V2 authority and provenance lock

**Task ID:** `P-V2-S00`
**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / high`, only on ESC-01 or ESC-09
**Risk:** Medium - authority drift only; no production authority
**Review class:** ARCHITECTURE

Before any PLAN-V2 bootstrap or reopened work, the controller must authorize `P-V2-S00` to migrate live status to the canonical four-verdict form and bind the accepted PLAN-V2 revision to immutable identities. A plan-only revision such as `PLAN-V2-R3` does not execute this task and cannot update live authorization by editing its own informational status text.

`P-V2-S00` records at minimum:

- authorization ID, issuer, issued-at time, expiry/report boundary, and authorization-text SHA-256;
- accepted `plan.md` path, source revision, output SHA-256, and controller decision;
- `controller_state.md` input/output SHA-256 and the four independent verdicts;
- repository/branch/base SHA, protected paths, and pre-existing dirty custody;
- explicit statement that historical acceptance is preserved and no recovery implementation is opened; and
- the exact successor authorized, or `NONE`.

Acceptance requires a read-only independent review of the hash-pinned before/after documents, no change to engine/tests/Trace/goldens/project data/assets/Git history, and a controller disposition that names the accepted plan and controller-state hashes. Any missing identity, combined Android verdict, or reusable authorization text is BLOCKED.

## 7.1.1 PLAN-V2 historical bootstrap and reopen gate

PLAN-V2's stricter packets and manifests were added after the original recovery was accepted. Historical acceptance remains valid under its recorded contract, but a later task must not pretend that PLAN-V2 artifacts already existed.

**Task ID:** `P-V2-B00`
**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / high`, only on ESC-01 or ESC-09
**Prerequisite:** accepted `P-V2-S00`
**Risk:** Medium — evidence custody only; no production authority
**Review class:** ARCHITECTURE

Before replaying, correcting, or reopening any accepted task later than P0-T01, the controller must authorize the evidence-only bootstrap task `P-V2-B00`. It has no production authority and creates or updates only controller-approved recovery evidence artifacts, normally:

- `recovery/plan_v2_historical_acceptance_manifest.json`;
- `recovery/plan_v2_preservation_supersession_ledger.json`;
- `recovery/plan_v2_waiver_registry.json`;
- `recovery/semantic_coverage_matrix.json`; and
- `recovery/oracle_custody_inventory_v1.json`, which identifies existing Trace V1 assets without claiming they satisfy the PLAN-V2 ordered-stream contract.

`P-V2-B00` must map each historical task/phase to its accepted commit SHA, report path, evidence identities, invariant disposition, known exceptions, rollback anchor, and controller decision. It may classify evidence only as `VERIFIED`, `HISTORICAL-ACCEPTED`, `UNKNOWN`, `MISSING`, `CONFLICTING`, or `BLOCKED`; `BLOCKED` must name the unmet prerequisite and never hides missing evidence.

Bootstrap rules:

1. It must not modify engine code, tests, Trace schema, comparator, normalizer, the Trace fixture manifest, goldens, fixtures, project data, assets, or Git history.
2. It must not manufacture a retroactive PASS, infer an absent measurement, or silently convert a historical limitation into a PLAN-V2 waiver.
3. `UNKNOWN`, `MISSING`, or `CONFLICTING` evidence remains explicit and blocks only the claims/tasks that depend on it.
4. A reopened task starts from the accepted SHA named in the bootstrap manifest plus a new complete Section 7.1 packet; report existence alone remains insufficient.
5. The controller must accept the bootstrap artifacts before any reopened implementation begins.
6. Trace V1 remains historical evidence. Because it records RNG snapshots rather than every correctness-relevant ordered draw, `P-V2-B00` must classify exact ordered-stream coverage as `MISSING` or `BLOCKED`; it must not create or label a complete PLAN-V2 exact-equivalence oracle lock.

Acceptance:

- every listed artifact exists, validates against its controller-approved schema, and has a recorded SHA-256;
- every historical task and verdict maps to an accepted SHA/report or remains explicitly `UNKNOWN`, `MISSING`, or `CONFLICTING`;
- no unresolved classification affecting a proposed reopened task is hidden or downgraded;
- the Trace V1 custody inventory distinguishes synchronization-state evidence from missing ordered-stream evidence;
- the allowed-path diff contains evidence artifacts only; and
- the controller records an explicit `P-V2-B00` disposition.

## 7.1.2 PLAN-V2 packet registry and validator gate

**Task ID:** `P-V2-O01`
**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / high`, only on ESC-09
**Prerequisite:** accepted `P-V2-S00` and `P-V2-B00`
**Risk:** Low — operational documentation/tooling only; no production authority
**Review class:** ROUTINE

Before any reopened implementation, the controller must authorize `P-V2-O01` to create:

- `recovery/tasks/<task-id>.md` packets using the exact Section 7.1 schema;
- `recovery/task_index.json` with externally computed exact-byte packet hashes, predecessor SHAs, disposition, and validator identity;
- `recovery/dependency_graph.json` with one explicit typed, acyclic edge set for governance/documentation, the T01-to-T03 Trace bootstrap, normal reopen, isolated emergency, presentation child plans, validation, and merge rehearsal;
- a deterministic packet validator at a controller-approved tooling path; and
- focused validator fixtures covering valid packets, missing fields, `TBD`, invalid allowlists, stale predecessor SHAs, dependency cycles/reversed Trace-bootstrap edges, and unauthorized advancement.

Validator rules:

1. Validation is read-only with respect to production, tests, Trace/golden, project data/assets, controller state, and Git history.
2. The validator checks schema completeness, the UTF-8-without-BOM/LF packet byte contract, absence of a self-digest field, exact allowed/forbidden paths, model/effort, typed acyclic dependencies, coverage row IDs, evidence output, rollback, result rules, and controller signature/decision identity; it computes the exact packet bytes' SHA-256 and compares only with the external index entry.
3. Inline implementation packets are invalid; documentation-only one-off authorizations remain governed by Section 1.5.
4. A packet or validator change invalidates its prior index hash and requires controller re-acceptance.
5. Bootstrap trust inputs are controller-frozen before implementation: schema hash, authorization identity, expected fixture results, plan/controller/base hashes, and reviewer identity. The validator may not generate or revise its own expected answers during the acceptance run.
6. A reviewer other than the validator author receives only hash-pinned schema, source, fixtures, expected outcomes, task packet, and dependency graph; the required verdict is `APPROVE` or `REQUEST CHANGES`.
7. The validator rejects missing transitive edges, duplicate authority, expired authorization, self-referential packet identity, non-canonical packet bytes, packet/index/hash drift, self-certification without the independent verdict, and any emergency path not enumerated in the graph.

Acceptance:

- positive and negative validator fixtures pass with exact expected exit codes;
- the independent bootstrap reviewer returns `APPROVE` against unchanged hash-pinned inputs;
- every proposed reopened task has one indexed packet and no duplicate task ID;
- the index, graph, packet, validator, schema, authorization, reviewer-input, and fixture hashes are captured in the evidence manifest; and
- no production/runtime behavior changes.

## 7.1.3 Document-topology migration

**Task ID:** `P-V2-D00`
**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / high`, only on ESC-09
**Prerequisite:** accepted `P-V2-S00`, `P-V2-B00`, and `P-V2-O01`
**Risk:** Medium — authority/read-order drift if performed incorrectly
**Review class:** ARCHITECTURE

`P-V2-D00` implements the target topology in Section 0.3 before any new multi-task recovery phase. It must preserve a hash-identified pre-split plan snapshot, update repository reading instructions and links atomically, prove that exactly one file owns each mutable fact, and provide a validator that detects duplicate/conflicting authority. An isolated emergency correction may proceed without waiting for this split only when the machine-readable graph contains the exact emergency route and its controller-approved packet still satisfies `P-V2-S00`, `P-V2-B00`, `P-V2-O01`, the applicable Trace V2/oracle gate, dirty custody, transaction/presentation contracts, and affected coverage rows.

The split must not alter recovery semantics, historical verdicts, task acceptance, engine/tests/Trace/goldens, project data/assets, or Git history. Until the controller accepts `P-V2-D00`, `plan.md` remains the authority described at the top of this file.

## 7.1.4 Trace V2 ordered-stream migration and oracle gate

Historical Trace V1 and its fixtures remain immutable evidence for the recovery already accepted. They are insufficient for a new exact-equivalence claim because initial/final RNG state cannot prove draw ordering. PLAN-V2 exact equivalence therefore requires the following separately authorized tasks; none may share a packet or commit with a production fix.

### P-V2-T01 - Design Trace V2

**Task ID:** `P-V2-T01`
**Primary:** `GPT-5.6 Sol / high`
**Escalation:** `GPT-5.6 Sol / max`, only on ESC-01 or ESC-09
**Prerequisite:** accepted `P-V2-S00`, `P-V2-B00`, `P-V2-O01`, and either accepted `P-V2-D00` or an enumerated isolated route
**Risk:** High - semantic observer contract and cross-stream ordering
**Review class:** ARCHITECTURE

Define a versioned observer-safe contract for ordered action/reversal, hook, event, playback, state-stack, cache-publication, and correctness-relevant RNG records. Each RNG draw includes `stream_id`, monotonic `draw_index`, operation/domain or bounds, result, and pre/post state digest without consuming an extra draw. The design must specify version coexistence, normalization limits, device transport, fixture migration, performance/observer budget, and an explicit proof strategy that disabled and enabled tracing preserve behavior.

The accepted design must also define one capture-only PC-reference instrumentation procedure. It starts from an isolated worktree at exact commit `9314f54b` and records its resolved pristine Git tree hash, applies one hash-pinned observer patch under a closed path/symbol allowlist, and produces a separately identified derived capture tree. The procedure must define how tooling proves every path outside that allowlist is byte-identical to the pristine reference tree and how generated outputs, project data, dependencies, and runtime inputs remain unchanged. The pristine reference tree is the semantic source; the derived tree is only an observation vehicle and cannot contain a correctness or product fix.

**STOP FOR CONTROLLER REVIEW.**

### P-V2-T02 - Implement and disprove observer effects

**Task ID:** `P-V2-T02`
**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`, only on ESC-03, ESC-05, or ESC-09
**Prerequisite:** accepted `P-V2-T01`
**Risk:** High - instrumentation can perturb the behavior it observes
**Review class:** ARCHITECTURE

Implement only the accepted Trace V2 contract. Mandatory negative tests prove no extra RNG draw, no changed exception/scheduling/action order, no mutation while the recorder is absent, no cross-stream index collision, deterministic cancellation/error cleanup, and V1 custody preservation. Trace schema/recorder/tests may change only inside this task's exact allowlist; production recovery fixes remain forbidden.

T02 must also materialize and independently review the capture-only reference observer patch specified by T01. In a disposable worktree rooted at commit `9314f54b`, record the pristine commit and resolved tree hash, patch SHA-256, exact changed path/symbol allowlist, derived tree hash, and a full-tree proof that all non-allowlisted paths are identical. Run the locked scenarios on the pristine tree and derived tree with Trace disabled, then run the derived tree with Trace OFF and ON under the accepted observer-effect assertions. Any product-output, exception, ordering, RNG, scheduling, generated-file, or non-allowlisted byte difference blocks T03; test success alone never authorizes widening the observer patch.

**STOP FOR CONTROLLER REVIEW.**

### P-V2-T03 - Repeatability, PC recapture, and immutable Trace V2 oracle lock

**Task ID:** `P-V2-T03`
**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`, only on ESC-01 or ESC-03
**Prerequisite:** accepted `P-V2-T02`
**Risk:** High - immutable oracle custody and reference recapture
**Review class:** ARCHITECTURE

Run at least three fresh-process reference captures per required scenario from the controller-accepted derived capture tree in a disposable worktree, with pinned input, dependencies, locale/time settings, project hashes, and RNG setup. Never edit or describe `9314f54b` itself as Trace-V2-instrumented. Identical canonical output is required before new fixtures are locked. Create the versioned manifest and `recovery/oracle_lock_v2.json`, preserve all V1 assets, and obtain an independent read-only `APPROVE` verdict over the pristine reference tree identity, derived capture tree identity, observer-patch hash/allowlist, non-allowlisted equality proof, Trace OFF/ON evidence, schema, recorder, runner, comparator, normalizer, fixtures, raw captures, and repeatability evidence.

Any reopened production task claiming exact equivalence depends on accepted `P-V2-T03`. Until then it may report historical Trace V1 synchronization evidence or bounded device observations, but it must not say `EXACT PLAN-V2 EQUALITY`.

**STOP FOR CONTROLLER REVIEW.**

## 7.2 Dependency graph and phase-exit manifests

The dependency graph is fail-closed. `accepted X` means the controller recorded the result, commit SHA, evidence path, waivers, and invariant disposition in the phase-exit manifest. After `P-V2-O01`, `recovery/dependency_graph.json` is the single executable dependency authority; this table is a human-readable projection and must hash-match the graph. The validator computes transitive closure and rejects any task whose direct or global predecessor is missing.

The normal PLAN-V2 reopen spine is:

```text
P-V2-S00 -> P-V2-B00 -> P-V2-O01 -> P-V2-D00
    -> P-V2-T01 -> P-V2-T02 -> P-V2-T03
    -> <affected audit/design task or P-V2-P00> -> <bounded production fix>
    -> semantic/runtime validation -> P9-T04-R3 -> P9-T05
    -> separate MERGE / RELEASE authorization
```

An isolated emergency route may replace only the `P-V2-D00` edge and must be a separately named graph branch with controller rationale, exact expiry, and unchanged global gates. It cannot skip `P-V2-S00`, `P-V2-B00`, `P-V2-O01`, required Trace V2/oracle coverage, dirty custody, transaction/presentation contracts, or independent review. No prose phrase such as "emergency" creates an edge.

Every graph node carries a validator-enforced route type. `GOVERNANCE_ONLY` covers `P-V2-S00`, `P-V2-B00`, `P-V2-O01`, and `P-V2-D00`; a Section 1.5 bounded documentation-only authorization is `DOCUMENTATION_ONLY`. Those routes may run without `P-V2-T03` but cannot touch production code/tests/Trace/goldens, execute runtime behavior, or make a semantic/presentation/performance claim. `TRACE_BOOTSTRAP` is reserved exclusively for the acyclic `P-V2-T01 -> P-V2-T02 -> P-V2-T03` chain: T01 and T02 may precede accepted T03 solely to design/implement/prove the Trace observer under their exact allowlists, T03 completes the route, and none grants product-fix authority or downstream semantic acceptance before T03 is accepted. There is no packet-level `NOT APPLICABLE` or generic property-oracle escape from Trace V2 for downstream product-behavior work. Shared optimizations, presentation work, and every downstream task touching RNG, actions, events, hooks, ordering, state publication, transactions, saves, or gameplay/runtime semantics must inherit accepted `P-V2-T03`; property and presentation oracles supplement rather than replace that edge.

| Task | Required predecessor |
|---|---|
| P-V2-S00 | Explicit controller authorization; accepted plan/controller/base identities; no recovery implementation opened |
| P-V2-B00 | accepted P-V2-S00; required before any PLAN-V2 replay/correction/reopening of accepted history |
| P-V2-O01 | accepted P-V2-S00 and P-V2-B00; independent bootstrap-validator review required |
| P-V2-D00 | accepted P-V2-S00, P-V2-B00, and P-V2-O01; required unless the graph names an isolated emergency route |
| P-V2-T01 | accepted P-V2-O01 and accepted P-V2-D00 or enumerated isolated route |
| P-V2-T02 | accepted P-V2-T01 |
| P-V2-T03 | accepted P-V2-T02; required before any new exact-equivalence production claim |
| P-V2-P00 | accepted P-V2-T03 and accepted P-V2-D00 or enumerated isolated route; required before a presentation child plan can authorize production work |
| P0-T01 | Controller authorization and recovery base SHA |
| P0-T02 | accepted P0-T01 |
| P1-T01 | accepted P0-T02 |
| P1-T02 | accepted P1-T01 |
| P1-T03 | accepted P1-T02 |
| P2-T01 | accepted Phase 1 exit manifest |
| P2-T02 | accepted P2-T01 |
| P2-T03 | accepted P2-T02 |
| P3-T01 | accepted Phase 2 exit manifest |
| P3-T02 | accepted P3-T01 |
| P3-T03 | accepted P3-T02 |
| P3-T04 | accepted P3-T03 |
| P4-T01 | accepted Phase 3 exit manifest |
| P4-T02 | accepted P4-T01 |
| P4-T03 | accepted P4-T02 |
| P5-T01 | accepted Phase 4 exit manifest |
| P5-T02 | accepted P5-T01 |
| P5-T03 | accepted P5-T02 |
| P6-T01 | accepted Phase 5 exit manifest |
| P6-T02 | accepted P6-T01 |
| P6-T03 | accepted P6-T02 |
| P7-T01 | accepted Phase 6 exit manifest |
| P7-T02 | accepted P7-T01 |
| P7-T03 | accepted P7-T02 |
| P7-T04 | accepted P7-T03 |
| P8-T01 | accepted Phase 7 exit manifest |
| P8-T02 | accepted P8-T01 |
| P8-T03 | accepted P8-T02 |
| P8-T04 | accepted P8-T03 |
| P9-T01 | accepted Phase 8 exit manifest |
| P9-T02 | accepted P9-T01 |
| P9-T03 | accepted P9-T02 semantic/runtime sub-gates; performance qualification may remain separately blocked |
| P9-T04 | accepted P9-T03 plus complete recovery phase-exit manifest |
| P9-T04-R3 | fresh PLAN-V2-R3 validation instance after accepted P-V2-T03 and graph-selected audit/fix/validation closure; bound to the exact recovery tip; historical P9-T04 cannot satisfy this node |
| P9-T05 | accepted matching P9-T04-R3 plus the same pinned recovery tip, pinned target-branch tip, and explicit rehearsal authorization; required before MERGE / RELEASE authorization |

The P0-T01 through P9-T04 rows describe their historical order. Any downstream production-behavior replay, correction, reopening, shared optimization, presentation, performance, or validation task inherits the full global PLAN-V2 spine through accepted `P-V2-T03`; no task packet may waive that edge. Only the explicitly typed governance/documentation routes and the ordered Trace-bootstrap chain itself may precede accepted T03. The graph, not omission from a legacy row or a prose `NOT APPLICABLE`, decides that inheritance.

Each phase-exit manifest must record:

- accepted task IDs and exact commit SHAs;
- task packet and evidence-report paths;
- task-index/validator/dependency-graph identities and affected coverage-matrix row IDs;
- invariant status and unresolved risks;
- historical Trace V1 custody identity and accepted Trace V2 schema/comparator/fixture-manifest/oracle-lock identities where applicable;
- waiver IDs and expiry/recheck triggers;
- preservation/supersession ledger coverage and unresolved entry IDs;
- required-test completion and exact exception signatures;
- rollback anchors;
- controller decision and timestamp.

No phase number, heading order, report existence, or prior conversational statement substitutes for this manifest.

## 7.3 Result and waiver policy

Task results have these meanings:

- **PASS** — every required check ran and passed; no active waiver affects the task's acceptance claims.
- **PASS WITH APPROVED EXCEPTIONS** — all non-waived checks passed and every exception has an active controller waiver. This status must not be shortened to PASS.
- **PARTIAL** — authorized work produced useful evidence but one or more acceptance criteria remain unmet.
- **FAIL** — evidence contradicts the contract or a required non-waived check failed.
- **BLOCKED** — the task cannot run because a prerequisite, environment, device, authority, or required model is unavailable. BLOCKED is never PASS.

Every waiver must be durable and contain:

```text
WAIVER ID:
CHECK / CLAIM AFFECTED:
FAILURE SIGNATURE OR MISSING EVIDENCE:
BASELINE / SOURCE SHA:
RATIONALE:
COMPENSATING EVIDENCE:
RESIDUAL RISK:
EXPIRY OR RECHECK TRIGGER:
BLOCKS SEMANTIC RECOVERY: YES | NO
BLOCKS ANDROID PERFORMANCE QUALIFICATION: YES | NO
BLOCKS MERGE / RELEASE: YES | NO
CONTROLLER APPROVAL + DATE:
```

Waivers cannot authorize semantic divergence, weaken INV-01 through INV-10, silently change goldens, or convert an unmeasured performance claim into PASS. Known baseline failures, unavailable type checks, device gaps, native process termination, and flaky tests require explicit waiver or exception-manifest entries keyed by stable signatures.

## 7.4 Approved semantic oracle and golden custody

Historical acceptance cites Trace V1 in `recovery/trace_schema.md` and the fixture hashes in `app/tests/fixtures/recovery_traces/v1/manifest.json`. The schema document's historical header may still describe its original proposal task; that wording alone is not a current acceptance or lock identity. Trace V1 is immutable historical synchronization-state evidence. It records initial/final RNG state rather than the ordered per-draw contract required for a new exact-equivalence claim, so V1 equality must not be relabeled as full PLAN-V2 equality.

For any PLAN-V2 replay or reopened exact-equivalence claim, the controller must first accept `P-V2-T01` through `P-V2-T03` and one immutable Trace V2 oracle lock, normally `recovery/oracle_lock_v2.json`, that records:

- schema path, schema version, accepted commit, and SHA-256;
- recorder, runner, canonicalizer, comparator, and normalizer paths plus source revisions/SHA-256 hashes;
- pristine `9314f54b` tree identity, isolated derived capture tree identity, observer-patch SHA-256, closed path/symbol allowlist, and proof that every non-allowlisted path is byte-identical;
- locked pristine-versus-derived-Trace-OFF and derived-Trace-OFF-versus-ON observer-effect evidence identities;
- fixture-manifest path and SHA-256;
- every scenario ID, fixture path/hash, deterministic input identity, reference revision, and supported/unsupported disposition;
- project fixture hashes and required runtime/dependency fingerprint;
- controller acceptance decision and timestamp.

The existing V1 fixture manifest is not a PLAN-V2 exact-equivalence oracle lock. `P-V2-B00` may hash it into the V1 custody inventory but must not upgrade its coverage classification. Until the independently reviewed Trace V2 lock is accepted, historical results retain their recorded status while every reopened task that depends on exact ordered-stream equality is BLOCKED.

An approved semantic oracle may be composed from:

- **PC reference trace** — reference semantics observed through the controller-accepted derived capture tree whose pristine base, observer-only patch, non-allowlisted equality, and Trace OFF/ON behavior are all locked under `P-V2-T01` through `P-V2-T03`; it is never an untracked modification of the initial PC reference SHA;
- **superseding correctness oracle** — a later independent fix backed by a minimal reproducer, invariant/property test, decision-ledger entry, and controller approval;
- **property oracle** — a platform-independent invariant where no single historical output is sufficient; or
- **composite oracle** — an explicit per-field/per-event composition of the above, never an undocumented blend.

Each scenario must name its oracle class and source identity. A later candidate output is never evidence for choosing its own expected result. The phrase `PC-reference golden` is insufficient when an accepted later correctness fix supersedes any observed field or ordered event.

Before a golden or oracle can be locked, the reference must pass a self-repeatability gate: at least three fresh-process runs per required environment with pinned inputs, dependencies, fixture hashes, locale/time settings, and RNG state must produce identical canonical traces. Any nondeterministic field must be removed only by a separately reviewed normalizer rule proving it is presentation-only; otherwise the scenario is BLOCKED.

Every trace-bearing task packet and report must identify:

- reference and candidate commit SHAs;
- Trace schema version, V1 custody identity when relevant, accepted V2 oracle-lock identity, runner revision, canonicalizer/comparator identity, and source hash;
- scenario ID, deterministic input fixture, seed/RNG setup, project fixture hash, and environment fingerprint;
- golden fixture path and SHA-256 from the manifest;
- exact comparator command, exit code, and first logical divergence when failing.

Canonical equality must cover both synchronization-point state and the ordered gameplay stream needed to detect equal-final-state/reordered-semantics defects: action application/reversal, hooks, RNG consumption, event dispatch, combat playback, state-stack operations, and cache publication where observable. Presentation-only objects remain excluded.

RNG consumption is mandatory for any scenario claiming exact semantic equality. The trace must observe each correctness-relevant draw without consuming an additional draw and record at minimum `stream_id`, monotonic `draw_index`, operation/domain or bounds, result, and pre/post state digest. Initial/final RNG state alone is insufficient to prove draw ordering. If a required RNG stream cannot be observed safely, the task must report the gap and cannot claim exact equality for that scenario.

Golden custody rules:

1. Production fixes and golden/schema/comparator/normalizer changes must never share a task or commit.
2. Any golden or trace-contract mutation requires a separately authorized controller task, explicit semantic rationale, reference recapture evidence, manifest/hash update, and independent review.
3. A candidate failure never authorizes rewriting expected output.
4. Comparator, schema, manifest, fixture, or normalizer drift blocks comparison until reconciled by the controller.
5. Historical host Trace V1 equality, host Trace V2 equality, and device runtime observation are distinct evidence. Android may claim exact PC Trace V2 equality only when the same accepted V2 contract/comparator is executed or an approved observer-safe transport reproduces every required record. Otherwise the report must say `HOST ORACLE + DEVICE SYNCHRONIZATION EVIDENCE`, not `EXACT DEVICE TRACE EQUALITY`.
6. An oracle-lock change is an evidence-contract change: it requires a separately authorized task and independent review even when it only updates identities.

## 7.5 Transaction failure and worker-safety contract

GameState restore, load, restart, tilemap/board replacement, combat publication, and Android background preparation must define explicit `PREPARE -> VALIDATE -> COMMIT` ownership. Until COMMIT succeeds, the old live world remains authoritative and usable.

Every affected task packet must name a controller-approved contract at `recovery/transactions/<transaction-id>.json`. `COMMIT` is not an acceptable black box: the contract must identify the exact linearization point and enumerate every state change before and after it.

Required transaction fields:

```text
TRANSACTION ID / OWNER / GENERATION TOKEN:
INPUT SNAPSHOT + HASH:
PREPARE READS / THREAD-AFFINITY RULES:
VALIDATION CHECKS:
LINEARIZATION POINT:
ORDERED AUTHORITATIVE MUTATIONS:
RNG / EVENT / ACTION-QUEUE EFFECTS:
UID / CACHE / REGISTRY EFFECTS:
SAVE-I/O / AUDIO / RESOURCE / FILESYSTEM EFFECTS:
REVERSIBLE EFFECTS + COMPENSATION:
IRREVERSIBLE EFFECTS + IDEMPOTENCE KEY:
CANCELLATION CUTOFF / TIMEOUT DISPOSITION:
REENTRANT / OVERLAPPING REQUEST POLICY:
STALE / LATE RESULT POLICY:
SHUTDOWN / EXCEPTION CLEANUP:
FAULT-INJECTION POINTS + EXPECTED OLD/NEW WORLD:
TRACE / PROPERTY / PRESENTATION ORACLE ROWS:
```

An effect that occurs before the linearization point must be private, reversible, or explicitly compensated. An irreversible external effect may occur only after the new world is authoritative or behind an idempotent outbox/commit protocol approved by the controller. Nested or overlapping transactions must name one owner and deterministic loser/cancellation behavior; "last writer wins" is not an implicit default.

Required failure semantics:

- deserialization, version, missing/corrupt resource, validation, allocation, worker, cancellation, timeout, and commit exceptions publish no partial world;
- rollback restores the exact prior coherent world or terminates the transaction before any live mutation;
- pending jobs use immutable input snapshots, generation/ownership tokens, stale-result rejection, deterministic cancellation, and exception propagation;
- workers do not read mutable `game`, `DB`, `RESOURCES`, owner-local caches, pygame objects, or other thread-affine state unless the approved packet proves that read immutable and thread-safe;
- simultaneous load/restart/tilemap requests, shutdown during work, and late worker completion have explicit disposition;
- barriers, temporary resources, threads, and pending results are released on success, cancellation, and exception.

Acceptance requires deterministic tests injecting failure before, at, and after every listed mutation/side-effect boundary and proving: no partial publication, no stale late commit, no leaked RNG/event/UID/cache/save/resource effect, no duplicate irreversible effect, and continued usability of the declared old or new coherent world.

## 7.6 Reproducible evidence manifest

Every task report must include or link an immutable evidence manifest with:

- authorization identity/hash/expiry, accepted plan/controller-state/dependency-graph hashes, repository root, branch, base/final SHA, and allowed-path diff;
- dirty-custody manifest identity, pre/post result, protected paths, and pre-existing tracked/untracked/relevant-ignored identities;
- OS, architecture, Python/runtime/dependency/tool versions and hashes where available;
- project/fixture identity and SHA-256;
- exact commands, environment variables, start/end timestamps, exit codes, and raw log paths/hashes;
- test selection rationale, pass/fail/error/skip counts, expected baseline exception signatures, and waiver IDs;
- historical Trace V1 custody identity plus accepted Trace V2 schema/comparator/manifest/oracle-lock identities where applicable;
- transaction-contract and presentation-contract identities plus their coverage-row IDs;
- build ID, ABI/API/build mode/signing class, artifact size and SHA-256 for packaged output;
- device/emulator model, OS/API, ABI, GPU where available, thermal/power mode, run count, warm-up, workload, raw measurements, and profiler configuration;
- controller disposition and rollback anchor.

Reference and candidate runs must use isolated worktrees/processes with pinned dependencies and hashed fixtures. A controller may waive process isolation only for a read-only evidence task whose packet proves no mutable overlap; production, Trace/golden, migration, merge-rehearsal, and performance-comparison tasks require isolation. If required isolation is impossible, the task is BLOCKED rather than silently downgraded.

## 7.7 Rollback and dirty-worktree discipline

Before editing, create `recovery/evidence/<task-id>/dirty_custody.json` from a NUL-safe porcelain/index inventory. Record every tracked modification, staged entry, untracked path, protected path, symlink/reparse identity, and controller-declared relevant ignored path with normalized absolute path, repository-relative path, file type, size, index/worktree status, and SHA-256 where content-addressable. Existing unrelated changes belong to the user and must remain byte-for-byte untouched.

Dirty-custody rules:

1. The validator rejects any intersection between the task allowlist and a pre-existing dirty/protected path unless the packet names that exact path, input hash, ownership, and intended mutation.
2. Production, Trace/golden, migration, merge-rehearsal, and performance tasks use an isolated worktree rooted at pinned commits. Documentation-only exceptions require an exact one-file allowlist and still require pre/post custody.
3. Relevant ignored paths are controller-declared before editing; discovery after editing cannot be used to exclude a changed path.
4. Pre/post verification compares file type, size, and SHA-256 for every non-allowed custody entry. Missing, renamed, normalized, replaced, or metadata-significant protected paths fail the task.
5. Zero-byte and unusual paths are hashed and protected exactly like ordinary files; cleanup/normalization is forbidden unless separately authorized.
6. The evidence manifest retains both custody snapshots and the deterministic comparison result.

Each conceptual implementation task requires:

- a bounded commit range or an explicitly authorized uncommitted disposition;
- a dependency-aware, controller-approved rollback procedure;
- preservation of raw evidence outside the rollback target;
- post-rollback focused tests proving restoration of the pre-task contract;
- explicit handling of save/schema compatibility when rollback crosses serialized behavior;
- controller disposition for partial uncommitted work after STOP, FAIL, or escalation.
- a successful dirty-custody comparison before PASS or PASS WITH APPROVED EXCEPTIONS.

Do not execute revert, reset, checkout, rebase, clean, history rewrite, or other Git mutation merely because a rollback procedure is documented. Each operation still requires its normal authorization.

## 7.8 Feature/fix preservation and supersession ledger

P0-T02 establishes a controller-approved ledger for every post-reference behavior that can affect runtime semantics or a required later feature, including changes in engine code, serialization, codegen inputs/outputs, data loading, build/runtime integration, mixed commits, and editor-to-runtime pathways.

Each ledger entry records:

```text
ENTRY ID:
COMMIT / RANGE:
FILES / SYMBOLS:
PATHWAY CLASS: ENGINE | SERIALIZATION | CODEGEN | LOADER | BUILD | EDITOR-RUNTIME | PROJECT-INTEGRITY
BEHAVIORAL INTENT:
CLASSIFICATION FROM SECTION 4:
PC REFERENCE OR SUPERSEDING CORRECTNESS SOURCE:
OWNING SUBSYSTEM:
PRESERVATION TEST / TRACE SCENARIO:
EVIDENCE STATUS: VERIFIED | HISTORICAL-ACCEPTED | UNKNOWN | MISSING | CONFLICTING | BLOCKED
FINAL DISPOSITION + SHA:
SUPERSESSION RATIONALE:
CONTROLLER DECISION:
```

Every phase updates affected entries. `UNKNOWN`, `MISSING`, `CONFLICTING`, or `BLOCKED` immediately blocks each dependent task; it must not wait for Phase 9. P9-T03/P9-T04/P9-T04-R3/P9-T05 require 100% reconciliation: no entry may remain unclassified, untested, or without a final disposition. An open-ended phrase such as "later correctness fixes" is not evidence unless backed by ledger entries and preservation tests. Protected project content remains outside rollback scope but its integrity hash/check must still be reported where relevant.

## 7.9 Invariant-to-evidence coverage matrix

`recovery/semantic_coverage_matrix.json` is the mandatory join between architecture intent and executable proof. Each row records:

```text
ROW ID:
INVARIANT ID:
SUBSYSTEM / SYMBOL BOUNDARY:
SCENARIO ID:
PLATFORM / DEVICE CLASS:
SYNCHRONIZATION POINTS:
ORACLE CLASS + SOURCE IDENTITY:
ORDERED TRACE FIELDS / PROPERTY ASSERTIONS:
FAULT / CANCELLATION VARIANT:
OWNING TASK PACKET:
EVIDENCE MANIFEST + RAW ARTIFACT HASHES:
STATUS: VERIFIED | HISTORICAL-ACCEPTED | UNKNOWN | MISSING | CONFLICTING | BLOCKED
WAIVER ID:
CONTROLLER DISPOSITION:
```

Rules:

- every INV-01 through INV-10 claim requires at least one positive row and every applicable transactional invariant requires a negative/fault row;
- a historical accepted row may use `HISTORICAL-NONE` for `OWNING TASK PACKET` only when it names the accepted report/SHA; any reopened work must replace that value with an indexed packet before implementation;
- every task packet names affected existing rows and any new rows it must add;
- every phase-exit manifest reports uncovered, stale, conflicting, or waived rows;
- a code path, platform, feature, or later correctness fix cannot be called preserved solely because its owning test suite passes; it must map to a row and evidence identity;
- P9-T03/P9-T04/P9-T04-R3/P9-T05 require 100% disposition of required rows, while Android physical performance rows may remain explicitly BLOCKED without invalidating a separate semantic PASS.

## 7.10 Presentation-correctness child-plan gate

Logical Trace equality intentionally excludes surfaces, transient frames, and other presentation-only objects. Therefore it cannot prove that a normal `update -> draw -> present` pipeline never exposes a blank participant, stale sprite, flicker, resurrection pixel, missing UI layer, or broken audio/resource handoff. A visible-output defect requires a separate hash-registered presentation contract; it must not weaken or replace the semantic oracle.

**Task ID:** `P-V2-P00`
**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`, only on ESC-03, ESC-05, or ESC-09
**Prerequisite:** accepted `P-V2-T03` and accepted `P-V2-D00` or an enumerated isolated route
**Risk:** High - visible-output oracle may miss host-frame or lifecycle defects
**Review class:** ARCHITECTURE

`P-V2-P00` registers exactly one child plan at `recovery/presentation/<contract-id>.md` and adds its explicit task edges to the dependency graph. The contract records:

```text
CONTRACT ID / DEFECT SIGNATURE / AFFECTED PATHS:
SOURCE CHILD-PLAN PATH + SHA-256 + BASE SHA:
NORMAL UPDATE / DRAW / PRESENT ORACLE:
VISIBLE-PIXEL / BLIT / CONTINUITY INVARIANTS:
PARTICIPANT / LAYER / AUDIO / RESOURCE LIFECYCLE MATRIX:
DYING / DEAD / HIDDEN / MISSING-RESOURCE OUTCOMES:
PLATFORM / RESOLUTION / TOLERANCE RULES:
FROZEN RED-TEST / SOURCE / MANIFEST / RAW-LOG HASHES:
SEMANTIC COVERAGE ROWS + TRACE V2 NON-REGRESSION:
SECTION 20 PERFORMANCE WORKLOAD IDS:
INDEPENDENT REVIEWER / HASH-PINNED INPUTS / VERDICT:
```

Rules:

- the behavior oracle is the production-order host/device pipeline and observable output, not private frame fields alone;
- deterministic off-screen pixel/blit invariants are preferred; perceptual tolerances require pre-approval and may not hide a fully blank or resurrected participant;
- red tests, test source, fixture/resource manifest, and red logs are frozen before production work; later tasks recompute hashes and stop on drift;
- the child plan references Section 20 rather than copying Android performance thresholds;
- the independent reviewer is not the production-fix author, is read-only, receives hash-pinned inputs only, and returns exactly `APPROVE` or `REQUEST CHANGES`;
- a child plan outside `recovery/presentation/`, including an untracked review document, is candidate input only and grants no execution authority until `P-V2-P00` registers its accepted hash and graph edges.

Every presentation production task depends on accepted `P-V2-P00`, its frozen red evidence, Trace V2 semantic non-regression, dirty custody, and its indexed packet. A semantic mismatch or second unrelated renderer defect stops the child task and returns to controller classification instead of widening the fix.

**STOP FOR CONTROLLER REVIEW.**

---

# 8. PHASE 0 — BASELINE, INVENTORY, SAFETY RAILS

## P0-T01 — Capture recovery baseline

**Primary:** `GPT-5.6 Luna / low`
**Escalation:** `GPT-5.6 Terra / medium`
**Risk:** Low
**Review class:** ROUTINE

Tasks:

- verify recovery branch ancestry and starting reference;
- record Python/runtime/dependency versions;
- record current full test-suite result;
- inventory Android/runtime flags;
- inventory profiling controls;
- list engine files changed between `9314f54b` and recovery starting HEAD;
- create `recovery/baseline.md`;
- do not modify engine behavior.

Escalate only if repository state/history is inconsistent with the plan or baseline collection exposes unexplained structural divergence.

Acceptance:

- baseline report committed;
- no engine behavior changes;
- existing test failures recorded and categorized, not fixed.

## P0-T02 — Build post-reference semantic change inventory

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P0-T01
**Review class:** ARCHITECTURE

Tasks:

- inspect the complete post-reference commit/symbol/path delta after `9314f54b` across engine/runtime, serialization and migrators, codegen inputs/generated outputs, loaders, build/runtime integration, project validation, and editor-to-runtime pathways;
- classify every behavior-affecting entry using Section 4 and the Section 7.8 pathway/status schema;
- identify mixed changes within commits and split their behavioral dispositions without reverting a mixed commit wholesale;
- inventory `is_android_runtime`, render optimization gates, staged jobs, generators/yields, worker threads, and deferred commits;
- create/update `recovery/change_inventory.md` and the controller-approved preservation/supersession ledger.

Escalate on ESC-01, ESC-02, ESC-04, or ESC-09.

Acceptance:

- every post-reference behavior-affecting commit/file/symbol/pathway has one ledger entry or a hash-identified non-behavioral exclusion rationale;
- uncertain cases use `UNKNOWN`, `MISSING`, `CONFLICTING`, or `BLOCKED`, name affected successor tasks, and remain fail-closed;
- mixed commits have per-behavior dispositions and preservation evidence;
- no production behavior changes.

**STOP FOR CONTROLLER REVIEW.**

---

# 9. PHASE 1 — BEHAVIORAL REGRESSION HARNESS

P1-T01 through P1-T03 below describe the historically executed Trace V1 phase. They are not a substitute for the PLAN-V2 ordered-stream migration in Section 7.1.4. Any replay or new exact-equivalence claim uses `P-V2-T01` through `P-V2-T03` and preserves V1 custody.

## P1-T01 — Design deterministic trace schema

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Approved P0-T02
**Review class:** ARCHITECTURE

Design synchronization-point tracing for:

- state stack nids;
- active level/overworld;
- unit logical state;
- positions, HP, mana, statuses, skills, inventory/durability;
- relevant game/level vars;
- historical Trace V1 RNG seed and combat/growth/other state snapshots, explicitly insufficient for ordered per-draw equality; PLAN-V2 ordered consumption belongs to `P-V2-T01` through `P-V2-T03`;
- combat playback/action sequence;
- triggered event IDs/order;
- turn/phase;
- tilemap/board identity and invariants;
- save/load/restart completion state.

Do not use frame count, audio objects, surfaces, or volatile presentation state as equality criteria.

Escalate if trace design itself requires new core lifecycle semantics or reference behavior is ambiguous.

**STOP FOR CONTROLLER REVIEW.**

## P1-T02 — Implement trace/test harness

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** Approved P1-T01
**Review class:** ROUTINE

Implement approved design with minimal production intrusion.

Escalate if instrumentation changes lifecycle ordering or requires invasive cross-system hooks.

## P1-T03 — Establish approved semantic oracle scenarios

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P1-T02
**Review class:** ARCHITECTURE

Minimum scenarios:

1. New game to first playable map.
2. Existing save load.
3. Save/load during event where supported.
4. Restart current chapter.
5. Standard map combat.
6. Simple combat.
7. Animation combat.
8. Arena/base combat where applicable.
9. Skill proc and pre/post-combat hooks.
10. Item durability/uses and broken/unusable handling.
11. Promotion/class-change edge cases.
12. Aura propagation/teardown/load.
13. Fog-of-war move preview/cancel/wait.
14. Tilemap change.
15. Phase transition.
16. Fast-forward ON vs OFF.
17. Debugger disabled/enabled observer equivalence.
18. Game-over/restart.
19. Editor `Test Chapter` to first playable control, first in-session save, and restart-slot behavior when `current_save_slot` begins unset.
20. Overworld load, node/route transition, cinematic completion, and return to a playable synchronization point.
21. Roam enter/leave, interaction, save/load, and return to tactical or overworld state where supported.
22. Turnwheel/action reversal across movement, combat, event, RNG, inventory/durability, aura, and fog-of-war state where supported.
23. Event skip/interruption/resume and save/load around an event transaction where supported.
24. Load/restart/tilemap cancellation, timeout, worker exception, stale late completion, and continued usability of the prior live world.
25. Overlapping load, restart, tilemap, and shutdown requests with explicit ownership/generation-token disposition.
26. Representative versioned-save migrations from the oldest supported boundary, intermediate retained versions, and current format.
27. Fresh-process oracle self-repeatability under pinned inputs before candidate comparison.
28. Android background/foreground and screen-off/resume during idle, Event, combat, load/restart, and tilemap preparation.
29. Android low-memory notification/reclaim followed by cache/resource reconstruction without authoritative-state loss.
30. Audio-focus loss/gain and OS interruption without gameplay-order or ownership divergence.
31. Supported Activity/configuration recreation with explicit state/resource ownership and no duplicate event/action publication.
32. Shutdown/cancel during pending work plus stale late-worker completion after resume or teardown.

Before capture, create coverage-matrix rows for every scenario and name its PC reference, superseding correctness, property, or composite oracle. Scenario 27 must pass before any golden is locked. Scenarios 24–25 and 28–32 are fault/property or lifecycle oracles and must not be reduced to `does not crash` checks.

Escalate on reference ambiguity, conflicting traces, or cross-subsystem invariant failure.

Do not modify an approved oracle to make current code pass. A later correctness fix may supersede PC-reference behavior only through the preservation/supersession ledger, minimal reproducer/property test, affected coverage rows, and explicit controller approval.

**STOP FOR CONTROLLER REVIEW.**

---

# 10. PHASE 2 — GAMESTATE AND STATE-MACHINE ATOMICITY

## P2-T01 — Audit GameState/load/state-restore delta

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Approved Phase 1 harness
**Review class:** ARCHITECTURE

Focus:

- `app/engine/game_state.py`;
- state machine files;
- title/load jobs;
- chapter/overworld restore entry points;
- staged-state fields/commit paths;
- restart/save dependencies.

Deliver a function-level restore/re-port map before implementation.

Escalate on ESC-01, ESC-02, ESC-04, or ESC-09.

**STOP FOR CONTROLLER REVIEW.**

## P2-T02 — Restore authoritative PC state semantics

**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`
**Prerequisite:** Approved P2-T01
**Review class:** ARCHITECTURE

Requirements:

- no saved state stack becomes authoritative before required level/overworld structures exist;
- do not normalize invalid partial states with widespread null guards;
- restore one atomic logical transaction boundary;
- retain later save format/features independent of Android staging;
- retain restart intent;
- isolate Android progressive preparation outside live authoritative state.

Escalate to `ultra` only on ESC-02, ESC-03, ESC-04, ESC-05, ESC-06, ESC-08, or ESC-09.

Run targeted harness and full unit suite.

**STOP FOR CONTROLLER REVIEW.**

## P2-T03 — Remove obsolete staged-restore workarounds

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P2-T02 accepted
**Review class:** ARCHITECTURE

Remove a guard only when tests prove the invalid staged condition is impossible. Keep independently useful defensive guards.

Escalate if removing a workaround reveals a nonlocal state invariant failure.

**STOP FOR CONTROLLER REVIEW.**

---

# 11. PHASE 3 — COMBAT LIFECYCLE SEMANTICS

## P3-T01 — Build combat lifecycle reference map

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Phase 2 accepted
**Review class:** ARCHITECTURE

Compare reference/current behavior for:

- `SimpleCombat`;
- `MapCombat`;
- `BaseCombat`;
- `AnimationCombat`;
- arena paths;
- solver initialization/advancement;
- pre-combat hooks;
- action generation/application;
- playback;
- cleanup hooks;
- broken/unusable checks;
- EXP/promotion transitions;
- state-stack handling;
- `end_combat` ordering;
- transform animation preparation;
- battle music preparation.

Separate gameplay work from presentation/resource work.

Escalate if class interactions make ordering ambiguous or the reference itself conflicts with later correctness fixes.

**STOP FOR CONTROLLER REVIEW.**

## P3-T02 — Restore Simple/Map combat transaction ordering

**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`
**Prerequisite:** Approved P3-T01
**Review class:** ARCHITECTURE

No yield/staging may expose an intermediate gameplay transaction to unrelated states. Preserve computational optimizations only when trace-equivalent.

Escalate to `ultra` only for unresolved cross-class/nonlocal trace divergence after one bounded correction.

**STOP FOR CONTROLLER REVIEW.**

## P3-T03 — Restore Base/Animation/Arena combat ordering

**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`
**Prerequisite:** P3-T02 accepted
**Review class:** ARCHITECTURE

Retain Android battle-music streaming as a platform implementation detail. Progressive animation/resource preparation is allowed only outside authoritative gameplay advancement.

Escalate to `ultra` only when shared class inheritance/order creates unresolved semantic conflict.

**STOP FOR CONTROLLER REVIEW.**

## P3-T04 — Combat feature/fix preservation sweep

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P3-T03 accepted
**Review class:** ARCHITECTURE

Verify:

- cleanup ordering;
- durability/use costs;
- promotion cancel/finalization;
- skill cache invalidation;
- aura interactions;
- fast-forward behavior;
- combat-related debugger behavior.

Escalate if a failure requires changing combat lifecycle architecture rather than re-porting a bounded feature/fix.

**STOP FOR CONTROLLER REVIEW.**

---

# 12. PHASE 4 — TILEMAP / BOARD / EVENT ATOMICITY

## P4-T01 — Decompose staged tilemap optimization

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Phase 3 accepted
**Review class:** ARCHITECTURE

Audit:

- `GameBoard.build_iter` and incremental helpers;
- `TilemapChangeJob`;
- batched tilemap transition;
- aura/terrain/fog/region rebuilding;
- event render deferral;
- commit ordering.

Classify computational optimization versus scheduling semantic change.

Escalate if the existing staged architecture prevents a clean classification.

**STOP FOR CONTROLLER REVIEW.**

## P4-T02 — Restore desktop atomic tilemap semantics

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Approved P4-T01
**Review class:** ARCHITECTURE

Desktop preserves original synchronous logical behavior. Safe build/lookup optimizations remain shared only when trace-equivalent.

Escalate if board/tilemap/aura/fog ordering has ambiguous transactional boundaries.

**STOP FOR CONTROLLER REVIEW.**

## P4-T03 — Android-only progressive board preparation

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P4-T02 accepted
**Review class:** ARCHITECTURE

Retain/implement only if profiling justifies it.

Required contract:

```text
LIVE OLD STATE
    -> build pending structures outside live world
    -> validate complete pending world
    -> one atomic logical commit
LIVE NEW STATE
```

Never point live `game` piecemeal at pending structures.

Escalate immediately on ESC-07 or if atomic commit requires new cross-cutting lifecycle architecture.

**STOP FOR CONTROLLER REVIEW.**

---

# 13. PHASE 5 — SAVE / LOAD / RESTART CONSOLIDATION

## P5-T01 — Save format and compatibility audit

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** Phase 4 accepted
**Review class:** ARCHITECTURE

Inventory/test:

- fields added since reference;
- event-state serialization;
- restart slots;
- chapter-start snapshot behavior;
- aura reconstruction;
- old/current save compatibility;
- representative oldest/intermediate/current serialization migrations;
- editor `Test Chapter` first-save/restart behavior with no pre-existing slot;
- overworld, roam, turnwheel/action-reversal, and event-resume persistence where supported;
- Android load orchestration dependencies.

Escalate on ESC-06 or ambiguous legacy behavior.

**STOP FOR CONTROLLER REVIEW.**

## P5-T02 — Canonical transactional load API

**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`
**Prerequisite:** Approved P5-T01
**Review class:** ARCHITECTURE

Implement one authoritative core load transaction. Android may prepare expensive resources around it but may not redefine when logical restore becomes visible.

Escalate to `ultra` only on unresolved save-format/lifecycle conflict, nonlocal invariant failure, or competing semantic designs.

**STOP FOR CONTROLLER REVIEW.**

## P5-T03 — Canonical restart contract

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P5-T02 accepted
**Review class:** ARCHITECTURE

Preserve:

- restart current chapter;
- intended difficulty selection;
- Test Chapter edge cases;
- game-over restart;
- debug-triggered restart.

Define pristine chapter-start state explicitly and prevent accidental mid-chapter inheritance.

Escalate if restart semantics require changes to the canonical load transaction.

**STOP FOR CONTROLLER REVIEW.**

---

# 14. PHASE 6 — PLATFORM POLICY BOUNDARY

## P6-T01 — Define runtime capability interfaces

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** Phase 5 accepted
**Review class:** ARCHITECTURE

Prefer narrow capabilities over a giant platform abstraction.

Candidate boundaries:

- audio/music backend;
- resource load/preload policy;
- render/cache policy;
- frame-work budget policy;
- filesystem/build handling.

Do not spread new `if is_android_runtime()` branches through gameplay-critical modules.

Escalate if the boundary affects authoritative gameplay lifecycle or requires a new cross-cutting architecture.

**STOP FOR CONTROLLER REVIEW.**

## P6-T02 — Migrate Android audio/resource policy

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** Approved P6-T01
**Review class:** ROUTINE

Keep Android streamed battle music where correct; implement approved interfaces without changing gameplay ordering.

Escalate if resource policy unexpectedly mutates/advances live gameplay state.

## P6-T03 — Migrate accepted Android scheduling policy

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P6-T02
**Review class:** ARCHITECTURE

Only migrate scheduling behavior already approved as safe. Any scheduling requiring gameplay core to tolerate partial state is rejected/redesigned.

Escalate immediately on ESC-07.

**STOP FOR CONTROLLER REVIEW.**

---

# 15. PHASE 7 — USER-FACING FEATURE PRESERVATION

## P7-T01 — Fast-forward equivalence suite

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** Phase 6 accepted
**Review class:** ARCHITECTURE

Compare identical seed/input with fast-forward ON/OFF. Actions, RNG outcomes, combat, XP, durability/costs, skills/statuses, events, and final state must match. Only presentation timing may differ.

Escalate if divergence is nonlocal or appears inside restored combat/state-machine semantics.

**STOP FOR CONTROLLER REVIEW.**

## P7-T02 — Debugger parity PC/Android

**Primary:** `GPT-5.6 Luna / medium`
**Escalation:** `GPT-5.6 Terra / high`
**Prerequisite:** P7-T01 accepted
**Review class:** ARCHITECTURE

Verify intended debug operations including restart, chapter navigation, unit editing, auto-level, teleport, items, world values, and platform UI integration. Debugger enabled but idle must be observer-equivalent.

Escalate if fixing a debugger defect requires gameplay-core semantic changes.

**STOP FOR CONTROLLER REVIEW.**

## P7-T03 — Profiler observer-equivalence

**Primary:** `GPT-5.6 Luna / low`
**Escalation:** `GPT-5.6 Terra / medium`
**Prerequisite:** P7-T02 accepted
**Review class:** ROUTINE

Verify profiler ON/OFF state equivalence and worker-thread scope isolation.

Escalate if instrumentation changes shared state or thread/lifecycle ordering.

## P7-T04 — Save/load/restart UX regression sweep

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P7-T03
**Review class:** ARCHITECTURE

Run feature-level scenarios on PC and Android pathways.

Escalate if failure traces point back to canonical load/restart architecture rather than UX integration.

**STOP FOR CONTROLLER REVIEW.**

---

# 16. PHASE 8 — SAFE SHARED OPTIMIZATION REINTRODUCTION

Correctness must already be stable before optimizing.

## P8-T01 — Cache/memoization audit

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** Phase 7 exit manifest accepted
**Review class:** ARCHITECTURE

Criteria:

- correct invalidation;
- no hidden mutable-state dependence absent from cache keys;
- identical logical traces.

Preserve the LTCache invariant: invalidate after publishing mutable component state.

Escalate if cache correctness depends on nonlocal lifecycle semantics.

**STOP FOR CONTROLLER REVIEW.**

## P8-T02 — Render/cache/batching optimization audit

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P8-T01 accepted
**Review class:** ARCHITECTURE

Keep output-equivalent optimizations shared. Any optimization that can alter visible frame continuity, participant/layer visibility, blit ordering, opacity, clipping, resource handoff, or audio presentation requires an accepted Section 7.10 presentation contract in addition to Trace V2 semantic equality.

Escalate if render optimization changes logical update scheduling or state visibility.

**STOP FOR CONTROLLER REVIEW.**

## P8-T03 — Allocation/redundant-work audit

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P8-T02 accepted
**Review class:** ARCHITECTURE

Measure before/after where practical and require trace equality.

Escalate only if optimization requires changing shared lifecycle boundaries.

**STOP FOR CONTROLLER REVIEW.**

## P8-T04 — Android-only performance retuning

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P8-T01 through P8-T03 accepted
**Review class:** ARCHITECTURE

Use profiler evidence. Optimize only behind accepted platform boundaries. No optimization is accepted solely on FPS improvement if behavioral traces differ.

Escalate on ESC-07, nonlocal regressions, or conflict between performance target and semantic invariants.

**STOP FOR CONTROLLER REVIEW.**

---

# 17. PHASE 9 — FULL VALIDATION AND RELEASE CANDIDATE

Phase 9 produces separate decisions. They must never be collapsed into one ambiguous PASS:

1. **SEMANTIC RECOVERY GATE** — PC reference equivalence, shared-core invariants, feature preservation, transaction atomicity, and architecture contamination.
2. **ANDROID RUNTIME EQUIVALENCE GATE** — current-provenance Android artifact reaches required synchronization points without Android-only gameplay divergence.
3. **ANDROID PERFORMANCE QUALIFICATION GATE** — release-equivalent arm64-v8a artifact passes the physical-device matrix and locked Section 20 thresholds.
4. **MERGE / RELEASE GATE** — controller disposition only after the three results above, waivers, known limitations, rollback evidence, and accepted isolated merge rehearsal are explicit.

Semantic recovery may be COMPLETE while Android performance qualification is BLOCKED or PASS WITH APPROVED EXCEPTIONS. In that case the final report must not say Android performance is qualified or that the artifact is fully release-ready.

## P9-T01 — Full PC regression matrix

**Primary:** `GPT-5.6 Luna / medium`
**Escalation:** `GPT-5.6 Terra / high`
**Prerequisite:** Phase 8 exit manifest accepted
**Review class:** ARCHITECTURE

Run:

- full unit tests;
- required type checks, or an explicit active waiver naming the unavailable tool/check;
- deterministic behavioral scenarios;
- task-packet-enumerated project launches through defined playable checkpoints;
- save/load/restart flows;
- fast-forward/debugger checks.

The task packet must pin the Windows/runtime environment, interpreter/dependencies, project fixture hashes, fresh-process isolation, scenario/input scripts, expected exit/crash policy, baseline-exception manifest, and exact required commands. No unexplained reference divergence or unwaived native termination is allowed.

Escalate only to diagnose failures; do not use Terra merely to run known tests.

**STOP FOR CONTROLLER REVIEW.**

## P9-T02 — Full Android regression/performance matrix

**Primary:** `GPT-5.6 Terra / medium`
**Escalation:** `GPT-5.6 Sol / high`
**Prerequisite:** P9-T01 accepted
**Review class:** ARCHITECTURE

P9-T02 has four independently reported sub-gates:

- **P9-T02A BUILD / PROVENANCE:** verify current source SHA, source digest, build ID, signing class, package/version, min/target API, selected ABI, exact native-library directories/ELF machines, artifact size/SHA-256, and reproducible build inputs. `arm64-v8a` remains the required default physical-device target; emulator/WSA ABIs are additional targets, not substitutes.
- **P9-T02B SEMANTIC ORACLE:** run the locked Trace V2 approved-semantic-oracle matrix under the host Android policy path and compare exact ordered-stream scenarios against their declared PC-reference, superseding-correctness, property, or composite oracle. Historical V1 results are reported separately as custody evidence. No schema, comparator, normalizer, manifest, fixture, budget, or production semantic may change inside this validation task.
- **P9-T02C DEVICE RUNTIME EQUIVALENCE:** on a current-provenance artifact, exercise title/startup, Event/combat, tilemap/board barrier, movement/FOW, save/load, pristine restart, `Test Chapter`, overworld/roam, turnwheel/reversal, versioned-save migration, phase, fast-forward, debugger/profiler observer behavior, presentation contracts, Android lifecycle interruptions, worker shutdown, and audio/resource fallback where supported through explicit synchronization assertions. Device logs are not called exact Trace V2 unless Section 7.4's same-contract requirement is met.
- **P9-T02D PHYSICAL PERFORMANCE QUALIFICATION:** run the Section 20 physical arm64-v8a device matrix with a release-equivalent build, raw frame/memory/thermal evidence, locked workload, and pass/fail thresholds.

Each sub-gate gets PASS, PASS WITH APPROVED EXCEPTIONS, PARTIAL, FAIL, or BLOCKED. P9-T02D must be BLOCKED on WSA/emulator-only evidence; neither PASS nor PASS WITH APPROVED EXCEPTIONS may claim physical performance qualification without the required physical matrix.

Escalate on unexplained semantic divergence or platform-boundary conflict.

**STOP FOR CONTROLLER REVIEW.**

## P9-T03 — Architecture contamination audit

**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`
**Prerequisite:** P9-T02A through P9-T02C accepted; P9-T02D disposition recorded separately
**Review class:** ARCHITECTURE

Search final code for:

- Android conditionals in gameplay-critical modules;
- staged/deferred fields in `GameState`;
- partial-state guards;
- worker-thread mutation of gameplay state;
- worker reads of mutable authoritative or thread-affine state;
- missing generation tokens, cancellation, stale-result rejection, or exception cleanup;
- transaction paths whose ordered mutations/side effects do not match their accepted linearization contract;
- presentation-critical paths lacking a registered output contract or frozen visible-output oracle;
- duplicate PC/Android gameplay implementations;
- yield/generator boundaries inside logical transactions;
- recovery TODO/FIXME markers.

Every remaining case requires justification.

Escalate if remaining contamination requires architecture-level reconciliation rather than local cleanup.

**STOP FOR CONTROLLER REVIEW.**

## P9-T04 — Final release candidate review

**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`
**Prerequisite:** P9-T03 accepted and complete recovery phase-exit manifest
**Review class:** FINAL

Codex must not merge to `master` unless the user explicitly instructs it after controller approval.

Deliver:

- final commit range;
- architecture summary;
- preserved feature list;
- removed/replaced staging list;
- known limitations;
- PC behavior-equivalence evidence;
- Android behavior-equivalence evidence;
- Android performance qualification result, physical-device coverage, thresholds, and waivers;
- full test results;
- evidence-manifest hashes and rollback anchors;
- task-index/validator/dependency-graph identities and final coverage-matrix disposition;
- recommended merge-rehearsal strategy and pinned candidate tip; no merge authorization.

The final report must state four independent verdicts: `SEMANTIC RECOVERY`, `ANDROID RUNTIME EQUIVALENCE`, `ANDROID PERFORMANCE QUALIFICATION`, and `MERGE / RELEASE`. A PASS in one does not imply PASS in another. At historical P9-T04, `MERGE / RELEASE` remains `AWAITING R3 VALIDATION`, `AWAITING REHEARSAL`, or `BLOCKED`; it cannot be `AUTHORIZED` before accepted P9-T04-R3 and P9-T05.

Escalate to `ultra` only on ESC-10 or unresolved high-blast-radius conflicts across multiple accepted subsystems.

**STOP FOR CONTROLLER REVIEW; HISTORICAL P9-T04 DOES NOT OPEN P9-T05.**

### P9-T04-R3 — Fresh PLAN-V2 merge-readiness validation

**Task ID:** `P9-T04-R3`
**Primary:** `GPT-5.6 Sol / max`
**Escalation:** `GPT-5.6 Sol / ultra`, only on ESC-10 or unresolved high-blast-radius conflicts across multiple accepted subsystems
**Prerequisite:** accepted `P-V2-T03`; accepted graph-selected audit/fix/semantic/runtime-validation closure; exact recovery tip pinned; explicit revalidation authorization
**Risk:** High - stale historical acceptance could be mistaken for current merge readiness
**Review class:** FINAL

`P9-T04-R3` is the only final-review node that P9-T05 may consume. It is a fresh, hash-bound replay of the P9-T04 review contract against the exact proposed recovery tip after the PLAN-V2-R3 spine has passed. Its packet and phase-exit manifest must identify that tip, accepted T03 oracle lock, dependency-graph closure, coverage/ledger/custody disposition, every reused-versus-rerun evidence item, and the independent final verdict. Historical P9-T04 acceptance remains valid historical evidence but cannot satisfy, alias, or be promoted into `P9-T04-R3`; PLAN-V2 defines no historical-merge route.

Any recovery-tip movement, stale evidence, missing R3 artifact, or mismatch between the P9-T04-R3 manifest and the candidate supplied to P9-T05 invalidates this node and requires a new authorized instance. Acceptance records the exact packet/index/manifest hashes and `R3 VALIDATION PASS`, `PASS WITH APPROVED EXCEPTIONS`, `FAIL`, or `BLOCKED`; only the first two can open P9-T05.

**STOP FOR CONTROLLER REVIEW AND SEPARATE P9-T05 AUTHORIZATION.**

## P9-T05 — Isolated merge integration rehearsal

**Task ID:** `P9-T05`
**Primary:** `GPT-5.6 Terra / high`
**Escalation:** `GPT-5.6 Sol / max`, only on ESC-09 or ESC-10
**Prerequisite:** matching `P9-T04-R3` accepted for the exact pinned recovery tip; exact target-branch tip pinned; explicit rehearsal authorization
**Risk:** High - combined-tree conflict resolution and release integration
**Review class:** FINAL

P9-T05 is a disposable integration experiment, not the real merge. Its packet must authorize only an isolated worktree and exact Git commands; it must not checkout or mutate `master`, update refs, push, tag, or reuse a dirty checkout. The validator rejects a historical P9-T04 manifest, a P9-T04-R3 manifest bound to another recovery tip, or any attempt to infer this prerequisite from the old final verdict.

Required evidence:

- recovery tip, target tip, merge base, remote/ref identities, toolchain, and input tree hashes;
- isolated-worktree path and preflight proof that neither source checkout nor target ref can be mutated;
- exact merge command and strategy, conflict list, and a conflict ledger explaining every chosen resolution against both parents and the preservation ledger;
- combined-tree diff against both parents, generated-file/codegen audit, project-data integrity check, and architecture-contamination audit;
- rerun of the packet-locked semantic, presentation, build, runtime, and applicable release checks on the rehearsed tree;
- resulting tree hash, evidence/log hashes, dirty-custody result, and proof that rehearsal cleanup restores the pre-task repository/ref state; and
- rollback procedure for the eventual real merge, without executing that merge or rollback.

Any target/source tip movement, unexplained conflict, lost later feature, resurrected contamination, failed required check, or mismatch between the rehearsed tree and proposed merge strategy invalidates the rehearsal. P9-T05 must be repeated against newly pinned tips.

Acceptance records `REHEARSAL PASS`, `PASS WITH APPROVED EXCEPTIONS`, `FAIL`, or `BLOCKED`; it never records the real merge as complete. Checkout/mutation of `master`, merge, push, or tag still requires a separate explicit user/controller authorization after P9-T05 acceptance.

**STOP FOR FINAL CONTROLLER MERGE / RELEASE DECISION.**

---

# 18. UNIVERSAL STOP CONDITIONS

Codex must stop and report rather than improvise if:

1. current model/effort does not match the task's primary configuration and no explicit escalation is authorized;
2. required model/effort cannot be detected or is unavailable;
3. a prerequisite/controller gate is not approved;
4. recovery work is requested directly on `master`;
5. a proposed fix intentionally changes PC behavioral semantics without approval;
6. the PC reference contains a later-fixed bug and classification is unclear;
7. an optimization changes RNG/action/event/hook ordering;
8. an Android optimization requires partial live gameplay state;
9. save compatibility requires an unapproved migration/format decision;
10. protected project content would be edited only to make an engine test pass;
11. scope expands into another major subsystem;
12. required tests cannot be run;
13. evidence contradicts an assumption in this plan;
14. a destructive Git operation appears necessary;
15. a Section 1.3 escalation condition is reached.
16. the approved task packet, phase-exit manifest, allowed-path list, rollback anchor, or required waiver is missing;
17. a production fix would require changing any Trace schema/recorder, comparator, normalizer, manifest, oracle lock, fixture, or golden in the same task;
18. Android performance qualification lacks the required physical-device matrix, raw samples, p99-equivalent evidence, or pre-locked thresholds;
19. transaction failure/cancellation behavior cannot prove the prior live world remains coherent and usable.
20. a replay/reopened task depends on historical acceptance that has not been reconciled through accepted `P-V2-B00` artifacts;
21. a reopened implementation lacks accepted `P-V2-O01`, an indexed validator-passing task packet, or complete affected coverage-matrix rows;
22. an exact-equivalence claim lacks an accepted oracle lock, reference self-repeatability, declared oracle class, mandatory ordered RNG evidence, or the locked pristine/derived-reference instrumentation proof;
23. authority, plan, controller-state, externally indexed packet, index, or dependency-graph hashes disagree; a packet embeds its own digest; canonical packet bytes are invalid; authorization is expired; or the validator is its own sole trust evidence;
24. production-behavior replay/correction/reopening, shared optimization, or presentation work lacks accepted `P-V2-T01` through `P-V2-T03` and an independently reviewed Trace V2 oracle lock;
25. a transactional task lacks an accepted linearization/side-effect contract or cannot compensate/private-stage every pre-commit effect;
26. dirty custody is incomplete, an allowlist overlaps an unowned dirty/protected path, required isolation is absent, or any non-allowed pre/post identity changes;
27. a visible-output fix lacks a hash-registered presentation contract, frozen red evidence, normal update/draw/present oracle, or independent verdict;
28. Android qualification weakens the supported device floor, omits required lifecycle cases, or treats autocorrelated frames as independent inferential samples; and
29. merge/release authorization is requested without a matching fresh `P9-T04-R3` and accepted P9-T05 against the exact pinned source/target tips.

---

# 19. CHANGE DISCIPLINE

## Commit discipline

Prefer one conceptual change per commit.

Suggested prefixes:

- `test(recovery): ...`
- `refactor(core): ...`
- `fix(core): ...`
- `perf(shared): ...`
- `perf(android): ...`
- `refactor(android): ...`
- `docs(recovery): ...`

Never combine project content changes with engine recovery commits.

## Diff discipline

Before finishing each task:

- inspect the complete diff;
- ensure generated files were not hand-edited incorrectly;
- remove unrelated formatting churn;
- remove temporary debug output/files;
- verify tests assert invariants, not only implementation details.

## Test discipline

A regression test should fail for the broken semantic condition and pass for the recovered one. Prefer state assertions over "does not crash" tests.

Because tests share the global `game` singleton, every new test touching `game` must initialize/reset each state element it relies on.

---

# 20. PERFORMANCE ACCEPTANCE RULES

Correctness is evaluated before performance.

## 20.1 Evidence classes

- **Characterization evidence** may come from desktop, host Android-policy tests, emulator, or WSA. It helps diagnose and compare but does not by itself qualify physical Android performance.
- **Android performance qualification evidence** requires a current-provenance, release-equivalent `arm64-v8a` artifact on the physical-device matrix below.
- A performance win with semantic divergence is FAIL regardless of frame time.
- A temporary regression may be accepted during semantic recovery only when recorded with a waiver/disposition; it remains blocking for Android performance qualification until remeasured and accepted.

## 20.2 Required physical-device matrix

Qualification requires at minimum:

1. one supported low/mid-tier physical `arm64-v8a` device near the lower supported Android/API range; and
2. one representative current physical `arm64-v8a` device in the current target API range.

For every device record model, SoC/GPU, RAM, Android/API, ABI, display refresh/resolution, thermal state, power mode, background-load policy, and whether the device is charging. Emulator or WSA results are reported separately and never substitute for either physical class.

A product-specific matrix may add devices or choose more representative models, but it may not remove the supported low/mid-tier floor or current-device class merely to obtain a PASS. A weaker matrix is valid only after a separate product-support-policy decision removes that device/API class from support before candidate measurement; the performance task itself cannot redefine the supported population.

The baseline and candidate builds must both be current-provenance and matched in compiler/interpreter optimization, native libraries, resources, signing class, cache capacity/policy, runtime flags, preload/warm-state rules, and toolchain identity except for the authorized candidate delta. Artifact/source/build/config SHA-256 values are locked before measurement. Development signing is acceptable only if signing is the sole material difference and the report proves it. Profiler overhead must be measured or bounded.

## 20.3 Required workloads and sampling

The task packet must provide deterministic input scripts and fixed project/fixture hashes for:

- cold startup to title and warm startup;
- title steady state;
- map idle, movement, Wait, and fog-of-war update;
- standard, simple, and animation combat;
- representative Event execution;
- tilemap/board change including pending preparation and atomic commit;
- current save, canonical load, pristine restart, and phase transition;
- editor `Test Chapter`, overworld, roam, turnwheel/action reversal, and versioned-save migration workloads where supported;
- fast-forward OFF and each supported speed;
- debugger/profiler idle observer modes;
- streamed/cached audio and resource fallback;
- background/foreground and screen-off/resume during idle, Event, combat, load/restart, and tilemap preparation;
- low-memory notification/reclaim and subsequent resource/cache reconstruction;
- audio-focus loss/gain, OS interruption, and supported Activity/configuration recreation; and
- shutdown/cancel during pending work plus stale late-worker completion after resume or teardown.

Characterization requires at least three independent runs. Qualification requires at least five paired baseline/candidate runs per device/build/scenario after a documented warm-up, with equal-duration/equal-frame comparison windows and at least 3,000 consecutive rendered frames for each steady-state window unless the controller locks a statistically justified alternative before measurement.

The task packet must lock before candidate measurement:

- balanced randomized `AB`/`BA` baseline-candidate order and a pairing key for every run;
- warm-up, cooldown, charging, power, background-load, display, and thermal-stability entry/exit criteria;
- minimum/maximum run count, confidence method, practical noise floor, and any sequential stopping rule;
- paired run-level estimand, equal-window rule, cluster/block unit, moving-block or hierarchical bootstrap method, block-length selection, device stratification, and confidence level;
- pre-declared invalid-run signatures such as instrumentation failure or OS interruption; invalidated runs remain in raw evidence with the reason and replacement identity; and
- profiler/external-capture overhead measurement and the maximum tolerated observer effect.

Retain raw frame timestamps and scope samples; averages or screenshots alone are insufficient. Report p99 separately for every run. A pooled raw-frame percentile may be reported only as a descriptive workload statistic over pre-locked equal windows; it must not treat autocorrelated frames as independent observations or give a longer run accidental inferential weight. Regression decisions use the pre-locked paired run-level estimand with moving-block/hierarchical resampling clustered by run and stratified by device. Never average per-run percentiles to manufacture a pooled percentile. Retain every valid slow run and never define an outlier rule after seeing results. Load/transaction workloads retain every individual stall, not only window aggregates. A ten-minute representative soak is the minimum for memory-leak and sustained-thermal observation; the task packet must require a longer soak when the supported device class cannot reach stable thermal behavior within that window.

## 20.4 Required metrics

Record and retain raw data sufficient to compute:

- median, p95, p99, and maximum frame time;
- percentage of frames above 16.67 ms and 33.34 ms;
- longest consecutive sequence above 33.34 ms;
- transaction/load duration and worst non-presentation main-thread stall;
- process RSS/PSS or the best supported equivalent, peak memory, post-scenario retained memory, and soak trend;
- thermal state/throttling indicators before and after each run;
- crash, ANR, native signal, audio underrun/fallback, and resource-load errors;
- semantic trace/transaction result and artifact/build identity.
- paired baseline/candidate deltas with the pre-locked confidence interval or equivalent uncertainty estimate;
- per-device and cross-device run/block-level uncertainty without frame-level pseudoreplication;
- run-order, thermal-entry/exit, invalidation, replacement-run, and observer-overhead records.

If the profiler cannot emit raw p99 or raw samples, Android performance qualification is BLOCKED until instrumentation or an approved external capture provides equivalent evidence. Maxima do not silently substitute for p99.

## 20.5 Absolute product budgets and regression ceilings

Android performance qualification requires both pre-locked absolute product budgets and relative regression ceilings. A candidate cannot qualify merely because it is no slower than an already-unusable baseline.

Before candidate measurement, the controller must lock absolute budgets for at least:

- target refresh/frame-time classes and permitted percentages above 16.67 ms and 33.34 ms;
- startup to title and startup to first playable control;
- save, canonical load, pristine restart, phase transition, and tilemap/board commit duration;
- worst permitted non-presentation main-thread stall and consecutive slow-frame sequence;
- peak/retained memory and soak-growth limit; and
- crash, ANR, native-signal, audio-underrun, and resource-failure tolerance.

Product-specific budgets must identify the supported device/API population they protect and include any known problematic supported device class when available. They may replace the numerical defaults below only when locked before candidate measurement and may not weaken the minimum supported device matrix absent a separate support-policy decision. Against the approved same-device baseline, every required scenario must also satisfy:

- median frame/operation time: no more than 5% regression;
- p95: no more than 10% regression;
- p99: no more than 15% regression;
- frames above 33.34 ms: no more than 0.5 percentage-point absolute increase;
- no new sequence of three or more consecutive frames above 33.34 ms in steady-state gameplay;
- no new steady-state main-thread stall above 100 ms;
- peak and retained memory: no more than 10% regression and no monotonic leak during the soak;
- no crash, ANR, native signal, new audio/resource failure, or semantic divergence.

Scenario-specific startup/load/tilemap thresholds must be locked in the task packet before measurement because those transactions may intentionally exceed one frame. If either the required same-device baseline or the required pre-locked absolute budget is absent, report characterization only and mark Android performance qualification BLOCKED. `PASS WITH APPROVED EXCEPTIONS` may cover an auxiliary, non-material observation gap, but it may not waive the core physical-device matrix, raw samples, p99-equivalent evidence, absolute budgets, or same-device comparison.

For each relative ceiling, the packet must pre-lock the paired run-level estimand, equal-window rule, moving-block/hierarchical confidence method, block/cluster unit, device stratification, confidence level, and practical noise floor. Raw frames are never the independent inferential unit. PASS requires the absolute budget and the relative decision rule to pass without a post-hoc method change. If the uncertainty interval crosses a locked ceiling after the pre-declared maximum sample count, the scenario is `BLOCKED / INCONCLUSIVE`, not PASS; extra sampling is allowed only under the pre-locked stopping rule or a new controller-approved measurement packet. Statistical aggregation never hides a failing crash, ANR, native signal, semantic divergence, or absolute product budget.

The accepted Android off-world tilemap preparation budget remains `4_000_000 ns`. Every packet using it must name the exact profiler scope, start/end markers, clock source, inclusion/exclusion rule, and measured observer overhead. Changing that budget, measurement scope, cache capacity, or scheduling knob requires its own controller-authorized retuning task with before/after physical-device evidence and exact accepted Trace V2 equality.

---

# 21. TOKEN-BUDGET ACCEPTANCE RULES

The model allocation itself is part of project efficiency.

For each task report, Codex must state whether escalation was needed.

Rules:

- Do not use Sol for deterministic execution that Luna/Terra can verify.
- Do not use `ultra` as a default task setting.
- Do not re-read large unrelated files after the task scope is established.
- Prefer targeted file/function diffs over whole-repository exploration.
- Prefer one failing deterministic test over broad speculative debugging.
- Prefer direct baseline-vs-current comparisons over reconstructing behavior from memory.
- Stop after the task acceptance criteria are met; do not perform opportunistic refactors.
- Reuse approved harnesses and reports rather than regenerating equivalent analysis.
- If a task can be split into a cheap evidence-gathering subtask and an expensive reasoning subtask, gather evidence first.

The controller may downgrade future task assignments when earlier phases reduce uncertainty.

---

# 22. CONTROLLER DECISION LOG

| Date | Decision | Scope | Rationale |
|---|---|---|---|
| 2026-08-08 | Use `9314f54b` as initial PC behavioral reference | Core gameplay | Last clear pre-Android behavioral baseline before `52bd0403`; behavioral reference only. |
| 2026-08-08 | Recovery starts from current HEAD `0821182a` | Entire repo | Preserve project content, later features, fixes, assets, and Android support. |
| 2026-08-08 | One shared gameplay core | Architecture | Prevent PC/Android behavioral forks. |
| 2026-08-08 | Android specialization only behind semantic boundaries | Android | Preserve Android performance without partial live gameplay state. |
| 2026-08-08 | Preserve fast-forward, PC/Android debugger, profiler, restart, save/load enhancements | Features | Explicit product requirements. |
| 2026-08-08 | GPT-5.6 Luna/Terra/Sol policy | Process | Luna for mechanical work, Terra as default coder, Sol for semantic architecture/nonlocal debugging. |
| 2026-08-08 | Replace fixed strongest-model assignment with primary + escalation gates | Process | Start with the cheapest safe model; escalate only on evidence-defined conditions. |
| 2026-08-08 | `ultra` is escalation-only | Process | Avoid excessive token use on tasks with already-approved architecture. |
| 2026-08-11 | PLAN-V2 execution-contract overlay | Process | Require task packets, explicit DAG/phase manifests, reproducible evidence, waivers, fault tests, and rollback anchors for any replay or reopening without retroactively invalidating accepted history. |
| 2026-08-11 | Separate semantic recovery, Android runtime equivalence, and Android performance qualification | Release | WSA/host evidence may prove bounded runtime/semantic claims but cannot silently substitute for physical arm64-v8a performance qualification. |
| 2026-08-11 | Trace V1/golden custody is a separate controller task | Evidence | Prevent candidate failures from rewriting the oracle and require version/hash/provenance control. |
| 2026-08-11 | PLAN-V2-R1 historical bootstrap and oracle lock | Evidence | Make later replay executable without inventing retroactive PLAN-V2 artifacts; bind schema, runner, comparator, manifest, fixtures, environment, and acceptance into one immutable identity. |
| 2026-08-11 | Universal controller advancement with explicit review classes | Process | Remove the misleading implication that `Controller gate: No` permits autonomous advancement while retaining cheaper review for routine tasks. |
| 2026-08-11 | Ordered RNG evidence and dual absolute/relative performance gates | Correctness / Android | Detect equal-final-state ordering defects and prevent a candidate from qualifying merely by matching an unusable baseline. |
| 2026-08-11 | Canonical four-verdict live status | Authority | Prevent a historical combined P9-T02 PASS or WSA result from being read as physical Android performance qualification or merge authorization. |
| 2026-08-11 | Accepted bootstrap artifacts are mandatory before reopen | Evidence | Materialize historical acceptance, supersession, waivers, coverage, and oracle identity instead of treating the PLAN-V2 contract itself as evidence. |
| 2026-08-11 | Indexed task packets plus deterministic validator | Execution | Make exact commands, allowlists, dependencies, result rules, and evidence outputs machine-checkable before implementation. |
| 2026-08-11 | Invariant-to-evidence coverage matrix | Correctness | Bind every invariant and preservation claim to a scenario, platform, synchronization point, oracle, task, and immutable evidence identity. |
| 2026-08-11 | Approved semantic oracle with repeatability gate | Evidence | Allow explicit later correctness supersession while preventing candidate-defined expectations and nondeterministic golden capture. |
| 2026-08-11 | Expanded lifecycle scenario matrix | Correctness | Cover Test Chapter, overworld, roam, turnwheel/reversal, interruption, concurrency/cancellation, and versioned-save migration. |
| 2026-08-11 | Paired statistical Android qualification | Performance | Control run order, thermal state, observer effect, uncertainty, outliers, and pooled-percentile computation before deciding regression. |
| 2026-08-11 | Split stable contract, live state, packets, and evidence | Process | Reduce repeated context cost and prevent mutable authorization from drifting inside the long-lived architecture plan. |
| 2026-08-12 | PLAN-V2-R3 authority and machine-readable DAG closure | Process | Reject stale/copyable prose authority and scattered implicit edges; bind authorization, plan, controller state, packets, validator, graph, and review inputs by hash. |
| 2026-08-12 | Independent validator bootstrap trust root | Process | A validator cannot be the sole proof of its own correctness; freeze schema/fixtures/expected outcomes before O01 and require a different read-only reviewer. |
| 2026-08-12 | Preserve Trace V1 and require Trace V2 for new exact equality | Evidence | Initial/final RNG snapshots cannot prove draw order; keep historical V1 immutable and migrate observer-safely before recapture/oracle lock. |
| 2026-08-12 | Per-transaction linearization and side-effect matrix | Correctness | A generic COMMIT label hides partial RNG/event/UID/cache/save/resource effects; enumerate mutation order, compensation, cancellation, and fault boundaries. |
| 2026-08-12 | Machine-enforced dirty custody and mandatory isolation | Safety | Path lists alone do not protect dirty/untracked/ignored or zero-byte files; compare pre/post type, size, status, and SHA-256 and block overlap. |
| 2026-08-12 | Separate presentation-correctness child contracts | Correctness | Logical traces intentionally exclude surfaces and transient frames, so normal update/draw/present and visible-pixel invariants need their own frozen oracle without replacing semantics. |
| 2026-08-12 | Block-aware Android inference and lifecycle matrix | Performance | Autocorrelated frames are not IID and emulator/WSA is not physical proof; decide on paired run/block units and cover resume, low memory, audio focus, interruption, and worker shutdown. |
| 2026-08-12 | Mandatory isolated merge rehearsal before authorization | Release | A branch-local PASS does not prove the combined tree; pin both tips, audit conflicts against both parents, rerun gates, and keep the real merge separately authorized. |
| 2026-08-12 | External task-packet content identity | Process | A packet cannot hash a digest embedded in its own bytes; store the digest in the machine index over one exact UTF-8/LF byte contract. |
| 2026-08-12 | Derived-tree Trace V2 reference instrumentation | Evidence | Preserve `9314f54b` as the pristine semantic source while locking an observer-only patch, derived capture tree, non-allowlisted equality, and Trace OFF/ON proof. |
| 2026-08-12 | No production Trace-V2 opt-out | Correctness | Property/presentation oracles can supplement ordered-stream evidence but cannot silently replace T01-T03 for product-behavior work. |
| 2026-08-12 | Fresh P9-T04-R3 before merge rehearsal | Release | Historical final acceptance is not current merge readiness; bind a new validation node and P9-T05 to the exact same recovery tip. |

---

# 23. LIVE EXECUTION STATE POINTER

This section is informational and never authorizes work.

The only mutable live authorization source is:

`recovery/controller_state.md`

At PLAN-V2-R3 revision time, the accepted semantic recovery is complete, the final historical controller gate has passed, and there is no reusable next recovery task. `PLAN-V2-R3` is a one-off documentation authorization for `plan.md` only at base `c4c18a7c68f6fa7003d69ad13df6059fa412bc2d`, input plan SHA-256 `46BC58D39175ADCE6329B9AD4759834122DBE450C046E3132C4121B0B293F46E`, using `GPT-5.6 Sol / max` under an explicit controller override, with all changes left uncommitted. The authorization becomes historical and non-reusable when its task report is returned. It does not execute or authorize `P-V2-S00`, `P-V2-B00`, `P-V2-O01`, `P-V2-D00`, `P-V2-T01` through `P-V2-T03`, `P-V2-P00`, P9-T04-R3, P9-T05, creation of their planned artifacts, engine, tests, Trace implementation, comparator, manifest, oracle-lock creation, goldens, project data/assets, controller state, Git history, merge, push, tag, or release work.

If this snapshot ever disagrees with `recovery/controller_state.md` or a later explicit controller authorization, fail closed and follow Section 1.5. Do not edit this section to activate a task.

---

# 24. SHORT FORM CODEX REMINDER

1. Read `AGENTS.md`, `AGENTS.override.md`, `plan.md`, and `recovery/controller_state.md`.
2. Execute only hash-bound authority with an externally content-hashed, indexed, independently validated Section 7.1 packet, matching dependency-graph closure, and exact allowed-path list; inline authorization is documentation-only.
3. Start with the task's exact primary model/effort; stronger is not automatically authorized.
4. Verify authorization, plan, controller-state, packet, index, validator, dependency-graph, dirty-custody, and phase-exit identities; fail closed on any mismatch or self-certified trust root.
5. Escalate only on a named evidence-based condition and STOP before switching.
6. Terra is the default coder; Sol is reserved for semantics/nonlocal architecture; `ultra` is escalation-only.
7. PC gameplay semantics remain authoritative unless the controller approves a later correctness fix.
8. Preserve intended features, independent bugfixes, dirty user files, and protected project content.
9. Product-behavior replay/correction/reopening, shared optimizations, and presentation work require an independently reviewed Trace V2 oracle lock and T01-T03; no packet-level opt-out exists. Historical V1 remains custody evidence and production fixes never rewrite either oracle.
10. Reopened implementation requires accepted `P-V2-S00`, `P-V2-B00`, `P-V2-O01`, the graph-selected topology route, `P-V2-T01` through `P-V2-T03`, the locked pristine/derived reference-instrumentation proof, affected coverage rows, dirty custody, and any required transaction/presentation contract.
11. Android optimization cannot expose partial gameplay state; workers require immutable inputs, transaction linearization/side-effect contracts, cancellation, and stale-result rejection.
12. Semantic recovery, Android runtime equivalence, physical-device performance qualification, and merge/release are separate verdicts.
13. Android performance qualification must preserve the supported-device floor and pass pre-locked absolute budgets, paired run/block-level same-device regression ceilings, lifecycle scenarios, thermal/run-order controls, and the locked uncertainty rule.
14. Missing tests/evidence require BLOCKED or an explicit waiver; never plain PASS.
15. Presentation fixes require a registered child contract, frozen red hashes, normal update/draw/present output oracle, Trace V2 non-regression, and independent read-only approval.
16. Record reproducible evidence, raw hashes, waivers, risks, transaction/presentation IDs, dirty-custody result, rollback anchors, and Git disposition.
17. A fresh P9-T04-R3 must validate the exact recovery tip; matching P9-T05 must then rehearse that tip with the exact pinned target tip in isolation before any separate merge/release authorization.
18. Do not self-advance, mutate Git history, or opportunistically refactor.
