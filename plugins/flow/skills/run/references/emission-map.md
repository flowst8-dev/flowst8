<!-- Part of the run skill. Read on demand from SKILL.md.
     {SKILL_DIR} = the run skill's base directory; {PLUGIN_ROOT} = the
     flow plugin root. SKILL.md defines both. -->

## Instrumentation (telemetry emission points)

Flow emits a small JSONL event stream at every phase boundary. The
field contract and the list of phase ids live in
`{SKILL_DIR}/references/telemetry-schema.md`. This file maps the schema
onto the pipeline phases (in `pipeline-*.md`) so you know *what* to emit
*where* without re-deriving it each run.

Rules that apply to every event:

- Skip the emission entirely if `FLOW_TELEMETRY_ENABLED=false`. No warning.
- Every event carries `ts` (ISO-8601 UTC), `run_id`, `event`,
  `flow_version` and `schema_version` (`"2"`).
- **Agent usage.** Every `phase.end` or `phase.error` for a phase that
  dispatched a plugin agent carries `usage: {tokens, tool_uses,
  duration_ms, model}`, copied from what the Agent tool reported for
  that dispatch (the tool result, or the task notification for a
  background dispatch). Unreported values are `null`, never estimated.
  Keep a running sum for `run.end.usage_totals`. Skipped and
  orchestrator-only phases carry no `usage`. Field rules:
  `telemetry-schema.md` → "Agent usage".
- A skipped phase emits one `phase.end` with `{skipped: true, reason}`
  and no `phase.start`.
- The full pipeline's `run.start` carries `invocation: "run"`.
- Best-effort: if the append itself throws, log to `{LOG_PATH}` and
  continue. A telemetry failure never halts the pipeline.
- Timestamps come from the invoking shell (`date -u +…` on Bash,
  `Get-Date` in UTC on PowerShell), not from Claude's context.

### Emission map

