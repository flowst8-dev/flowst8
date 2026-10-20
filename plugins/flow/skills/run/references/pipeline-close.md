<!-- Part of the run skill. Read on demand from SKILL.md.
     {SKILL_DIR} = the run skill's base directory; {PLUGIN_ROOT} = the
     flow plugin root. SKILL.md defines both. -->

# Full pipeline, part 3 — Waves G and H, Phases 5c to 8

### Wave G — Test plan generation

Wave G is a single lane — `test-planner` — writing under `{PASS_ROOT}`.
It always runs, including under `--docs-only`, and produces **three**
documents from the spec and the diff.

#### test-planner

Dispatch the `flow:test-planner` agent (Agent tool, `subagent_type: "flow:test-planner"`) with this prompt:
```
test-planner \
  --spec {SPEC_PATH} \
  --diff-range origin/{diff-branch}...HEAD \
  --branch {branch_name} \
  --ticket {ticket} \
  --write {VALIDATION_PATH} \
  --frontend-guide {FRONTEND_TEST_PATH} \
  --spec-testing-guide {SPEC_TESTING_PATH}
```

Three documents from the same spec and diff:

- `{VALIDATION_PATH}` — the developer/QA test plan (priorities,
  conditional-logic table, automate-vs-manual scenarios). Written for
  someone who will build or run the tests.
- `{FRONTEND_TEST_PATH}` — plain-language click-by-click front-end test
  guide for the person checking the change in the running app. No code,
  file paths, SQL or TS-ids.
- `{SPEC_TESTING_PATH}` — AC-mapped test index: one row per AC with its
  test scenario (input/action → expected outcome), automate/manual/UI
  classification, and a link to the row in `validation.md` or
  `front-end-testing.md` that covers it. This is the spec-shaped view of
  testing (`validation.md` is the coverage-shaped view). Every AC in the
  spec has exactly one row.

If the change has no user-facing surface (pure back-end or data work
with nothing to click), the test-planner writes a short
`front-end-testing.md` saying so and pointing the tester at the relevant
validation scenarios instead — no fabricated UI steps.

### Wave G join

Wait for `test-planner` to return. Emit `artifact` events for the three
documents. A failure is logged as `phase.error` (`terminal: false`): the
run continues so Phase 5c and Phase 8 still run, but Wave H is skipped
(`reason: "no-spec-testing"`) because it consumes `{SPEC_TESTING_PATH}`,
and the Phase 8 summary reports the missing test documents.

Keep `frontend_applicable` from the test-planner payload — Wave H reads
it as the "no UI to test" signal.

### Wave H — Playwright authoring

A single lane — `playwright-testing` in **author mode** — dispatched
after the Wave G join. It turns the AC-mapped scenarios in
`{SPEC_TESTING_PATH}` (the `TS-###` ids), the front-end guide and the
diff into runnable Playwright spec files inside the consuming codebase's
**existing** e2e suite, composing against that suite's fixtures, page
objects and test data. It never runs the tests, never opens a browser
and never reads or logs credentials — the unattended pipeline authors;
running them is the developer's call via `/flow:playwright {ticket}`.

**Skip conditions** — emit `phase.end` `wave.h.playwright_testing` with
`{skipped: true, reason: …}` and log the reason to `{LOG_PATH}`:

- `docs-only` — the run is `--docs-only`; there are no code changes to test.
- `no-ui` — test-planner reported `frontend_applicable: false`.
- `no-spec-testing` — Wave G failed, so there is no scenario index.
- `no-e2e-suite` — no `playwright.config.{js,ts,mjs,cjs}` under
  `PLAYWRIGHT_E2E_DIR` in the consuming repo.

**E2E suite resolution.** Resolve `PLAYWRIGHT_E2E_DIR` (per-run
`--e2e-dir`, else env `FLOW_PLAYWRIGHT_E2E_DIR`, else
`.flow/config.md`, else the shipped default `e2e`). Relative values
are joined with the consuming repo root. Search that folder and its
immediate children for `playwright.config.*`; the folder holding the
config is `E2E_SUITE`. More than one match → prefer the one whose path
contains the board key (case-insensitive); still ambiguous → skip with
`no-e2e-suite` and list the candidates in `{LOG_PATH}` so the developer
can pin `PLAYWRIGHT_E2E_DIR`.

