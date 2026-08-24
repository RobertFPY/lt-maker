# Recovery Control Override

This repository is currently under the PC-core semantics recovery program.

Before doing **any** recovery work in this repository, Codex MUST:

1. Read root `AGENTS.md` in full for repository architecture, commands, conventions, and subsystem gotchas.
2. Read root `plan.md` in full. `plan.md` is the authoritative recovery execution plan.
3. Read `recovery/controller_state.md` in full. It is the live controller-gate state and determines the currently authorized task when the static `CURRENT EXECUTION STATE` section in `plan.md` is stale.
4. Identify the exact authorized task ID from `recovery/controller_state.md`, then read that task's full definition in `plan.md`.
5. Read that task's **primary model/effort**, **escalation target**, prerequisites, invariants, acceptance criteria, and stop conditions.
6. Verify the current branch. Recovery work must not be performed directly on `master`; use `recovery/pc-core-semantics` or an explicitly controller-authorized child branch.
7. Start with the task's exact **primary** model/effort unless the controller has explicitly authorized the task's escalation target.
8. Never self-escalate. If a named escalation condition in `plan.md` is reached, STOP before expanding scope, report evidence, and ask the user/controller to authorize the specified escalation model/effort.
9. Never use a stronger model merely because it is available. The primary assignment is intentionally the cheapest configuration judged sufficient for the task.
10. Check all prerequisites and controller gates. Never self-advance to another task or phase.

For recovery work, ChatGPT is the plan owner/controller/reviewer/gatekeeper. Codex is the implementation executor. Codex must not independently redefine architecture, weaken acceptance criteria, accept semantic divergence for performance, bypass a controller gate, or spend higher-tier model budget without authorization.

Token-efficiency policy:

- Luna: deterministic/mechanical/report/verification work.
- Terra: default coding workhorse for bounded engineering.
- Sol: semantic architecture, nonlocal debugging, and high-blast-radius reconciliation.
- `ultra`: escalation-only unless `plan.md` is explicitly revised by the controller.

Authority order for recovery work:

1. `AGENTS.md` — repository architecture/conventions.
2. `plan.md` — recovery architecture, task definitions, invariants, model assignments, escalation and acceptance rules.
3. `recovery/controller_state.md` — live task authorization and controller-gate status; it overrides only a stale `CURRENT EXECUTION STATE` section in `plan.md`.
4. User instruction — may select/request the currently authorized task but may not bypass the above gates unless it contains explicit controller authorization.
