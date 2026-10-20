---
name: playwright
description: Flow subcommand. Authors or refreshes a ticket's Playwright specs in the consuming codebase's e2e suite, asks you for any missing test data, runs them, and writes test-plan-results.md beside the spec. The only place Flow runs browser tests. Run as /flow:playwright {ticket} [TS-###].
argument-hint: "{ticket} [TS-###]"
disable-model-invocation: true
---

# /flow:playwright — author, run, record

Arguments: `$ARGUMENTS` — the ticket and an optional `TS-###` filter.

Runs `playwright-testing` against the latest existing pass — the
generate-and-execute loop for a developer at the keyboard, and the only
place Flow executes browser tests. The full pipeline only authors
(Wave H). The agent cannot talk to the developer, so this skill does the
asking between an author pass and the run.

**Paths.** `${CLAUDE_PLUGIN_ROOT}` is the flow plugin root — the flow
reference files call it `{PLUGIN_ROOT}` — and
`${CLAUDE_PLUGIN_ROOT}/skills/run` is the run skill directory they
call `{SKILL_DIR}`. Honour
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/context-boundaries.md`.

**1. Pre-flight** in subcommand mode per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/preflight.md`, with
`invocation: "playwright"`. `PASS_DIR = p{HIGHEST}`. If
`{SPEC_TESTING_PATH}` does not exist, stop with:
`⚠️  No spec-testing.md for {ticket} in {PASS_DIR} — run /flow:test {ticket} (or the full pipeline) first.`

**2. Resolve the suite and patterns** exactly as Wave H does in
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/pipeline-close.md`
(`PLAYWRIGHT_E2E_DIR` → `E2E_SUITE`;
`{consuming repo}/.flow/{board-key}-playwright-patterns.md` →
`PATTERNS_PATH`).
No suite → stop, print the folders searched and how to pin
`PLAYWRIGHT_E2E_DIR` in `.flow/config.md` or with `--e2e-dir`.

**3. Author.** Emit `phase.start` `wave.h.playwright_testing` (agent
`playwright-testing`) — the only `phase.start` of this command. The
author dispatch, the test-data questions and the run dispatch are one
phase: do not emit a `phase.end` between them, and never invent a
suffixed id such as `wave.h.playwright_testing.author`. Then dispatch
the `flow:playwright-testing` agent (Agent tool,
`subagent_type: "flow:playwright-testing"`) with the block below as the prompt,
every `{token}` resolved to an absolute value. Its final message is
its JSON payload.

```
playwright-testing \
  --mode author \
  --spec {SPEC_PATH} \
  --spec-testing {SPEC_TESTING_PATH} \
  --frontend-guide {FRONTEND_TEST_PATH} \
  --diff-range origin/{diff-branch}...HEAD \
  --repo {consuming codebase repo} \
  --e2e-suite {E2E_SUITE} \
  --patterns {PATTERNS_PATH}     # omit when the file is absent
  --ticket {ticket} \
  --scenario {TS-###}            # only when a filter was given
```

It reuses spec files it already wrote for the ticket.

**4. Collect test data.** For each entry in the payload's
`missing_test_data`, ask the developer once, showing its `key`,
`scenario` and `hint`. A skipped answer stays blank and its test stays
guarded with `test.skip()`. Never ask for credentials — the suite loads
its own from its environment file, and Flow never reads them.

**5. Run.** Dispatch `flow:playwright-testing` again with the same
flags, `--mode run`, `--results {PLAYWRIGHT_RESULTS_PATH}`, and
`--test-data {JSON of the answers}` when there are any. The agent
writes the answers into the ticket's `test-data.json`, executes
`npx playwright test` from `E2E_SUITE`, and writes
`{PLAYWRIGHT_RESULTS_PATH}` with pass / fail / skip counts and per-test
detail, redacting any credential that leaks into output. Failing tests
are results, not a failure of this command.

**6. Nothing is committed.** `{PLAYWRIGHT_RESULTS_PATH}` stays
uncommitted under `{CARD_ROOT}`, and the spec files written into the
codebase stay uncommitted in its working tree — outside the full
pipeline, committing code and spec artifacts is the developer's call.

**7. Emit** the single `phase.end` `wave.h.playwright_testing` with
`{mode: "run", specs_written_count, passed, failed, skipped}` — its
`usage` sums both dispatches — and an `artifact` (kind: `test_results`,
`phase: wave.h.playwright_testing`) for `{PLAYWRIGHT_RESULTS_PATH}`, then
`run.end` per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/emission-map.md`, then move
the run's telemetry buffer into the local telemetry file per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/telemetry-schema.md` →
"Where events go".

**8. Show** the totals and the results path in chat, plus any
`open_questions` and `existing_overlap` the agent returned.
