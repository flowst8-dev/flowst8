---
name: run
version: 2.1.0
description: >
  Flow is a multi-agent, spec-driven development pipeline. Takes a Jira
  ticket from card to verified, reviewed, tested implementation in one
  command, and keeps a card-level append-only decision log alongside the
  spec. Run as /flow:run {ticket} (e.g. /flow:run PROJ-123). Also
  triggers on /flow followed by a ticket key (/flow PROJ-123,
  /flow WEB-42) or a subcommand (/flow brief PROJ-123; direct
  forms: /flow:brief, /flow:spec, /flow:code, /flow:review,
  /flow:verify, /flow:test, /flow:playwright, /flow:decisions,
  /flow:drift, /flow:log, /flow:report, /flow:datapoints), and on phrases
  like "run flow on PROJ-123", "kick off flow for PROJ-123", "run
  the pipeline on this card", "brief me on PROJ-123", "log a decision for
  PROJ-123", "add this to the decision log", "update the decision log",
  "show flow stats", "which code writes to these tables", or any
  variant of "track this decision against {ticket}". Works with any Jira
  board prefix.
---

<!--
  Bumping guidance for `version:` above (semver, informal):
    - Patch — prose cleanup, no behavior change.
    - Minor — new phase, new flag, new default that keeps prior invocations working.
    - Major — breaking rename/removal (phase renamed, config key retired, flag semantics change).
  Emitted with every telemetry event as `flow_version`. Agent versions live
  at the top of each `agents/*.md` file in the plugin root (plus the
  `brief` skill); the version map is stamped at run.start. See
  `references/telemetry-schema.md`.
-->

# Flow — multi-agent spec-driven dev pipeline

> *From Jira card to spec to verified, reviewed, tested code — in one command.*

> **Heads up: `/flow:run` is for demonstration and educational purposes.**
> It is slow, token-heavy, and takes the human out of the loop: it walks
> the whole process in one go instead of pausing for you to review each
> step. It does work, but it is not the ideal fit for every codebase. For
> real work, the subcommands (`/flow:spec`, `/flow:code`, `/flow:review`,
> `/flow:verify`, `/flow:test`) let you check each stage before moving on.

**Paths used throughout the reference files:**

- `{SKILL_DIR}` = `${CLAUDE_SKILL_DIR}` — this skill's directory.
- `{PLUGIN_ROOT}` = `${CLAUDE_PLUGIN_ROOT}` — the flow plugin root,
  which holds `agents/`, `hooks/`, `scripts/` and the subcommand skills
  under `skills/`.
- `{SPEC_ROOT}` — where spec artifacts live: `FLOW_SPEC_ROOT`
  (env var or `.flow/config.md`), default `.flow/.spec` at the consuming
  repo root. `{CARD_ROOT}` = `{SPEC_ROOT}/{type}/{ticket}`, where `{type}`
  is `features`, `bugfixes`, `hotfixes` or `default`. Resolution
  rules: `{SKILL_DIR}/references/preflight.md` → "Spec path resolution".

This file is the router and the map. The procedure lives in
`{SKILL_DIR}/references/`, loaded only when the command needs it —
never load every reference at once.

## Data collected (telemetry)

Every Flow command writes a small JSONL event log **on your
machine**, one file per run at
`{repo}/.flow/.telemetry/{YYYY-MM}/{run_id}__{user}__{command}__{ticket}.jsonl`,
where `{user}` is a slug of `git config user.email`. Events buffer under
`~/.claude/flow/telemetry-buffer/{run_id}.jsonl` during the run; the
last act of every command moves the buffer into the telemetry folder
(`{PLUGIN_ROOT}/scripts/telemetry_flush.py`), and the plugin's `Stop`
hook recovers buffers from runs that crashed first. Each event carries a
run id, the phase, the Flow, schema and agent versions, the git
email, hostname and working directory; artifact events add file paths
and PR URLs; agent dispatches record the tokens, tool calls, time and
model the Agent tool reported. When Flow creates the telemetry
folder it adds a `.gitignore`, so the files stay out of git. **Flow
never commits, pushes or uploads telemetry.** Read it with
`/flow:report`. Set `FLOW_TELEMETRY_ENABLED=false` in
`.flow/config.md` (or the environment) to emit nothing. Full
contract: `{SKILL_DIR}/references/telemetry-schema.md`.

