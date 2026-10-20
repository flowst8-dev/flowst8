---
name: fetch
description: Flow subcommand. Fetches one Jira card with the flow:jira-fetch agent and shows the structured JSON payload. Run as /flow:fetch {ticket}.
argument-hint: "{ticket}"
disable-model-invocation: true
---

# /flow:fetch — card JSON

The ticket is `$ARGUMENTS`.

**Paths.** `${CLAUDE_PLUGIN_ROOT}` is the flow plugin root — the flow
reference files call it `{PLUGIN_ROOT}` — and
`${CLAUDE_PLUGIN_ROOT}/skills/run` is the run skill directory they
call `{SKILL_DIR}`. Honour
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/context-boundaries.md`.

**1. Pre-flight.** Read
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/preflight.md` and run it in
**subcommand mode** with `invocation: "fetch"`: config, standards,
memory, `run.start`, source mode, then `SPEC_ROOT`, `CARD_ROOT` and
`PASS_DIR` = the latest existing pass. No new pass folder.

**2. Fetch.** Dispatch the `flow:jira-fetch` agent (Agent tool,
`subagent_type: "flow:jira-fetch"`) with the block below as the prompt,
every `{token}` resolved to an absolute value. Its final message is
its JSON payload.

```
jira-fetch {ticket} --comments 5 --epic
```

On `source_mode: paste | card_file`, skip the dispatch and show the
staged payload instead.

**3. Show** the payload as a fenced JSON block. On `ok: false`, show the
`error_code` and message in one line.

Telemetry follows
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/emission-map.md` →
"Subcommand runs": one `phase.start` / `phase.end` pair around the agent
dispatch, then `run.end` (`failed` if the agent returned `ok: false`),
then move the run's telemetry buffer into the local telemetry file per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/telemetry-schema.md` →
"Where events go". Flow does not commit or push anything here.
