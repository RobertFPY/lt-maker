# Recovery Control Override

This repository is currently under the PC-core semantics recovery program.

Before doing **any** work in this repository, Codex MUST:

1. Read the root `AGENTS.md` in full for repository architecture, commands, conventions, and subsystem gotchas.
2. Read the root `plan.md` in full. `plan.md` is the authoritative recovery execution plan.
3. Identify the exact authorized task ID from `plan.md` and the user's instruction.
4. Enforce the exact model/reasoning gate defined for that task. If the current model cannot be verified or does not exactly satisfy the task gate, STOP before editing and ask the user to switch to the required model or return to the controller.
5. Verify the current branch. Recovery work must not be performed directly on `master`; use `recovery/pc-core-semantics` or an explicitly controller-authorized child branch.
6. Check all prerequisites and controller gates. Never self-advance to another task/phase.

For recovery work, ChatGPT is the plan owner/controller/reviewer/gatekeeper. Codex is the implementation executor. Codex must not independently redefine architecture, weaken acceptance criteria, accept semantic divergence for performance, or bypass a controller gate.

If this file and `plan.md` conflict, `plan.md` governs recovery task details while this file governs the mandatory read/gating protocol.