---

## Command router

Parse the command before doing anything else. Subcommands are their own
skills in this plugin; both spellings reach them — `/flow:brief
PROJ-123` directly, or `/flow brief PROJ-123` through this router. For
the router form, read the subcommand's `SKILL.md` and follow it with the
remaining arguments, then stop. Never run the full pipeline for a
subcommand.

| Command | Behavior |
|---------|----------|
| `/flow:run {ticket}` · `/flow {ticket}` | Full pipeline — see "Full pipeline" below |
| `/flow:run {ticket} --decisions {content}` | Full pipeline plus a decision-log update from `{content}` (text, file path, or Jira comment URL) in Wave A · A2 |
| `/flow:run {ticket} --verify` | Dry-run trace with real Jira data, nothing written → `{SKILL_DIR}/references/dry-run.md` |
| `/flow:run {ticket} --log` · `/flow --log` | Same as `/flow:log` → `{PLUGIN_ROOT}/skills/log/SKILL.md` |
| `/flow:decisions {ticket} [--decisions {content}]` | Decision log only; works **even before the card exists** (pre-card mode) → `{PLUGIN_ROOT}/skills/decisions/SKILL.md` |
| `/flow:drift {ticket} [pass … \| --all] [--block]` | Compare the decision log with the latest pass's spec, manifest and diff, and each pass with the next; report drift → `{PLUGIN_ROOT}/skills/drift/SKILL.md` |
| `/flow:brief {ticket}` | Ticket-readiness interview → `{PLUGIN_ROOT}/skills/brief/SKILL.md` |
| `/flow:spec {ticket}` | Regenerate the latest pass's spec → `{PLUGIN_ROOT}/skills/spec/SKILL.md` |
| `/flow:code {ticket} [--target-acs N,N]` | Implement the latest pass's spec (full), or fix named ACs (targeted); no review, verify or commit → `{PLUGIN_ROOT}/skills/code/SKILL.md` |
| `/flow:review [ticket]` | One code review, no escalation → `{PLUGIN_ROOT}/skills/review/SKILL.md` |
| `/flow:verify {ticket}` | One AC verification, no escalation → `{PLUGIN_ROOT}/skills/verify/SKILL.md` |
| `/flow:fetch {ticket}` | Card JSON → `{PLUGIN_ROOT}/skills/fetch/SKILL.md` |
| `/flow:test {ticket}` | Regenerate the three test documents → `{PLUGIN_ROOT}/skills/test/SKILL.md` |
| `/flow:playwright {ticket} [TS-###]` | Author, run and record the ticket's Playwright specs → `{PLUGIN_ROOT}/skills/playwright/SKILL.md` |
| `/flow:log [ticket] [p0N]` | Show a run log, or list them all → `{PLUGIN_ROOT}/skills/log/SKILL.md` |
| `/flow:report [ticket] [--since …] [--until …] [--user …] [--command …] [--html [path]] [--json]` | Summarize local telemetry: totals, per-command, per-ticket and per-agent tables, quality signals, recent runs; optional HTML dashboard → `{PLUGIN_ROOT}/skills/report/SKILL.md` |
| `/flow:datapoints --tables a,b \| --endpoint path` | Catalog the code paths that write to the named database tables (or the tables one endpoint writes) → `{PLUGIN_ROOT}/skills/datapoints/SKILL.md` |

Natural-language requests route the same way: "brief me on PROJ-123" →
brief; "log a decision for PROJ-123" or "add this to the decision log" →
decisions; "show flow stats" or "how are my flow runs going" →
report.

**Source-mode gate exemption.** `/flow:decisions` bypasses pre-flight
step 7 entirely: it supports pre-card mode and cannot be gated by MCP
availability or ticket-key validation. `/flow:report` and
`/flow:datapoints` skip pre-flight altogether. Every other command
goes through the source-mode gate.

---

## Agents

Every sub-agent is a **plugin agent** in `{PLUGIN_ROOT}/agents/`.
Dispatch one with the Agent tool and `subagent_type: "flow:{name}"`;
the prompt is the invocation block from the reference file with every
`{token}` resolved. An agent sees only that prompt, cannot talk to the
developer, and returns the JSON payload its file defines as its final
message. Lanes in the same wave go out as parallel Agent calls in one
message. Do not read the agent files into this conversation — dispatch
them.

