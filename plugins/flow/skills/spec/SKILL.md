---
name: spec
description: Flow subcommand. Regenerates spec.md for the latest pass of a ticket with the flow:spec-author agent, from a fresh card fetch. Run as /flow:spec {ticket}.
argument-hint: "{ticket}"
disable-model-invocation: true
---

# /flow:spec — refine the latest pass's spec

The ticket is `$ARGUMENTS`.

**Paths.** `${CLAUDE_PLUGIN_ROOT}` is the flow plugin root — the flow
reference files call it `{PLUGIN_ROOT}` — and
`${CLAUDE_PLUGIN_ROOT}/skills/run` is the run skill directory they
call `{SKILL_DIR}`. Honour
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/context-boundaries.md`.

**1. Pre-flight.** Read
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/preflight.md` and run it in
**subcommand mode** with `invocation: "spec"`: config, standards,
memory, `run.start`, source mode, then `SPEC_ROOT`, `CARD_ROOT` and
`PASS_DIR` = the latest existing pass. No new pass folder.

**2. Card.** Dispatch `flow:jira-fetch` with `jira-fetch {ticket}
--comments 5 --epic`, or use the staged payload on `paste`. On
`ok: false`, stop and show the error. The `flow:spec-author` agent
only accepts `card.source` ∈ `{"jira-mcp", "paste"}`; a `card_file` source
would fail with `SOURCE_UNSUPPORTED`.

**3. Spec.** Dispatch the `flow:spec-author` agent (Agent tool,
`subagent_type: "flow:spec-author"`) with the block below as the prompt,
every `{token}` resolved to an absolute value. Its final message is
its JSON payload.

```
spec-author \
  --card {card payload JSON} \
  --template ${CLAUDE_PLUGIN_ROOT}/skills/run/references/spec-template.md \
  --standards {consuming repo}/.flow/{board-key}-standards.md \
  --author "{git user.name} <{git user.email}>" \
  --branch {current branch of the consuming repo} \
  --write {SPEC_PATH}
```

If `{SPEC_PATH}` already exists, copy it to
`{CARD_ROOT}/{PASS_DIR}/spec-{YYYYMMDD-HHMM}.md` first, so the refinement never
silently overwrites the previous spec.

**4. Show** the spec path and a one-line summary (AC count, sections
marked `[NEEDS CLARIFICATION]`). The spec stays uncommitted under
`{CARD_ROOT}` — Flow never commits spec artifacts outside the full
pipeline's Wave F.

Telemetry follows
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/emission-map.md` →
"Subcommand runs": one `phase.start` / `phase.end` pair around the agent
dispatch, then `run.end` (`failed` if the agent returned `ok: false`),
then move the run's telemetry buffer into the local telemetry file per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/telemetry-schema.md` →
"Where events go". Flow does not commit or push anything here.
