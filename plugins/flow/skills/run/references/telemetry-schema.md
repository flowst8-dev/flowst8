# Flow telemetry — event schema

> Every Flow command writes a small JSONL event file on the
> developer's machine, under `{repo}/.flow/.telemetry/`. Nothing is
> committed or pushed. The schema below is the contract between the
> events and whatever reads them — `/flow:report` first of all.

**Schema version `2`.**

The design is **event-driven, not summary-driven**. Emit at phase
boundaries, not once at the end. A crash mid-run is captured by the
*absence* of `run.end` rather than the loss of the whole record.

---

## Where events go

Every run's events end up in one local file:

```
{repo}/.flow/.telemetry/{YYYY-MM}/{run_id}__{user}__{command}__{ticket}.jsonl
```

- `{repo}` — the consuming repo root. The folder is fixed under the repo
  and does not depend on `FLOW_SPEC_ROOT`.
- `{YYYY-MM}` — the month of the `run_id` timestamp (UTC).
- `{user}` — slug of `run.start.user`: lowercase, every run of
  non-alphanumeric characters collapsed to `-`, edges trimmed
  (`jane.doe@example.com` → `jane-doe-example-com`).
- `{command}` — `run.start.invocation` (`run`, `dry-run`, `spec`,
  `code`, `test`, …).
- `{ticket}` — the ticket key, or `no-ticket`.
- `__` separates fields because user slugs and ticket keys contain `-`.

Every run gets a file — full pipeline, subcommand, dry run, or a run
that fails in pre-flight. A file is written during its run and never
edited afterwards.

**Buffering during a run.** Events are appended to a per-run scratch
file first, because `run.start` is emitted before every path is
resolved:

- POSIX: `~/.claude/flow/telemetry-buffer/{run_id}.jsonl`
- Windows: `%USERPROFILE%\.claude\flow\telemetry-buffer\{run_id}.jsonl`

**Finalize step — the last act of every command.** After `run.end` has
landed in the buffer, move the buffer into the telemetry folder with the
bundled script:

```bash
python "{PLUGIN_ROOT}/scripts/telemetry_flush.py" flush \
  --run-id {run_id}
```

The script finds the repo from the run's `cwd` (or `--repo`, when given)
and works without the spec root, so it runs even when pre-flight failed
before resolving `SPEC_ROOT`. What it does:

1. Appends the buffer to the run's file under
   `{repo}/.flow/.telemetry/{YYYY-MM}/` and deletes the buffer.
2. If `{repo}/.flow/.telemetry/` did not exist yet, creates it with a
   `.gitignore` containing `*` and `!.gitignore`, so telemetry stays out
   of git even when the spec root lives inside a repo. A team that wants
   telemetry under version control deletes that `.gitignore`; Flow
   never recreates it in an existing folder.
3. Prints one JSON line: `{ok, run_id, telemetry_path, error}`.

No commit, no push, no network — Flow never commits or pushes
telemetry. The script always exits 0; if it reports an error, mention it
in one line and move on. The plugin's `Stop` hook
(`hooks/flow-telemetry-recover.py`) runs `telemetry_flush.py recover`
at the end of every turn, which moves any buffer older than 30 minutes —
a run that crashed before its finalize step — into the same folder.
Pre-flight does not recover anything; the hook owns it.

If `FLOW_TELEMETRY_ENABLED=false` (env var or `.flow/config.md`),
skip all emission silently — no error, no buffer, no telemetry file.

### Emitting an event

Build the JSON with a safe emitter and append the line to the buffer.
**Python is preferred** — it is on every developer machine that runs the
plugin's hooks, and `json.dumps` handles embedded quotes, newlines and
backslashes correctly every time:

```bash
python - <<'PYEOF'
import json, os, pathlib
ev = {"ts": "2026-07-28T14:03:22Z", "run_id": os.environ["RUN_ID"],
      "event": "run.start", "flow_version": "2.0.0", "schema_version": "2", ...}
p = pathlib.Path.home() / ".claude" / "flow" / "telemetry-buffer" / (os.environ["RUN_ID"] + ".jsonl")
p.parent.mkdir(parents=True, exist_ok=True)
with p.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
PYEOF
```

