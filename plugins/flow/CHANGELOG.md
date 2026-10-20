# Changelog

All notable changes to Flow are recorded here. Versions follow
informal semver: patch for prose cleanup, minor for new phases, flags or
defaults that keep prior invocations working, major for breaking renames
or removals.

## v2.1.0 — 2026-10-19 — drift check

### Added

- `flow:drift-checker` sub-agent (1.0.0). It compares every row of the card's
  `decision-log.md` with the latest pass's spec, manifest and diff, and each
  pass with the next. It reports findings for unsourced scope, decisions the
  spec dropped or contradicts, missing validation, security, consequence and
  stale-test gaps, each with a severity of high, medium or low.
- Drift check phase after Wave C, before Wave E (before Wave F under
  `--docs-only`). Output is `drift.md` in the latest pass folder, an artifact
  of kind `drift_report`, and phase id `phase.drift.check`.
- `--drift-block` flag on `/flow:run`. Off by default. When on, a high-severity
  finding halts the run before Wave E with `DRIFT_BLOCKED`.
- `/flow:drift {ticket} [pass … | --all] [--block]`, which runs the same check
  on demand without halting the run.

### Changed

- The run skill opens with a notice that `/flow:run` is for demonstration and
  educational use: slow, token-heavy, and it takes the human out of the loop.
  The subcommands are the recommended path for real work.
- Run skill 2.1.0 and plugin 2.1.0. The telemetry schema stays at `"2"`
  because the additions (one phase id, one artifact kind) are additive.
- The report script (`flow_report.py`) does not yet count `phase.drift.check`
  or `drift_report`; they appear in the raw telemetry only.


### Changed

- Plugin renamed from `specflow` to `flow`. Every `/specflow:*` command is
  now `/flow:*` (`/flow:run {ticket}`, `/flow:spec`, `/flow:verify`, and so
  on), and sub-agents dispatch as `flow:{name}` instead of `specflow:{name}`.
- Per-repo config and team files live in `.flow/` (`config.md`, board
  standards, memory, Playwright patterns). Spec output moves from `.spec/`
  at the repo root to `.flow/.spec/`, and the `FLOW_SPEC_ROOT` default
  follows it.
- Each ticket's spec folder is typed: `{SPEC_ROOT}/{features,bugfixes,
  hotfixes,default}/{ticket}/`. The type comes from the Jira issue type
  (Bug → `bugfixes`; Incident, Hotfix, or a `hotfix`/`urgent` label →
  `hotfixes`; anything else → `features`). Pasted cards, card files and
  runs that never fetch go under `default/`, and a later fetch that
  resolves the type moves the folder out of `default/`.
- The card folder is created once Wave A's jira-fetch (A1) returns the
  card. A2 (decision-logger) now runs after A1, with the card payload, and
  A3 (settings) runs alongside A2. Pre-card `/flow:decisions` writes to
  `default/`.
- A3 writes `{CARD_ROOT}/settings.local.json` as JSON (`BASE_BRANCH`,
  `DIFF_BRANCH`). It replaces the `.claude/settings.local.json` write, so
  nothing under `.claude/` is touched, and the file is not gitignored.
  Nothing reads it yet.
- Telemetry stays local in `{repo}/.flow/.telemetry/`, a fixed folder beside
  the spec root rather than inside it, with its own `.gitignore`. The flush
  and report scripts read and write that folder whatever `FLOW_SPEC_ROOT` is.
- User-level directory `~/.claude/specflow/` is now `~/.claude/flow/` (hook
  log and telemetry buffer).
- Environment variables renamed from `SPECFLOW_*` to `FLOW_*`, for example
  `FLOW_SPEC_ROOT`, `FLOW_TELEMETRY_ENABLED` and `FLOW_HOOK_LOG`.
- Telemetry field `specflow_version` is now `flow_version`, and
  `schema_version` is bumped to `"2"`. The report script still reads
  schema `"1"` run files through the old key.
- Hook and helper scripts renamed: `flow-path-guard.py`,
  `flow-telemetry-recover.py`, `flow_paths.py`, `flow_report.py`.
- Repository, homepage and marketplace references point at
  `christie304/flow`.
- Sub-agent versions bumped to 2.0.0 because their dispatch names changed.

### Removed

- The `specflow` name, the `specflow:` namespace and the `SPECFLOW_*`
  variables. None of them are read any more, and there is no alias.

### Follow-ups

- Existing repos need a one-time move: rename `.specflow/` to `.flow/`,
  move a root `.spec/` into `.flow/.spec/` (or keep it by setting
  `FLOW_SPEC_ROOT=.spec`), move each ticket folder into its typed folder
  (`.flow/.spec/features/{ticket}/` for stories and tasks), rename any
  `SPECFLOW_*` variables in shell profiles or CI, move `{SPEC_ROOT}/telemetry/`
  to `.flow/.telemetry/` (or delete the old folder, since it is local-only),
  and reinstall the plugin from the `flow` marketplace entry.

## v1.0.0 — 2026-10-15 — first public release

### Added

- `/specflow:run {ticket}`, the full pipeline: pre-flight, card fetch and
  decision log, branch and spec, implementation, escalated code review,
  local commits, escalated acceptance-criteria verification, test
  documents, Playwright authoring, an opt-in code push and PR, an
  optional dev→QA handoff, and a closing run log.
- Subcommands as their own skills: `brief`, `spec`, `code`, `review`,
  `verify`, `fetch`, `test`, `playwright`, `decisions`, `datapoints`,
  `log` and `report`.
- `/specflow:report`, which reads local telemetry and renders a summary
  in the terminal, or a self-contained HTML dashboard with `--html`.
- `/specflow:datapoints`, a language-agnostic catalog of every code path
  that writes to named database tables, with a reverse lookup by file.
- Ten plugin sub-agents dispatched as `specflow:{name}`: `jira-fetch`,
  `decision-logger`, `branch-manager`, `spec-author`, `implementer`,
  `code-reviewer`, `ac-verifier`, `test-planner`, `playwright-testing`
  and `jira-commenter`.
- Guardrail hooks: a path guard that keeps spec artifacts under the spec
  root and blocks edits to the plugin cache, and a `Stop` hook that
  recovers telemetry from runs that crashed.
- A local spec root (`.spec` at the consuming repo root by default,
  configurable with `SPECFLOW_SPEC_ROOT`) for specs, decision logs and
  telemetry. Specflow never pushes spec artifacts or telemetry anywhere;
  only the code feature branch is pushed, and only when you opt in with
  `--push` or `AUTO_PUSH=true`.