| Agent | Wave / lane / phase |
|-------|---------------------|
| `flow:jira-fetch` | Wave A · A1; `/flow:fetch`, `/flow:brief`, `/flow:spec`, `--verify` |
| `flow:decision-logger` | Wave A · A2; `/flow:decisions` |
| `flow:branch-manager` | Wave B · B1 (create/checkout), Wave F commits, E/D retry commits, Wave H commit, Phase 5c push and PR, Phase 8 closing spec commit — the only git-touching agent |
| `flow:spec-author` | Wave B · B2; `/flow:spec` |
| `flow:implementer` | Wave C (full mode); Wave E and D retries (targeted mode); `/flow:code` |
| `flow:drift-checker` | Drift check after Wave C (full pipeline and `--docs-only`); `/flow:drift` |
| `flow:code-reviewer` | Wave E · r1, then r2 + r3 on escalation; `/flow:review` |
| `flow:ac-verifier` | Wave D · r1, then r2 + r3 on escalation; `/flow:verify` |
| `flow:test-planner` | Wave G; `/flow:test` |
| `flow:playwright-testing` | Wave H (author mode); `/flow:playwright` (author, then run) |
| `flow:jira-commenter` | `/flow:brief`, after the developer confirms a comment |

`brief` is a skill, not an agent: its interview needs the developer. The
orchestrator itself (this skill, in the main conversation) does
pre-flight, the A3 settings write, every join, episodic recall, the
escalation gates and majority-vote consolidation, the manifest.md
render, the Phase 6 Jira transition, the Phase 7 handoff packet and the
Phase 8 close.

**Pipeline sequence** — waves execute in this order, not alphabetically.
Wave letters are ids, not sequence markers:

```
Pre-flight → Wave A → Wave B → Wave C → Drift → Wave E → Wave F → Wave D → Wave G → Wave H → Phase 5c → Phase 6/7 → Phase 8
             fan-out  fan-out  impl    drift    review   commit   verify   test    e2e      push/PR    handoff    close
```

## Guardrail hooks

The plugin ships two hooks in `{PLUGIN_ROOT}/hooks/`, registered by
`hooks/hooks.json` and active whenever the plugin is enabled:
`flow-path-guard.py` (blocks writes into a `.spec/` folder outside
the resolved spec root, stray `.flow/` files, plugin-cache edits, and
reads of per-user memory) and `flow-telemetry-recover.py` (at `Stop`,
moves telemetry buffers left by crashed runs into
`{repo}/.flow/.telemetry/`; no git, no network). A
`[flow-path-guard] blocked …` message is the guard working — fix the
path, don't route around it.

## Context boundaries

Flow reads context from repo-scoped sources only — the plugin, the
consuming codebase, its `.flow/*` files, and `{SPEC_ROOT}` — never
from per-user state such as auto-memory or `~/.claude/CLAUDE.md`. Read
`{SKILL_DIR}/references/context-boundaries.md` at the start of every
command; it lists the allowed and forbidden sources and the output
style guide.

---

## Supported flags (full pipeline)

