---
name: test
description: Flow subcommand. Regenerates validation.md, front-end-testing.md and spec-testing.md for the latest pass with the flow:test-planner agent. Run as /flow:test {ticket}.
argument-hint: "{ticket}"
disable-model-invocation: true
---

# /flow:test — regenerate the test documents

The ticket is `$ARGUMENTS`.

**Paths.** `${CLAUDE_PLUGIN_ROOT}` is the flow plugin root — the flow
reference files call it `{PLUGIN_ROOT}` — and
`${CLAUDE_PLUGIN_ROOT}/skills/run` is the run skill directory they
call `{SKILL_DIR}`. Honour
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/context-boundaries.md`.

**1. Pre-flight.** Read
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/preflight.md` and run it in
**subcommand mode** with `invocation: "test"`: config, standards,
memory, `run.start`, source mode, then `SPEC_ROOT`, `CARD_ROOT` and
`PASS_DIR` = the latest existing pass. No new pass folder.

If `{SPEC_PATH}` does not exist, stop and point at `/flow:spec`.

**2. Plan.** Dispatch the `flow:test-planner` agent (Agent tool,
`subagent_type: "flow:test-planner"`) with the block below as the prompt,
every `{token}` resolved to an absolute value. Its final message is
its JSON payload.

```
test-planner \
  --spec {SPEC_PATH} \
  --diff-range origin/{diff-branch}...HEAD \
  --branch {current branch of the consuming repo} \
  --ticket {ticket} \
  --write {VALIDATION_PATH} \
  --frontend-guide {FRONTEND_TEST_PATH} \
  --spec-testing-guide {SPEC_TESTING_PATH}
```

**3. Show** the three paths, the scenario count and whether the change
has a front-end surface. The three documents stay uncommitted under
`{CARD_ROOT}` — Flow never commits spec artifacts outside the full
pipeline's Wave F.

Telemetry follows
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/emission-map.md` →
"Subcommand runs": one `phase.start` / `phase.end` pair around the agent
dispatch, then `run.end` (`failed` if the agent returned `ok: false`),
then move the run's telemetry buffer into the local telemetry file per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/telemetry-schema.md` →
"Where events go". Flow does not commit or push anything here.
