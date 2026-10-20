---
name: verify
description: Flow subcommand. Scores every acceptance criterion in the latest pass spec against the branch diff with one flow:ac-verifier (no escalation) and writes acceptance-criteria.md. Run as /flow:verify {ticket}.
argument-hint: "{ticket}"
disable-model-invocation: true
---

# /flow:verify — single AC verification

The ticket is `$ARGUMENTS`. (Not to be confused with the dry-run flag
`/flow:run {ticket} --verify`.)

**Paths.** `${CLAUDE_PLUGIN_ROOT}` is the flow plugin root — the flow
reference files call it `{PLUGIN_ROOT}` — and
`${CLAUDE_PLUGIN_ROOT}/skills/run` is the run skill directory they
call `{SKILL_DIR}`. Honour
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/context-boundaries.md`.

**1. Pre-flight.** Read
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/preflight.md` and run it in
**subcommand mode** with `invocation: "verify"`: config, standards,
memory, `run.start`, source mode, then `SPEC_ROOT`, `CARD_ROOT` and
`PASS_DIR` = the latest existing pass. No new pass folder.

If `{SPEC_PATH}` does not exist, stop with:
`⚠️  No spec.md for {ticket} in {PASS_DIR} — run /flow:run {ticket} or /flow:spec {ticket} first.`

**2. Verify.** Dispatch the `flow:ac-verifier` agent (Agent tool,
`subagent_type: "flow:ac-verifier"`) with the block below as the prompt,
every `{token}` resolved to an absolute value. Its final message is
its JSON payload.

```
ac-verifier \
  --spec {SPEC_PATH} \
  --diff-range origin/{diff-branch}...HEAD \
  --branch {current branch of the consuming repo} \
  --ticket {ticket} \
  --decision-log {DECISION_PATH} \
  --write {AC_PATH}
```

No `--reviewer-id`: in single-verifier mode the agent writes the final
checklist itself. The diff only sees committed work, so remind the
developer to commit first if the working tree is dirty.

**3. Show** the pass / partial / fail / manual tally, each non-pass AC
with its evidence, and any decision-log coverage gaps (advisory).

Telemetry follows
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/emission-map.md` →
"Subcommand runs": one `phase.start` / `phase.end` pair around the agent
dispatch, then `run.end` (`failed` if the agent returned `ok: false`),
then move the run's telemetry buffer into the local telemetry file per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/telemetry-schema.md` →
"Where events go". Flow does not commit or push anything here.