| Flag | Purpose | Default |
|------|---------|---------|
| `--base {branch}` | Base branch to create from and diff against | `BASE_BRANCH` → `main` |
| `--diff {branch}` | Base of the diff for AC verification | `BASE_BRANCH` → `main` |
| `--branch-format {fmt}` | Override branch naming format | stored config |
| `--e2e-dir {path}` | Override `PLAYWRIGHT_E2E_DIR` for this run — the folder (relative to the consuming repo root, or absolute) under which Wave H and `/flow:playwright` look for the e2e suite's `playwright.config.*`. | `PLAYWRIGHT_E2E_DIR` (ships `e2e`) |
| `--retry-budget {N}` | Max fix cycles across review + AC verify | `2` |
| `--push` / `--no-push` | Push (or don't) the consuming repo's code feature branch to `origin` at Phase 5c. Overrides stored `AUTO_PUSH`. Ships off, so a fresh install never pushes or opens a PR without you asking. This is the only push Flow ever makes — spec artifacts and telemetry are never pushed. | `AUTO_PUSH` (ships `false`) |
| `--pr {off\|draft\|ready}` | Whether and how to open a PR into the base after a code push (via `gh`). Only takes effect when code push is enabled. | stored `PR_MODE` (ships `draft`) |
| `--docs-only` | **Retrospective docs pass — leaves the consuming codebase's code untouched.** Use when the card's code already shipped and you're back-filling `spec.md` / `validation.md` / `front-end-testing.md` / `spec-testing.md`. Skips Wave B · B1 (no feature branch), Wave C, Wave E, Wave D, Wave H and the Phase 5c push. Wave B · B2 still writes the spec, Wave G still writes the three test documents, and spec commits follow the usual local rules (in `same-repo` mode they land on the currently checked-out branch). Incompatible with `--handoff`. | false |
| `--iterate` | **Default mode.** Create a new pass folder (`p02`, `p03`, …) for this run, preserving every prior pass. Pass index = highest existing `p*` under `{CARD_ROOT}` + 1 (or `p01` if none). See "Pass-index resolution". | true |
| `--overwrite` | Reuse the latest existing pass folder in place. Falls back to `p01` if no pass exists yet. Mutually exclusive with `--iterate`. | false |
| `--decisions {content}` | Add a decision-log update before Phase 1. `{content}` may be quoted text, a file path, or a Jira comment URL. With no value, prompt the developer to paste content. | unset |
| `--drift-block` | After the drift check, halt the run before Wave E when it finds a high-severity finding (the run goes to Phase 8 with `DRIFT_BLOCKED`). Without it the drift check only reports to `drift.md` and the run goes on. | false |
| `--card-file {path}` | Pre-canned card content, bypassing both Atlassian MCP and the interactive paste prompt. `.json` → the `jira-fetch` success-payload shape (`title`, `description`, `acceptance_criteria`, `ticket`, `parent`, `comments`); `.md`/`.txt`/anything else → freeform, parsed like pasted content (first `#` heading → title; body up to "Acceptance Criteria" → description; checkbox/numbered list → ACs). Sets `source_mode: card_file`. Useful for CI, scripted runs and reproducible testing. | unset |
| `--handoff` | After Phase 5c, move the Jira card to `HANDOFF_JIRA_STATUS` when that key is set (Phase 6), and write a dev→QA packet to `{CARD_ROOT}/{PASS_DIR}/handoff.md` (Phase 7). Off by default so iterative runs don't produce a packet every time. | false |
| `--verify` | Dry-run trace with real Jira data — nothing written but the local telemetry file | false |

---

## Full pipeline

Run these in order, reading each reference file when you reach it:

1. **Pre-flight** — `{SKILL_DIR}/references/preflight.md`, full mode
   (all steps, including the run log and the decision-log scaffold),
   plus its "Spec path resolution" and "Pass-index resolution".
2. **Telemetry map** — `{SKILL_DIR}/references/emission-map.md`. Keep
   it at hand: it says what to emit at every boundary below.
3. **Waves A → C** — `{SKILL_DIR}/references/pipeline-build.md`: wave
   execution semantics, fetch and decision log, branch and spec,
   implementation, the manifest render and the drift check.
4. **Waves E → F → D** — `{SKILL_DIR}/references/pipeline-quality.md`:
   escalated review, the local commit lanes, escalated AC verification,
   and the shared retry budget.
5. **Waves G → H, Phases 5c → 8** —
   `{SKILL_DIR}/references/pipeline-close.md`: test documents,
   Playwright authoring, the opt-in code push, the `--handoff` phases,
   and closing the run with the closing spec commit, `run.end` and the
   telemetry finalize step.

Phase 8 always runs, even after a failure, so the summary and `run.end`
land. Supporting files the steps point at: `credentials.md` (config
keys, resolution order, first-run prompt, MCP paste fallback),
`spec-template.md`, `decision-log-template.md`, `writing-style.md`,
`telemetry-schema.md`, and the templates under `{SKILL_DIR}/assets/`.

## `--verify` mode

Dry run: pre-flight config resolution, one real `flow:jira-fetch`,
then the full trace template in `{SKILL_DIR}/references/dry-run.md`.
Nothing is written except the `run.start` / `run.end` pair, which the
finalize step moves into the local telemetry folder.
