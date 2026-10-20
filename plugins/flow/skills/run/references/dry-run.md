<!-- Part of the run skill. Read on demand from SKILL.md.
     {SKILL_DIR} = the run skill's base directory; {PLUGIN_ROOT} = the
     flow plugin root. SKILL.md defines both. -->

## `--verify` mode

When `--verify` is passed:

1. Run pre-flight config resolution
2. Dispatch the `flow:jira-fetch` agent and fetch the card for real (read-only)
3. Resolve parent story from `card.parent_card`
4. Compute branch name from format + parent story
5. Print the full dry-run trace. **Output style rules:**
   - Do **not** narrate telemetry in the CONFIG block or the trace body. No
     `Telemetry` line, no repo-path callouts, no "first real run will create
     `{repo}/.flow/.telemetry/`" warnings. Telemetry is plumbing —
     the user has already opted in via config, and every mechanic is
     best-effort per this skill's own rules. Silence is the default.
   - Do **not** append a "flags for the real run" or "caveats" section after
     the trace box unless the pipeline would fail (missing card, MCP down,
     etc.). One-off observations (wrong branch checked out, PR already exists)
     belong inline in the ⚠️ lines of the affected phase, not as a post-script
     lecture.
   - Match the fenced trace template below exactly — no extra CONFIG lines
     beyond what it lists.
   - **Show fully-resolved values** in the trace, not template
     placeholders. `Branch format` shows the resolved branch name (with
     the template shown parenthetically for reference). Every path is
     absolute — never a relative `.flow/.spec/…` string. Every `{token}` is expanded to its actual value
     before rendering.