**Pattern library.** `PATTERNS_PATH =
{consuming repo}/.flow/{board-key}-playwright-patterns.md` (e.g.
`.flow/PROJ-playwright-patterns.md`). If it exists, pass it to the
agent — it carries the team's page-object inventory, fixtures, test-data
helpers, tagging rules, gotchas and reuse hierarchy. If absent, omit the
flag; the agent falls back to generic Playwright authoring and the
payload reports `patterns_file: false`. A team starts one from
`{SKILL_DIR}/assets/playwright-patterns.template.md` and commits it to
the consuming repo.

Dispatch the `flow:playwright-testing` agent (Agent tool, `subagent_type: "flow:playwright-testing"`) with this prompt:
```
playwright-testing \
  --mode author \
  --spec {SPEC_PATH} \
  --spec-testing {SPEC_TESTING_PATH} \
  --frontend-guide {FRONTEND_TEST_PATH} \
  --diff-range origin/{diff-branch}...HEAD \
  --repo {consuming codebase repo} \
  --e2e-suite {E2E_SUITE} \
  --patterns {PATTERNS_PATH}          # omit when the file is absent
  --ticket {ticket}
```

On `ok: true`: capture `specs_written`, `scenarios_covered`,
`scenarios_skipped`, `existing_overlap` and `open_questions`. Append
`open_questions` (data the agent could not resolve and guarded with
`test.skip()`) and `existing_overlap` to `{LOG_PATH}` — in author mode
the agent never prompts, so these are the developer's to-do list.

### Wave H join

A failure is non-fatal: log `phase.error` (`terminal: false`) and
continue; the Wave G documents still ship. On success, emit `artifact`
(kind: `playwright_spec`) per file written, then **commit the new spec
and test-data files on the codebase feature branch** so Phase 5c
publishes them with the implementation:

```
branch-manager \
  --repo {consuming codebase repo} \
  --commit "{ticket}: Playwright specs"
```

`NOTHING_TO_COMMIT` is not an error. This commit is what makes the
generated tests part of the PR — Wave F ran before the specs existed. In
`same-repo` mode it also carries the Wave G documents. Emit
`phase.start` / `phase.end` `wave.h.commit` around it; when Wave H wrote
nothing, skip the commit and emit nothing.

### Phase 5c — Publish the code branch (opt-in)

Phase 5c is the only place Flow pushes anything, and it pushes only
the consuming repo's code feature branch. Spec artifacts are never
pushed — in `same-repo` mode they reach the remote inside the feature
branch's commits; in `separate` mode they stay in your spec repo until
you push it yourself. Telemetry is never committed or pushed.

Phase 5c runs only when code was implemented this pass and the
consuming-repo feature branch has commits ahead of `origin/{base}`.
Resolve the behavior:

- **Push?** `AUTO_PUSH` (stored, ships `false`) unless overridden per
  run by `--push` or `--no-push`. A fresh install with no per-run flag
  does **not** push.
- **PR?** `--pr {off|draft|ready}` if passed, else stored `PR_MODE`
  (ships `draft`). Only takes effect when push is enabled.

Skip the phase — noted in `{LOG_PATH}` — under any of:

- Push is disabled (default: `AUTO_PUSH=false` and no `--push`).
- `--docs-only` was passed.
- The feature branch has **no commits ahead of `origin/{base}`** (a
  spec-only or investigation pass).

In each case the local commits are preserved — publication is simply
left to the developer.

Otherwise delegate to `branch-manager` (the only sub-agent that runs git):
```
branch-manager \
  --repo {consuming codebase repo} \
  --push \
  --open-pr {draft|ready}          # omit if PR mode is off
  --base {base-branch} \
  --ticket {ticket} \
  --title "{ticket}: {card title}" \
  --pr-body-file {a temp file containing the PR body}
```