| Location | Emit |
|----------|------|
| End of pre-flight (step 6) | `run.start` — identity, flag map, version map, `pass_dir`, `spec_root`, `git_head`, `model`, `agent_models` |
| Pre-flight step 7 (source resolution) | `phase.end` `preflight.source_resolved` with `{mode, mcp_available, argument_was_valid, ticket_key_normalized, card_file_path, card_file_format}`. On hard-fail, `phase.error` (`terminal: true`) with an `error_code` from `{card_file_missing, card_file_bad_json, card_file_missing_keys, ticket_key_absent, mcp_down, bad_ticket_key, mcp_down_and_bad_key}`. Not emitted for `/flow:decisions` |
| Wave A dispatch | `phase.start` `wave.a.jira_fetch` (A1) first. Once A1 returns the card payload and `CARD_ROOT` exists, `phase.start` × 2 for `wave.a.decision_logger` (A2) and `wave.a.settings_write` (A3), which run in parallel. On `source_mode: paste\|card_file`, `wave.a.jira_fetch` emits only `phase.end` with `{skipped: true, reason: "source_mode:paste"}` or `"source_mode:card_file"`, and A2 and A3 start straight away under `default/{ticket}`, using the payload from step 7's staging |
| Wave A each lane returns | `phase.end` with the lane's small outputs (e.g. jira-fetch → `{ac_count, has_parent}`); `phase.error` (`terminal: true`) if the lane returned `ok: false`. A2 also emits `artifact` (kind: `decision_log`, path: `{DECISION_PATH}`) when it added rows. A3 writes `{CARD_ROOT}/settings.local.json` as JSON (`BASE_BRANCH`, `DIFF_BRANCH`) and emits no artifact |
| Wave A join complete | `phase.end` `wave.a.join` |
| Wave B dispatch | `phase.start` × 2 for `wave.b.branch_manager`, `wave.b.spec_author` |
| Wave B each lane returns | `phase.end` per lane; `phase.error` (`terminal: true`) on failure. Under `--docs-only`, `wave.b.branch_manager` emits only `phase.end` with `{skipped: true, reason: "docs-only"}` |
| Wave B join complete | `phase.end` `wave.b.join` + `artifact` (kind: `spec`, path: `{SPEC_PATH}`) after the staged spec moves into place |
| Wave C dispatch | `phase.start` `wave.c.implementer`. Under `--docs-only`, only `phase.end` with `{skipped: true, reason: "docs-only"}` |
| Wave C `implementer` returns | `phase.end` `wave.c.implementer` with `{acs_completed, acs_deferred, files_written_count}`; `phase.error` (`terminal: true`) on failure — implementation is critical-path |
| Wave C join complete | `phase.end` `wave.c.join` + `artifact` events for `manifest_json` and `manifest_md` |
| Drift check dispatch (after the Wave C join, before Wave E — or before Wave F under `--docs-only`; never skipped) | `phase.start` `phase.drift.check` |
| Drift check returns | `phase.end` `phase.drift.check` with `{drift, high, medium, low, passes_compared_count, blocked}` + `artifact` (kind: `drift_report`, path: `{DRIFT_PATH}`) when the report was written; `phase.error` (`terminal: false`) when the agent returned `ok: false`. With `--drift-block` and `blocked: true`, also `phase.error` (`terminal: true`, `error_code: DRIFT_BLOCKED`) after the `phase.end` — the run halts to Phase 8 |
| Wave E dispatch (solo — always fires) | `phase.start` `wave.e.code_review.r1`; after a retry, `wave.e.retry_{n}.r1`. Under `--docs-only`, only `phase.end` `wave.e.code_review` with `{skipped: true, reason: "docs-only"}` |
| Wave E solo returns | `phase.end` `wave.e.code_review.r1` with `{findings: {high, medium, low}}`; `phase.error` (`terminal: false`) on failure — forces escalation |
| Wave E escalation dispatch (only if r1 flagged high/medium or failed) | `phase.start` × 2: `wave.e.code_review.r2`, `wave.e.code_review.r3` (retry rounds: `wave.e.retry_{n}.r{2\|3}`) |
| Wave E escalation returns | `phase.end` per reviewer with `{findings: {high, medium, low}}`; `phase.error` (`terminal: false`) per failed reviewer |
| Wave E consolidation | `phase.end` `wave.e.consolidate` with `{escalated, escalation_degenerated, votes: {"3": N, "2": N, "1": N}, majority_high_medium, reviewers_returned}`. At the **final** review round (budget exhausted, no majority high/medium finding, or early halt), `outcome` (kind: `code_review`, with `retries_used`, `retries_halted_no_op`) and `artifact` (kind: `code_review`, path: `{REVIEW_PATH}`) |
| Wave E retry fix | `phase.start` / `phase.end` `wave.e.retry_{n}.implementer` with `{mode: "targeted", acs_completed, acs_deferred, files_written_count}`; when the fix is committed, `phase.start` / `phase.end` `wave.e.retry_{n}.commit` with `{committed: true\|false, repo: "codebase"}` |
| Wave E retry halt | `phase.end` `wave.e.retry_{n}.halted` with `{reason: "fix_no_op", implicated_files: [...], files_written: [...]}` — the fix touched no file the confirmed findings implicated, so the loop exits without another review round |
| Wave F dispatch | `phase.start` for each lane that runs: `wave.f.spec_commit` (separate spec repo only), `wave.f.code_commit` |
| Wave F each lane returns | `phase.end` per lane with `{committed: true\|false, repo: "spec"\|"codebase", includes_spec: true\|false}`. `NOTHING_TO_COMMIT` and `NOT_A_GIT_REPO` are `phase.end` with `committed: false`, not `phase.error`. Skipped lanes: `wave.f.spec_commit` with `{skipped: true, reason: "same-repo"}` (the spec files ride in F2) or `reason: "no-git"`; `wave.f.code_commit` with `reason: "docs-only"` when the spec root is outside the consuming repo |
| Wave F join complete | `phase.end` `wave.f.join` |
| Wave D dispatch (solo — always fires) | `phase.start` `wave.d.ac_verify.r1`; after a retry, `wave.d.retry_{n}.r1`. Under `--docs-only`, only `phase.end` `wave.d.ac_verify` with `{skipped: true, reason: "docs-only"}` |
| Wave D solo returns | `phase.end` `wave.d.ac_verify.r1` with `{pass, partial, fail, manual}`; `phase.error` (`terminal: false`) on failure — forces escalation |
| Wave D escalation dispatch (only if r1 reported partial/fail or failed) | `phase.start` × 2: `wave.d.ac_verify.r2`, `wave.d.ac_verify.r3` (retry rounds: `wave.d.retry_{n}.r{2\|3}`) |
| Wave D escalation returns | `phase.end` per verifier with `{pass, partial, fail, manual}`; `phase.error` (`terminal: false`) per failed verifier |
| Wave D consolidation | `phase.end` `wave.d.consolidate` with `{escalated, escalation_degenerated, pass, partial, fail, manual, verifiers_returned}`. At the **final** verify round, `outcome` (kind: `ac_verify`, with `retries_used`, `retries_halted_no_op`) and `artifact` (kind: `ac_checklist`, path: `{AC_PATH}`) |
| Wave D retry fix | `phase.start` / `phase.end` `wave.d.retry_{n}.implementer` with `{mode: "targeted", acs_completed, acs_deferred, files_written_count}`; when the fix is committed, `phase.start` / `phase.end` `wave.d.retry_{n}.commit` with `{committed: true\|false, repo: "codebase"}` |
| Wave D retry halt | `phase.end` `wave.d.retry_{n}.halted` with `{reason: "fix_no_op", implicated_files: [...], files_written: [...]}` |
| Wave G dispatch | `phase.start` `wave.g.test_planner` |
| Wave G returns | `phase.end` `wave.g.test_planner` with `{scenario_count, frontend_applicable}` + `artifact` events for `validation`, `frontend_test` and `spec_testing`; `phase.error` (`terminal: false`) on failure — the run continues and Wave H is skipped |
| Wave H dispatch | `phase.start` `wave.h.playwright_testing` (author mode). When skipped, only `phase.end` with `{skipped: true, reason: "docs-only\|no-ui\|no-spec-testing\|no-e2e-suite"}` |
| Wave H returns | `phase.end` `wave.h.playwright_testing` with `{mode: "author", specs_written_count, scenarios_covered_count, scenarios_skipped_count, patterns_file}` + `artifact` (kind: `playwright_spec`) per spec file; `phase.error` (`terminal: false`) on failure |
| Wave H commit | `phase.start` `wave.h.commit` → `phase.end` with `{committed: true\|false, repo: "codebase"}` (`NOTHING_TO_COMMIT` → `committed: false`). No events when Wave H wrote nothing |
| Phase 5c | `phase.start` `phase.5c.branch_publish` → `phase.end`. `artifact` (kind: `pull_request`) on a successful PR open; `phase.error` (`terminal: false`) on push/PR failure. Skipped (push off, `--docs-only`, nothing ahead of base) → only `phase.end` with `{skipped: true, reason}` |
| Phase 6 | `phase.start` `phase.6.jira_status` → `phase.end` with `{status, transitioned: true}`; `phase.error` (`terminal: false`, `error_code: transition_not_found` or the MCP error) on failure. Skipped (`--handoff` not passed, or `HANDOFF_JIRA_STATUS` unset) → only `phase.end` with `{skipped: true, reason: "no-handoff"\|"no-status-configured"}` |
| Phase 7 | `phase.start` `phase.7.handoff` → `phase.end` + `artifact` (kind: `handoff`, path: `{HANDOFF_PATH}`); `phase.error` (`terminal: false`) on failure. Without `--handoff`, only `phase.end` with `{skipped: true, reason: "no-handoff"}` |
| Phase 8 spec commit | `phase.start` `phase.8.spec_commit` → `phase.end` with `{committed: true\|false, repo: "spec"\|"codebase"}`; skipped (`no-git`) → only `phase.end` with `{skipped: true, reason}` |
| Phase 8 close | `phase.start` `phase.8.close_run_log` → `phase.end` + `artifact` (kind: `flow_log`, path: `{LOG_PATH}`). Then `run.end` — the last event of the run, always emitted, even on failure paths. Then the finalize step (`telemetry-schema.md` → "Where events go") — no event, since the telemetry file is what it writes |