```
╔══ /flow:run {ticket} --verify ══════════════════════════════════╗

  CONFIG
  ├─ Board            {board-prefix}
  ├─ Standards        {absolute path to .flow/{board-key}-standards.md}  ✅ / ⚠️ will be created
  ├─ Base branch      {resolved}  (source: flag | stored | default)
  ├─ Branch format    {resolved branch name}
  │                   (template: {resolved format string}, resolved above)
  ├─ Spec root        {absolute SPEC_ROOT}  (source: env | config | default)
  │                   commits: {feature branch (same repo) | {spec repo} local only | none — not a git repo}
  ├─ Pass mode        {iterate (new pass) | overwrite (reuse latest)}
  ├─ Pass folder      {absolute PASS_ROOT}   (existing latest: {p0N | none})
  ├─ Memory           {absolute path to .flow/memory.md}  {✅ {N} chars ({P}% of budget) | — not present | ⚠ over budget}
  ├─ Jira MCP         {✅ reachable | ⚠ not connected}
  ├─ Argument         {argument-as-typed} → {ticket_key_normalized | invalid}
  ├─ Source mode      {jira | paste | card_file}  ({one-line rationale})
  │                   {if card_file: path + format (json/freeform)}
  └─ Config gaps      none ✅ / {list any gaps}

  ── DRY RUN ──────────────────────────────────────────────────────

  Wave A — A1, then A2 and A3
  ├─ A1 jira-fetch  {or: A1 no-op (source_mode: paste|card_file)}
  │   └─ {jira mode:}  Fetched:  {ticket} "{title}"
  │                    Parent:  {parent-ticket} "{parent-title}"  (or: no parent — card IS the story)
  │                    ACs:     {N}
  │                    Labels:  {labels}
  │                    Card folder: {absolute CARD_ROOT}  (type: {features | bugfixes | hotfixes})
  │   └─ {paste/card_file mode:} Staged from step 7: {N} ACs, title "{title}"
  │                              (jira-fetch not called)
  │                              Card folder: {absolute CARD_ROOT}  (type: default)
  ├─ A2 decision-logger  {or: SKIPPED (--decisions not passed)}
  │   └─ Decision log:  {absolute DECISION_PATH}
  │                     {would create blank | exists, N rows}
  │                     {if --decisions passed: would append from {source label}}
  └─ A3 settings.local.json
      └─ Would write:  {absolute CARD_ROOT}/settings.local.json
                       {"BASE_BRANCH": "{base}", "DIFF_BRANCH": "{diff}"}

  Wave A join — proceed

  Wave B — post jira-fetch (parallel)
  ├─ B1 branch-manager  {or: SKIPPED (docs-only) — no branch created}
  │   └─ Would create:  {resolved-branch-name}
  │                     (from: {base-branch})
  │                     (named from: {parent-ticket or card-ticket})
  └─ B2 spec-author
      └─ Would stage:   {absolute TEMP_SPEC_PATH}
                        (moved to {absolute SPEC_PATH} at Wave B join)

  Wave B join — move staged spec, sync decision-log header if needed

  Wave C — post spec
  └─ implementer (full)
      └─ Would implement: {N} ACs from spec

  Wave C join — render manifest.md from manifest.json, then proceed

  Drift check — report-only (--drift-block: halts on a high finding)
  └─ drift-checker
      └─ Would compare:  {PREV_PASS},{PASS_DIR} against {DECISION_PATH}
                         (diff vs {DIFF_BRANCH} skipped under --docs-only)
                         → {absolute DRIFT_PATH}

  Wave E — code review (3 parallel reviewers + majority-vote consolidation)
  └─ Would dispatch:  3 parallel code-reviewer runs against files from manifest
                      (retry budget: {N}; retry trigger: 2/3+ high/medium)
                      → {absolute REVIEW_PATH}  (findings tagged 1/3, 2/3, 3/3)

  Wave F — commit, local only
  ├─ F1 spec:  {separate: would commit {SPEC_ROOT} → "{ticket}: spec pass {PASS_DIR}" (never pushed)
  │             | same-repo: SKIPPED — spec files ride in F2 | none: SKIPPED — not a git repo}
  └─ F2 code:  would commit {codebase} → "{ticket}: {card title}"
               {same-repo: + spec files under CARD_ROOT}  (skipped when nothing to commit)

  Wave D — ac-verifier (3 parallel verifiers + majority-vote consolidation)
  └─ Would verify: {N} ACs against diff origin/{diff-branch}...HEAD via 3 verifiers
                   Consolidation: majority-conservative on disagreement
                   Decision-log cross-check: advisory only
                   Retry: shared budget with Wave E; each targeted fix re-committed via F2
                   → {absolute AC_PATH}  (verdicts tagged with vote distribution)

  Wave G — test generation
  └─ test-planner → {absolute VALIDATION_PATH}       (QA/dev test plan)
                    {absolute FRONTEND_TEST_PATH}     (human front-end test steps)
                    {absolute SPEC_TESTING_PATH}      (AC-mapped test index, TS-### ids)

  Wave H — Playwright authoring      (author mode; execute later with /flow:playwright {ticket})
  ├─ E2E suite:    {absolute folder holding playwright.config.* under PLAYWRIGHT_E2E_DIR}  ✅ / ⚠ none found → skipped
  ├─ Patterns:     {absolute .flow/{board-key}-playwright-patterns.md}  ✅ / — none, generic authoring
  ├─ Would write:  {E2E_SUITE}/{tests folder per patterns}/{ticket}-{slug}.spec.{js|ts}   (one per TS-### scenario)
  └─ Would commit: {codebase} → "{ticket}: Playwright specs"
                   (skipped on docs-only or when the change has no UI)

  Phase 5c — publish branch    (opt-in: --push or AUTO_PUSH=true; ships OFF)
  ├─ Would push:   {branch_name} → app-repo origin/{branch_name}  (-u)
  └─ Would open:   {PR_MODE} PR into {base-branch}  (title "{ticket}: {card title}")
                   (skipped when push is disabled, --docs-only was passed,
                    or no commits ahead of origin/{base-branch})

  Phase 6 — Jira status             (skipped unless --handoff)
  └─ Would move: {ticket} → "{HANDOFF_JIRA_STATUS}"
                 {or: SKIPPED — HANDOFF_JIRA_STATUS not set}

  Phase 7 — handoff packet (dev→qa) (skipped unless --handoff)
  └─ Would write: {absolute HANDOFF_PATH}

  Phase 8 — close
  ├─ Would close: {absolute LOG_PATH}, update latest.txt
  └─ Would commit: closing spec commit (same rules as F1/F2, never pushed)

  ── Nothing was written. Run /flow:run {ticket} to execute. ────
╚══════════════════════════════════════════════════════════════════╝
```

6. Emit `run.end` (`status: "success"`, `terminal_phase: null`,
   `phases_completed: []`, `duration_ms` from the run.start timestamp).
   Even a dry run is a data point — dashboards need to distinguish "no
   full runs" from "no invocations at all." The dry run's `run.start`
   carries `invocation: "dry-run"`.
7. Finalize telemetry — `telemetry_flush.py flush` as in
   `{SKILL_DIR}/references/telemetry-schema.md` → "Where events go".
   That one local file is the only thing a dry run writes.
8. Stop. Write nothing else.

**Combining `--docs-only` with `--verify`.** The trace continues to show
every phase in full for readability, but Wave B.B1 (branch-manager),
Wave C, Wave E, Wave D, Wave F.F2 (unless it carries same-repo spec
files), Wave H (playwright-testing), Phase 5c code push, Phase 6 and
Phase 7 would read `SKIPPED (docs-only)` in a real run.
Interpret the trace's "Would…" statements as unconditional; the flags
in the CONFIG block decide what actually executes.