**Windows path caveat.** Python on Windows does not understand Git
Bash's `/c/Users/...` form. Build paths inside Python (as above, from
`Path.home()`), or pass the drive-letter form.

**Alternate: jq**, when it is installed (`command -v jq >/dev/null`
first — Git for Windows does not ship it). **Alternate: PowerShell** —
`ConvertTo-Json -Compress` on a hashtable, appended with
`Out-File -Append -Encoding utf8`.

**Never** use a naked `echo '{"…":"…"}' >> buf` — an embedded
apostrophe, newline or backslash produces invalid JSON, and readers
choke on the broken line.

---

## Common fields (present on every event)

| Field | Type | Notes |
|-------|------|-------|
| `ts` | ISO-8601 UTC | Timestamp for this event — always UTC (`Z` suffix). |
| `run_id` | string | Stable id for one Flow invocation: `YYYYMMDD-HHMMSSZ-{4-char-rand}`, e.g. `20260727-140322Z-a3f9`. Assigned at `run.start` and carried on every later event. |
| `event` | enum | One of `run.start`, `run.end`, `phase.start`, `phase.end`, `phase.error`, `artifact`, `outcome`. |
| `flow_version` | string | The run skill's `version:` frontmatter. Repeated on every event so a stream is readable without joining back to `run.start`. |
| `schema_version` | string | Version of this schema the event was written against: `"2"`. Schema `"1"` run files (written before the rename to Flow) carry the same value as `flow_version` under the key `specflow_version`; readers fall back to it. |

---

## Event types

### `run.start`

Emitted once, at the end of pre-flight step 6 (after config resolution,
before Wave A). Carries the identity and version map for the whole run.

| Field | Type | Notes |
|-------|------|-------|
| `ticket` | string | e.g. `PROJ-123`. |
| `board_prefix` | string | Derived from the ticket (`PROJ`). |
| `invocation` | enum | `run` (full pipeline), `dry-run` (`/flow:run {ticket} --verify`), `brief`, `spec`, `code`, `review`, `verify` (the `/flow:verify` subcommand), `fetch`, `test`, `playwright`, `decisions`, `log`. |
| `flags` | object | Flat map of resolved flags that shape the run (`iterate\|overwrite`, `no_push`, `pr_mode`, `docs_only`, `handoff`, `retry_budget`, `e2e_dir`). One level deep, no nested objects. |
| `base_branch` | string | Resolved `BASE_BRANCH`. |
| `diff_branch` | string | Resolved `DIFF_BRANCH`. |
| `pass_dir` | string | Resolved `PASS_DIR` (e.g. `p03`). |
| `spec_root` | string | Absolute resolved `SPEC_ROOT`. The recovery hook uses it to place a crashed run's buffer. |
| `user` | string | `git config user.email`; falls back to `git config user.name`, then `unknown@localhost`. |
| `host` | string | `hostname` (or `$env:COMPUTERNAME` on PowerShell). |
| `agents` | object | Version map `{agent_name: version}` for **every** sub-agent that could be invoked this run, whether it fires or not. Read each `> **Version:** X.Y.Z` line from `{PLUGIN_ROOT}/agents/{name}.md`, plus `brief` from `{PLUGIN_ROOT}/skills/brief/SKILL.md`; a file with no stamp records `"unstamped"`. The most important field for version-impact analysis — a change to `code-reviewer` shifts outcomes without touching Flow's own version. |
| `cwd` | string | Repository working directory at run start. |
| `git_head` | string \| null | `git rev-parse HEAD` at run start, or `null` outside a repo. |
| `model` | string | Model id of the orchestrating session, as the session states it. `"unknown"` when it does not — never guess. |
| `agent_models` | object | `{agent_name: model}` from the `model:` frontmatter of each file in `{PLUGIN_ROOT}/agents/`, recorded raw (`inherit` stays `inherit`; missing → `"unset"`). Same keys as `agents`, minus `brief`. |

### `phase.start`