`--repo` here is always the consuming codebase. If branch-manager
returns `push: "REFUSED_SPEC_REPO"` (`ok: true`) it was asked to push a
repo other than the one the session runs in — a guard against pushing a
spec repo. Log it, skip the PR, and continue; it is not a failure.

Suggested PR body — links tie the code back to the paper trail:
```markdown
## {ticket}: {card title}

**Jira**: {jira-url}
**Spec**: {SPEC_PATH}
**Run id**: {run_id} (local telemetry: `{repo}/.flow/.telemetry/{YYYY-MM}/{run_id}__…jsonl`)
**Flow pass**: {PASS_DIR}
**Playwright specs**: {N files under {E2E_SUITE}, or "—"}

{One-paragraph summary from the spec's problem statement and goals.}

### Acceptance criteria
{AC pass/partial/fail/manual tallies from Wave D}

🤖 Generated with [Claude Code](https://claude.com/claude-code) via Flow
```

In `same-repo` mode write `**Spec**` as the repo-relative path so the
link works in the PR; in `separate` mode the spec is not in the PR's
repo, so give the path for reference only.

Push and PR are **best-effort**: a `git push` or `gh pr create` failure
(auth, no remote, `gh` not installed) appends the error to `{LOG_PATH}`
and the pipeline continues to Phase 6 — local files and commits are
never lost to a publish problem. Capture the PR URL for the Phase 8
summary and the handoff packet.

### Phase 6 — Move the Jira card (skipped unless `--handoff`)

If `HANDOFF_JIRA_STATUS` is unset (the shipped default), skip with a
note in `{LOG_PATH}` — `Jira status: unchanged (HANDOFF_JIRA_STATUS not
set)` — and emit `phase.end` `phase.6.jira_status` with
`{skipped: true, reason: "no-status-configured"}`.

Otherwise, through the Atlassian MCP (`cloudId` from the pre-flight
probe):

1. `getTransitionsForJiraIssue` for `{ticket}`.
2. Pick the transition whose target status name — or, failing that, its
   own name — equals `HANDOFF_JIRA_STATUS`, case-insensitively.
3. Found → `transitionJiraIssue` with that transition id. Already in
   that status → nothing to do; record success.
4. Not found → warn in `{LOG_PATH}` and chat, listing the available
   transitions, and emit `phase.error` (`terminal: false`,
   `error_code: transition_not_found`).

Append the result to `{LOG_PATH}`. Continue to Phase 7 regardless — a
failed transition never blocks the handoff packet.

### Phase 7 — Dev→QA handoff packet (skipped unless `--handoff`)

Write `{HANDOFF_PATH}` (= `{CARD_ROOT}/{PASS_DIR}/handoff.md`) — a
self-contained packet a tester can work from without reading the rest of
the pass folder. Build it only from what this run produced; never
invent steps or results. Follow
`{SKILL_DIR}/references/writing-style.md` (atomic bullets, sentence-case
headings).

```markdown
# Dev → QA handoff — {ticket}: {card title}

**Jira**: {jira-url} · **Status**: {new status, or "unchanged"}
**Branch**: {branch_name} · **PR**: {pr-url, or "— (not pushed)"}
**Pass**: {PASS_DIR} · **Run**: {run_id} · **Date**: {YYYY-MM-DD}

## What changed
- {one bullet per completed AC, in plain language}
- Files: {paths from manifest.files_written}

## How to test
1. {setup and steps distilled from front-end-testing.md — or, for a
   change with no UI, the key scenarios from validation.md}
- Full guides: [front-end-testing.md](front-end-testing.md),
  [spec-testing.md](spec-testing.md), [validation.md](validation.md)
- Automated: {N Playwright specs under {E2E_SUITE}, run with
  `/flow:playwright {ticket}`; or "none"}

## Acceptance criteria
| AC | Verdict | Notes |
|----|---------|-------|
| {n} | {pass / partial / fail / manual} | {one line from acceptance-criteria.md} |

## Known gaps
- {deferred ACs, ACs still partial/fail, majority code-review findings
  left open, Playwright open questions, decision-log coverage gaps — or
  "None known"}

## Links
- [Spec](spec.md) · [Decision log](../decision-log.md) ·
  [Code review](code-review.md) · [AC checklist](acceptance-criteria.md)
```