### Subcommand runs

For `/flow:spec`, `/flow:code`, `/flow:review`,
`/flow:verify`, `/flow:test`, `/flow:fetch`, `/flow:brief`,
`/flow:decisions`, `/flow:playwright`, `/flow:drift` and `/flow:log` (also
reached as `/flow spec …` and `--log` through the run skill's
router): emit `run.start` with the matching `invocation`, one
`phase.start` / `phase.end` pair for the sub-agent invoked (phase ids in
`telemetry-schema.md` → "Phase ids"), then `run.end` with
`status: "success"` (or `failed` if the sub-agent returned `ok: false`),
then the finalize step. Subcommands never commit: the spec artifacts
they write stay uncommitted under `{CARD_ROOT}` until the developer
commits them or the next full pipeline run's commits pick them up.

- `/flow:code` reuses `wave.c.implementer` with `{mode:
  "full"|"targeted", acs_completed, acs_deferred, files_written_count}`,
  plus `artifact` events for `manifest_json` and `manifest_md`. No
  `wave.c.join`.
- `/flow:review` and `/flow:verify` use `wave.e.code_review.r1`
  and `wave.d.ac_verify.r1`, then one `outcome` (`retries_used: 0`).
- `/flow:playwright` reuses `wave.h.playwright_testing` with
  `{mode: "run", specs_written_count, passed, failed, skipped}`, plus an
  `artifact` (kind: `test_results`) for `{PLAYWRIGHT_RESULTS_PATH}`. Its
  author and run dispatches are **one** phase: a single `phase.start`
  before the author dispatch and a single `phase.end` whose `usage` sums
  both (`dispatches: 2`). Suffixed ids such as
  `wave.h.playwright_testing.author` are not canonical.