Emitted just before a lane or phase runs. Carries only what identifies
the phase — durations come from the paired `phase.end`.

| Field | Type | Notes |
|-------|------|-------|
| `phase` | string | Canonical phase id — see "Phase ids" below. |
| `agent` | string | Optional. The plugin agent dispatched (e.g. `jira-fetch`, `implementer`). Omitted for orchestrator-only phases such as `wave.b.join`. |

### `phase.end`

Emitted when a phase returns `ok: true`, or when a phase is skipped.
Pairs with `phase.start` on `run_id` + `phase`.

| Field | Type | Notes |
|-------|------|-------|
| `phase` | string | Same value as the paired `phase.start`. |
| `agent` | string | Same as the paired start, if any. |
| `outputs` | object | Small, flat, phase-specific result — e.g. jira-fetch `{ac_count: 8, has_parent: true}`, implementer `{acs_completed: 5, acs_deferred: 3, files_written_count: 4}`, ac-verifier `{pass: 5, partial: 1, fail: 2, manual: 0}`. A skipped phase carries `{skipped: true, reason}` and no `phase.start`. Big blobs go in `artifact` events. |
| `usage` | object | Present when the phase dispatched a plugin agent; omitted for orchestrator-only and skipped phases. See "Agent usage". |

### `phase.error`

Emitted when a phase returns `ok: false` or the orchestrator catches an
exception running it.

| Field | Type | Notes |
|-------|------|-------|
| `phase` | string | Same convention as `phase.start`. |
| `agent` | string | If applicable. |
| `error_code` | string | The agent's `error_code` when available, else a short slug (`mcp_unavailable`, `git_conflict`, `transition_not_found`, `ac_deferred`, `unknown`). Pre-flight step 7 codes are listed in the emission map. |
| `error_message` | string | One line, truncated to ~200 characters. |
| `terminal` | bool | `true` if this error halts the run (a Wave A/B lane, the Wave C implementer, a pre-flight hard-fail). `false` if the pipeline continues (Waves G/H, Phase 5c, Phases 6/7). |
| `usage` | object | As on `phase.end`, when an agent was dispatched and returned — a failed agent still spent tokens. |

### `artifact`

Emitted after a phase produces a file a human or a later phase is
expected to read, so a reader can build an inventory without walking
the disk.

| Field | Type | Notes |
|-------|------|-------|
| `phase` | string | The phase that produced it. |
| `kind` | enum | `spec`, `manifest_json`, `manifest_md`, `code_review`, `ac_checklist`, `validation`, `frontend_test`, `spec_testing`, `playwright_spec`, `test_results`, `handoff`, `flow_log`, `decision_log`, `pull_request`, `drift_report`. `playwright_spec` is one event per spec file Wave H writes into the consuming codebase's e2e suite; `test_results` is the `test-plan-results.md` that `/flow:playwright` writes; `handoff` is the Phase 7 `handoff.md`; `drift_report` is the `drift.md` the drift check writes into the latest pass folder. Extend the enum only when a new artifact kind exists. |
| `path` | string | Absolute path for local files; URL for a pull request. |
| `bytes` | integer | Optional. Size for local files; omitted for URLs. |

### `outcome`

Emitted at most once per scored phase family, at its final round —
`ac_verify` (Wave D, `/flow:verify`) and `code_review` (Wave E,
`/flow:review`). Redundant with `phase.end.outputs`, but pulled out so
readers can key off `event` alone.

| Field | Type | Notes |
|-------|------|-------|
| `kind` | enum | `ac_verify`, `code_review`. |
| `results` | object | `ac_verify`: `{pass, partial, fail, manual}` counts. `code_review`: `{high, medium, low}` finding counts. |
| `retries_used` | integer | Fix cycles spent in this wave's retry loop (0 for subcommands). |
| `retries_halted_no_op` | bool | `true` when the loop stopped early because a fix touched no flagged file. |

### `run.end`

Emitted once, at the end of Phase 8 (or of a subcommand), after the
run-log summary block is written and before the finalize step. Always
emitted, even on failure paths.

