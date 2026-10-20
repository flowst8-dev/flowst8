---
name: review
description: Flow subcommand. Runs one flow:code-reviewer pass (no escalation) over the files changed on the current branch, or the latest pass manifest for a ticket, and shows severity-ranked findings. Run as /flow:review [ticket].
argument-hint: "[ticket]"
disable-model-invocation: true
---

# /flow:review — single code review

Arguments: `$ARGUMENTS` (an optional ticket key).

**Paths.** `${CLAUDE_PLUGIN_ROOT}` is the flow plugin root — the flow
reference files call it `{PLUGIN_ROOT}` — and
`${CLAUDE_PLUGIN_ROOT}/skills/run` is the run skill directory they
call `{SKILL_DIR}`. Honour
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/context-boundaries.md`.

**1. Pre-flight.** Read
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/preflight.md` and run it in
**subcommand mode** with `invocation: "review"`: config, standards,
memory, `run.start`, source mode, then `SPEC_ROOT`, `CARD_ROOT` and
`PASS_DIR` = the latest existing pass. No new pass folder. A ticket is optional here: without one, skip the path resolution and
the source-mode step.

**2. Files.** With a ticket whose latest pass has `{MANIFEST_PATH}`, use
its `files_written`. Otherwise use
`git diff --name-only origin/{base-branch}...HEAD` in the consuming
repo. No files → say so and stop.

**3. Review.** Dispatch the `flow:code-reviewer` agent (Agent tool,
`subagent_type: "flow:code-reviewer"`) with the block below as the prompt,
every `{token}` resolved to an absolute value. Its final message is
its JSON payload.

```
code-reviewer \
  --files {comma-separated paths} \
  --standards {consuming repo}/.flow/{board-key}-standards.md \
  --ticket {ticket, or omit} \
  --write {CARD_ROOT}/{PASS_DIR}/code-review-adhoc-{YYYYMMDD-HHMM}.md   # only with a ticket
```

One reviewer, no escalation, no retry loop, no fixes. The pipeline's
consolidated `{REVIEW_PATH}` is never overwritten.

**4. Show** the findings grouped by severity, with `file:line` and
category, and the findings file path when one was written.

Telemetry follows
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/emission-map.md` →
"Subcommand runs": one `phase.start` / `phase.end` pair around the agent
dispatch, then `run.end` (`failed` if the agent returned `ok: false`),
then move the run's telemetry buffer into the local telemetry file per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/telemetry-schema.md` →
"Where events go". Flow does not commit or push anything here.