Emit `artifact` (kind: `handoff`, path: `{HANDOFF_PATH}`) and tell the
developer where the packet is. If a source document is missing (Wave G
failed, say), write the section as `— not available ({reason})` rather
than skipping the packet.

### Phase 8 — Close the run log

Append a final summary block to `{LOG_PATH}`:

```
---

**Overall status**: ✅ Success | ⚠️ Partial | ❌ Failed
**Completed**: {YYYY-MM-DD HH:MM}
**Branch**: {branch_name}
**Pushed**: {`origin/{branch}`, or "— (push disabled / --docs-only / no commits)"}
**Pull request**: {pr-url, or "— (PR mode off / nothing to publish)"}
**Spec**: {SPEC_PATH}
**Spec commits**: {"on the feature branch" | "{spec repo path} (local, not pushed)" | "— (spec root not in a git repo)"}
**Jira status**: {new status, "unchanged", or "— (no --handoff)"}
**Handoff packet**: {HANDOFF_PATH or "—"}
**AC results**: {N pass}, {N partial}, {N fail}, {N manual}, or `— (docs-only)`
**Test scenarios**: {N from test-planner summary}
**Playwright specs**: {N spec files → {E2E_SUITE}, or "— (docs-only / no UI / no e2e suite)"}
**Retry budget used**: {N of total}
```

Status rules:

- **Success** — every phase returned `ok: true` and every AC is `pass`
  or `manual`.
- **Partial** — any AC remained `fail` or `partial` after retries, but no
  phase errored.
- **Failed** — any phase halted with `ok: false`.

Also update `{LATEST_PATH}` with `{PASS_DIR}` so later passes and
`/flow:log` know the latest pass.

**Closing spec commit.** Files written after Wave F — the Wave G
documents in `separate` mode, `handoff.md`, the closed run log and
`latest.txt` — are committed once more by the Wave F spec lane, as phase
`phase.8.spec_commit`, following the same `SPEC_COMMIT_MODE` table:

```
branch-manager \
  --repo {SPEC_ROOT | consuming codebase repo} \
  --commit "{ticket}: close pass {PASS_DIR}"
```

`separate` → `--repo {SPEC_ROOT}`; `same-repo` → the consuming repo, on
the feature branch (or the current branch under `--docs-only`); `none` →
skip (`reason: "no-git"`). Never `--push`. In `same-repo` mode this
commit lands after Phase 5c's push, so it goes up with the developer's
next push — say so in chat when a PR was opened. `NOTHING_TO_COMMIT` and
`NOT_A_GIT_REPO` are not errors.

**Emit `run.end`** — always, even on partial or failed paths; it is what
distinguishes a completed run from a crashed one. Populate:

- `status` — `success` / `partial` / `failed` per the rubric above.
- `phases_completed` — the deduped set of base phase ids that returned
  `phase.end` this run.
- `terminal_phase` — the phase that halted the run, or `null`.
- `retry_budget_used`.
- `duration_ms` — `run.end.ts` − `run.start.ts` in milliseconds.
- `usage_totals`.

Append it to the per-run buffer with the JSON-safe emitter from
pre-flight step 6. If the append fails, log to `{LOG_PATH}` and continue.

**Finalize telemetry** — the true last act, on every path (success,
partial, failed, `--docs-only`, push off):

```bash
python "{PLUGIN_ROOT}/scripts/telemetry_flush.py" flush \
  --run-id {run_id}
```

It moves the buffer to
`{repo}/.flow/.telemetry/{YYYY-MM}/{run_id}__{user}__{command}__{ticket}.jsonl`
(creating the folder's `.gitignore` on first write) and prints one JSON
line. No commit, no push. Full contract:
`{SKILL_DIR}/references/telemetry-schema.md` → "Where events go". If it
reports an error, mention it in one line; the plugin's `Stop` hook
recovers the buffer later. Subcommands and `--verify` dry runs end with
the same call. Finish by pointing the developer at `/flow:report`
when they want the numbers.