| Field | Type | Notes |
|-------|------|-------|
| `status` | enum | `success`, `partial`, `failed` — the Phase 8 rubric: `success` = every phase ok and every AC `pass`/`manual`; `partial` = ACs remain `fail`/`partial` but no phase errored; `failed` = at least one phase halted. |
| `phases_completed` | array of strings | Every base phase id that emitted a `phase.end` this run (retry variants deduped to their base id). |
| `terminal_phase` | string \| null | The phase that halted the run, or `null` on success/partial. **The most valuable field for reliability analysis.** |
| `retry_budget_used` | integer | Fix cycles consumed across Waves E and D (shared budget). |
| `duration_ms` | integer | `run.end.ts` − `run.start.ts`, computed by the shell from the two timestamps, never estimated. Readers recompute it from `ts` when the two disagree. |
| `usage_totals` | object | Sums over every `usage` object this run: `{tokens, tool_uses, agent_duration_ms, dispatches, dispatches_missing_usage}`. `tokens`, `tool_uses` and `agent_duration_ms` sum the non-null values; `dispatches` counts every agent dispatch; `dispatches_missing_usage` counts dispatches whose usage was not reported. |

### Agent usage

Every Agent tool dispatch reports what it spent when it returns: a
foreground dispatch in the tool result, a background dispatch in its
task notification. Copy those numbers into the phase's `usage` object;
do not estimate, round or recompute them.

