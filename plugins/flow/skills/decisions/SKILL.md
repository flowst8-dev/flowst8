---
name: decisions
description: Flow subcommand. Appends decisions from pasted meeting notes, a chat thread, an email, a file or a Jira comment URL to a ticket's card-level decision log, via the flow:decision-logger agent. Works before the Jira card exists. Run as /flow:decisions {ticket} [--decisions content].
argument-hint: "{ticket} [--decisions {content}]"
disable-model-invocation: true
---

# /flow:decisions — update the decision log

Arguments: `$ARGUMENTS` — the ticket, optionally followed by
`--decisions {content}`.

**Paths.** `${CLAUDE_PLUGIN_ROOT}` is the flow plugin root — the flow
reference files call it `{PLUGIN_ROOT}` — and
`${CLAUDE_PLUGIN_ROOT}/skills/run` is the run skill directory they
call `{SKILL_DIR}`. Honour
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/context-boundaries.md`.

**1. Pre-flight.** Read
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/preflight.md` and run it in
**subcommand mode** with `invocation: "decisions"`: config, standards,
memory, `run.start`, source mode, then `SPEC_ROOT`, `CARD_ROOT` and
`PASS_DIR` = the latest existing pass. No new pass folder. **Skip step 7
(source mode) entirely** — pre-card mode is legitimate here, so neither MCP
availability nor ticket-key validation gates it.

The full pipeline also runs Steps 1–4 below as Wave A · A2 when
`/flow:run {ticket}` is given `--decisions`.

# Decision Log subprocess

This block runs whenever flow needs to update the decision log — either
because `--decisions` was passed on a full pipeline run (runs as Phase 0,
before jira-fetch) or because the user invoked `/flow:decisions {ticket}`
on its own.

### Step 1 — Resolve the input

If invoked via `/flow:decisions {ticket}` with no `--decisions` value, prompt
the user:

```
📝 Decision-log update for {ticket}.
Paste meeting notes / chat thread / email body / Jira comment URL below.
Press enter on an empty line to finish.
```

Otherwise, take the value of `--decisions` and resolve it:

| Form | Detection | Resolution |
|------|-----------|------------|
| File path | starts with `./`, `/`, `~/`, or `{drive}:\` and exists on disk | Read the file contents |
| Jira comment URL | matches `https://*.atlassian.net/.*?(focusedCommentId\|comment).*` | Fetch the comment via Atlassian MCP `fetch` tool |
| Plain text | anything else | Use as-is |

The result is a string called `content`. If `content` is empty after
resolution, abort with: `⚠️  Decision-log update aborted — no content.`

Track a `source-label` describing where the content came from (e.g.
"chat paste 2026-04-30", "meeting-notes.txt", "Jira comment PROJ-123#42").

### Step 2 — Ensure the decision log exists

If `{DECISION_PATH}` does not exist, create it from
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/decision-log-template.md`. Populate the header with the card
title and Jira URL **if** jira-fetch has already run (full pipeline) and
returned ok — otherwise leave the pre-card placeholders in place. The
decision-logger sub-agent will fill them in later if/when the card resolves.

Never overwrite an existing decision log file in this step. Existing rows
are sacred — append-only. Even the header is left alone unless transitioning
out of pre-card mode.

### Step 3 — Call decision-logger

Dispatch the `flow:decision-logger` agent (Agent tool, `subagent_type: "flow:decision-logger"`) with this prompt:

```
decision-logger \
  --content {content} \
  --decision-log-path {DECISION_PATH} \
  --template ${CLAUDE_PLUGIN_ROOT}/skills/run/references/decision-log-template.md \
  --ticket {ticket} \
  --card {jira-fetch payload, or null if pre-card} \
  --source-label "{source-label}" \
  --write {DECISION_PATH}
```

Capture the success payload — the rows added, rows skipped as duplicates,
and any candidates needing user confirmation.

### Step 4 — Display the result

Show a short summary in chat:

```
✅ Decision log updated for {ticket}
   → {N} new row(s) added, {M} skipped as duplicates
   → {K} candidate(s) flagged for confirmation (if any)
   File: {DECISION_PATH}
```

If candidates_needing_confirmation is non-empty, list them so the user
knows what was *not* added (and why) and can decide whether to re-paste
with clearer phrasing.

### Pre-card mode

When `/flow:decisions {ticket}` is run before the Jira card exists:

1. Skip jira-fetch entirely.
2. `CARD_ROOT` is `{SPEC_ROOT}/default/{ticket}` (see preflight.md,
   "CARD_ROOT"). The decision log goes there, not under a typed folder,
   because the card's type is not known yet.
3. Decision-logger writes the log with `Jira URL: [NEEDS CLARIFICATION] —
   pre-card mode` in the header.
4. Later, when `/flow:run {ticket}` fetches the card for the first time, the
   `default/{ticket}` folder moves into the typed folder for the card's type
   (preflight.md, "CARD_ROOT" step 3). The header is updated with the
   now-known card title and URL; rows are untouched.

Telemetry follows
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/emission-map.md` →
"Subcommand runs": one `phase.start` / `phase.end` pair around the agent
dispatch, then `run.end` (`failed` if the agent returned `ok: false`),
then move the run's telemetry buffer into the local telemetry file per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/telemetry-schema.md` →
"Where events go". Flow does not commit or push anything here.