- `/flow:drift` reuses `phase.drift.check` with the same outputs,
  `blocked` included, and the `drift_report` artifact for `{DRIFT_PATH}`.
  It has no `--drift-block` halt: the command reports, it does not run a
  pipeline.
- `/flow:report` and `/flow:datapoints` emit nothing — the report
  is a read-only viewer over this data, and datapoints is a standalone
  codebase search.

**Dry-run (`--verify`) runs.** Emit `run.start` with
`invocation: "dry-run"`, then `run.end` with `status: "success"` at the
end of the trace, then the finalize step — the telemetry file is the
only thing a dry run writes. Do not emit `phase.start` / `phase.end` for
lanes the trace only *described*.

**Fields to emit on `run.end`.**

- `status` — `success` | `partial` | `failed` using the Phase 8 rubric.
- `phases_completed` — every `phase` value that emitted a `phase.end`
  this run, retry variants deduped to their base id (`wave.e.retry_1.r1`
  counts as `wave.e.code_review`).
- `terminal_phase` — the phase id that halted the run, or `null` on
  success/partial. Populate it on **every** failure path. **Do not skip.**
- `retry_budget_used` — total fix cycles across Waves E and D.
- `duration_ms` — `run.end.ts` minus `run.start.ts` in milliseconds,
  computed by the shell from the two timestamps.
- `usage_totals` — `{tokens, tool_uses, agent_duration_ms, dispatches,
  dispatches_missing_usage}` summed over this run's `usage` objects.
