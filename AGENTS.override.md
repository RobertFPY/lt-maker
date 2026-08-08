# Recovery Control Override

This repository is currently under the PC-core semantics recovery program.

Before doing **any** recovery work in this repository, Codex MUST:

1. Read root `AGENTS.md` in full for repository architecture, commands, conventions, and subsystem gotchas.
2. Read root `plan.md` in full. `plan.md` is the authoritative recovery execution plan.
3. Identify the exact authorized task ID from `plan.md` and the user's instruction.
4. Read that task's **primary model/effort**, **escalation target**, prerequisites, invariants, and stop conditions.
5. Verify the current branch. Recovery work must not be performed directly on `master`; use `recovery/pc-core-semantics` or an explicitly controller-authorized child branch.
6. Start with the task's exact **primary** model/effort unless the controller has explicitly authorized the task's escalation target.
7. Never self-escalate. If a named escalation condition in `plan.md` is reached, STOP before expanding scope, report evidence, and ask the user/controller to authorize the specified escalation model/effort.
8. Never use a stronger model merely because it is available. The primary assignment is intentionally the cheapest configuration judged sufficient for the task.
9. Check all prerequisites and controller gates. Never self-advance to another task or phase.

For recovery work, ChatGPT is the plan owner/controller/reviewer/gatekeeper. Codex is the implementation executor. Codex must not independently redefine architecture, weaken acceptance criteria, accept semantic divergence for performance, bypass a controller gate, or spend higher-tier model budget without authorization.

Token-efficiency policy:

- Luna: deterministic/mechanical/report/verification work.
- Terra: default coding workhorse for bounded engineering.
- Sol: semantic architecture, nonlocal debugging, and high-blast-radius reconciliation.
- `ultra`: escalation-only unless `plan.md` is explicitly revised by the controller.

If this file and `plan.md` conflict, `plan.md` governs task details, model assignments, escalation conditions, and controller decisions; this file governs the mandatory read/gating protocol.
