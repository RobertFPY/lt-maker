# Recovery Controller State

> Live controller-gate state. `plan.md` remains authoritative for architecture, invariants, task definitions, model policy, and global escalation rules. This file records the active P1-T03 escalation and prior controller decisions.

## Current authorization

- Current phase: Phase 1
- Harness gate: **P1-T02 ACCEPTED**
- Active task: **P1-T03 only**
- Latest executor stop: **ESC-03** during scenario 1 (`New game -> first playable map`)
- Divergent checkpoint: `player.control.ready`
- First divergent path: `/logical_state/rng/combat_state`
- Reference value: `992`
- Recovery value: `598`
- Controller disposition: **ESC-03 CONFIRMED**
- Authorized model for bounded diagnosis: **GPT-5.6 Sol / max**
- Escalation authorization: **YES, for this P1-T03 ESC-03 diagnosis only**
- Phase 2 remains **UNAUTHORIZED**
- Gameplay repair remains **UNAUTHORIZED**
- Golden/manifest blessing remains **UNAUTHORIZED** until the divergence is classified by controller review

## ESC-03 evidence accepted

The reference and recovery traces reach the same scenario checkpoint with matching semantic-delta hash and empty pending state, but combat RNG state differs (`992` vs `598`). This is a logical-state divergence, not presentation/provenance noise.

The Trace V1 RNG observer is not the source of the mismatch:

- reference and recovery use the same `LCG` implementation and the same `get_combat_random_state()` observer;
- the only Trace-harness-related change in `app/utilities/static_random.py` is a read-only growth-RNG state getter;
- reading combat RNG state does not advance it.

Therefore the next authorized work is to locate and classify the **first divergent combat-RNG consumption/order** between reference and recovery.

## P1-T03 ESC-03 diagnosis contract

Use **GPT-5.6 Sol / max**. This is an explicit controller-authorized escalation under ESC-03.

The diagnosis is evidence-only. Do not repair gameplay, alter RNG behavior, weaken Trace V1, bless an exception, regenerate a golden after mismatch, or begin Phase 2.

### Required diagnosis

For scenario 1 only, determine the earliest point at which the reference and recovery combat RNG streams diverge.

Prefer observer-only/test-owned instrumentation that records, for each combat-RNG mutation:

- pre-state;
- post-state;
- operation (`get_combat`, `get_randint`, `shuffle`, direct state set/restore, or equivalent);
- arguments/result when applicable;
- stable call-site/function identity;
- nearest semantic context/checkpoint/event/action when available.

Instrumentation must not consume additional RNG or change call ordering. Do not insert gameplay-side calls solely to make traces align.

### Root-cause classification

Once the first divergence is found, identify the smallest post-reference commit/file/function cluster responsible and classify it as one of:

1. **Likely recovery regression** — changed RNG consumption/order with no independently approved semantic reason;
2. **Known independent correctness fix** — divergence is caused by a later correctness fix that intentionally changes semantics;
3. **Harness/scenario mismatch** — the two runs are not actually receiving equivalent seed/input/content/bootstrap conditions;
4. **Reference ambiguity / competing semantics** — evidence is insufficient to choose behavior safely;
5. **Other** — explain precisely.

Do not choose category 2 merely because a post-reference commit is labeled a fix; prove the specific RNG divergence is a necessary consequence of that correctness fix.

### Required evidence report

Report at minimum:

- initial seed and all RNG states at scenario start for both runs;
- first matching RNG mutation sequence before divergence;
- first divergent RNG mutation with pre/post state, operation, call site, and semantic context;
- relevant reference-vs-recovery source diff or commit(s);
- whether project content/input/bootstrap is identical for the compared path;
- classification from the list above with evidence;
- whether scenario 1 can remain a strict PC-reference golden comparison or requires a controller semantic decision.

If the diagnosis discovers a second correctness-critical subsystem or a new semantic ambiguity, preserve evidence and STOP; do not broaden into a repair.

After the bounded ESC-03 diagnosis, STOP FOR CONTROLLER REVIEW. Do not continue scenarios 2-18 until the controller disposes of scenario 1.

## Prior controller decision — reference component-system bootstrap

Behavioral reference: `9314f54b49f4552b5a3d023b4da0012ce7dfbc89`.

`app/engine/skill_system.py` and `app/engine/item_system.py` are reference-owned generated artifacts. The reference `.gitignore` ignores them, and the reference-owned component generator deterministically creates them from source inputs at the same revision.

Authorized reference bootstrap remains:

1. verify reference HEAD exactly;
2. run only `generate_component_system_source()`;
3. do not hand-edit generated files;
4. do not copy generated files from recovery;
5. record generated SHA-256 hashes;
6. ensure normal git status remains clean;
7. use the generated outputs only to make that exact reference revision runnable.

A different missing artifact may be generated without escalation only if the exact reference contains its generator and authoritative inputs, the output is clearly generated, and no recovery implementation is copied in.

## Prior controller decision — scenario 17

Scenario 17 remains a hybrid reference-anchored + recovery metamorphic invariant:

- **17A:** PC reference with debugger/profiler absent/disabled establishes the baseline;
- **17B:** recovery disabled must equal the reference baseline;
- **17C:** recovery debugger enabled-idle must equal recovery disabled after exiting temporary UI state and without mutating debug commands;
- **17D:** recovery profiler enabled-idle must equal recovery disabled in logical state/order/RNG; profiler diagnostics are provenance only.

There is no simulated PC-reference enabled-idle debugger/profiler golden.

## Gate status

Only the bounded P1-T03 ESC-03 diagnosis above is authorized now. Phase 2 and all gameplay repairs remain blocked.