| Field | Type | Source |
|-------|------|--------|
| `tokens` | integer \| null | The reported subagent token count. |
| `tool_uses` | integer \| null | The reported tool-call count. |
| `duration_ms` | integer \| null | The reported wall-clock for the dispatch. |
| `model` | string | The agent's `model:` frontmatter; `inherit` resolves to `run.start.model`. |
| `dispatches` | integer | Only when one phase made several dispatches (a lane re-dispatched after `AGENT_BAD_PAYLOAD`, or `/flow:playwright`'s author + run pair); `usage` then sums them. |

A value the result did not report is `null` — readers count it as
missing, not zero. Parallel escalation reviewers (`r2`, `r3`) are
separate phases, so each carries its own `usage`.

---

## Phase ids

Every `phase` value Flow emits. Where and with which `outputs` is in
`emission-map.md`.

| Phase id | Agent | Emitted by |
|----------|-------|------------|
| `preflight.source_resolved` | — | Pre-flight step 7 |
| `wave.a.jira_fetch` | `jira-fetch` | Wave A · A1; `/flow:fetch`, `/flow:brief`, `/flow:spec` |
| `wave.a.decision_logger` | `decision-logger` | Wave A · A2; `/flow:decisions` |
| `wave.a.settings_write` | — | Wave A · A3 |
| `wave.a.join` | — | Wave A join |
| `wave.b.branch_manager` | `branch-manager` | Wave B · B1 |
| `wave.b.spec_author` | `spec-author` | Wave B · B2; `/flow:spec` |
| `wave.b.join` | — | Wave B join |
| `wave.c.implementer` | `implementer` | Wave C; `/flow:code` |
| `wave.c.join` | — | Wave C join |
| `phase.drift.check` | `drift-checker` | Drift check after Wave C (before Wave E or F); `/flow:drift` |
| `wave.e.code_review` | `code-reviewer` | Wave E when skipped (`docs-only`) |
| `wave.e.code_review.r1`, `.r2`, `.r3` | `code-reviewer` | Wave E reviewers; `/flow:review` uses `.r1` |
| `wave.e.retry_{n}.implementer` | `implementer` | Wave E retry fix (targeted mode) |
| `wave.e.retry_{n}.commit` | `branch-manager` | Wave E retry commit |
| `wave.e.retry_{n}.r1`, `.r2`, `.r3` | `code-reviewer` | Wave E re-review after a retry |
| `wave.e.retry_{n}.halted` | — | Wave E early halt |
| `wave.e.consolidate` | — | Wave E consolidation |
| `wave.f.spec_commit` | `branch-manager` | Wave F · F1 |
| `wave.f.code_commit` | `branch-manager` | Wave F · F2 |
| `wave.f.join` | — | Wave F join |
| `wave.d.ac_verify` | `ac-verifier` | Wave D when skipped (`docs-only`) |
| `wave.d.ac_verify.r1`, `.r2`, `.r3` | `ac-verifier` | Wave D verifiers; `/flow:verify` uses `.r1` |
| `wave.d.retry_{n}.implementer` | `implementer` | Wave D retry fix (targeted mode) |
| `wave.d.retry_{n}.commit` | `branch-manager` | Wave D retry commit |
| `wave.d.retry_{n}.r1`, `.r2`, `.r3` | `ac-verifier` | Wave D re-verification after a retry |
| `wave.d.retry_{n}.halted` | — | Wave D early halt |
| `wave.d.consolidate` | — | Wave D consolidation |
| `wave.g.test_planner` | `test-planner` | Wave G; `/flow:test` |
| `wave.h.playwright_testing` | `playwright-testing` | Wave H (author); `/flow:playwright` (author + run) |
| `wave.h.commit` | `branch-manager` | Wave H commit |
| `phase.5c.branch_publish` | `branch-manager` | Phase 5c |
| `phase.6.jira_status` | — | Phase 6 (`--handoff`) |
| `phase.7.handoff` | — | Phase 7 (`--handoff`) |
| `phase.8.spec_commit` | `branch-manager` | Phase 8 closing spec commit |
| `phase.8.close_run_log` | — | Phase 8 |

---

## Version-map convention

Every agent file under `{PLUGIN_ROOT}/agents/` (and the `brief` skill,
`{PLUGIN_ROOT}/skills/brief/SKILL.md`) carries a version stamp near the
top, below its frontmatter:

```markdown
# {agent-name} — {tagline}

> **Version:** 2.0.0
```

Grep-friendly (`grep -m1 "^> \*\*Version:" agents/*.md` from the plugin
root). Read the first ~30 lines of each file during pre-flight to build
the `agents` map for `run.start`. Files missing the stamp record as
`"unstamped"` — never fabricate a version.

Bumping rules (semver, informal):

- **Patch** — prose cleanup, no behavior change.
- **Minor** — new capability, new optional argument, new output field.
  Callers on the old contract still work.
- **Major** — breaking change: renamed argument, removed output field,
  different exit semantics. The orchestrator changes in the same commit.

The orchestrator's own version lives in the run skill's `version:`
frontmatter and bumps on the same scale. A schema change that readers
must handle bumps `schema_version`; events already written are never
rewritten.

---

## Reading telemetry

Everything is local, under `{repo}/.flow/.telemetry/`:

- `/flow:report` — headline totals, per-command, per-ticket and
  per-agent tables, quality signals and recent runs, plus an optional
  self-contained HTML dashboard (`--html`). It runs
  `{PLUGIN_ROOT}/scripts/flow_report.py`; see
  `{PLUGIN_ROOT}/skills/report/SKILL.md`.
- Glob by filename — `{repo}/.flow/.telemetry/2026-09/*__dry-run__*.jsonl`,
  `{repo}/.flow/.telemetry/*/*__PROJ-123.jsonl`.
- Query the folder as one table, e.g. DuckDB
  `SELECT * FROM read_json_auto('.flow/.telemetry/**/*.jsonl')`.

`/flow:report` is a read-only viewer and emits no telemetry of its
own, so looking at the data never changes it.

## Retention

Flow never edits or deletes a telemetry file once its run is over.
Month folders are the natural boundary if you want to archive or prune —
that is the developer's call, made by hand.

## Privacy

Records include `user` (git email), `host`, `cwd`, `spec_root` and the
ticket you were working on. They stay on the machine that wrote them:
Flow never commits, pushes or uploads telemetry, and the folder's
`.gitignore` keeps it out of git. A team that wants shared numbers can
delete that `.gitignore` and commit the files deliberately — that is an
explicit choice, never a default.

**Opting out:** set `FLOW_TELEMETRY_ENABLED=false` in
`.flow/config.md` or the environment. No events are emitted, no
buffer is created and no telemetry file is written.
