# Config — resolution and prompting

Config is two-tier, and the split matters:

- **Shipped defaults** (this file) travel with the plugin. They are
  deliberately board-agnostic — no Jira board, no team-specific ids.
  Treat this file as **read-only**: the plugin is installed into a
  versioned cache that Claude Code replaces on every update, so anything
  written here is lost at the next release.
- **Project config** (`.flow/config.md` at the consuming repo's root)
  holds everything team-specific. It is committed, so a team sets its
  board and branch conventions once and every developer on that repo
  inherits them — a new hire gets them by cloning. This is the only file
  Flow ever writes config back into.

Per-run overrides come from inline flags and environment variables.

Nothing in either file is a secret — board keys, paths and branch names
are all safe to commit. If Flow ever needs a real credential, it
belongs in the environment, not in either of these files.

---

## Shipped defaults

> Flow reads this section on every run, **after** `.flow/config.md`
> in the consuming repo. Anything a team needs to change belongs there,
> not here. `JIRA_DEFAULT_BOARD` has no sensible default: Flow prompts
> for it on first run in a new repo and writes the answer to
> `.flow/config.md`. `HANDOFF_JIRA_STATUS` ships empty, which turns
> the `--handoff` Jira transition off.

```
BASE_BRANCH=main
BRANCH_FORMAT={type}/{ticket-key}-{slug}
JIRA_DEFAULT_BOARD=
DEFAULT_PASS_MODE=iterate
FLOW_SPEC_ROOT=.flow/.spec
FLOW_MEMORY_ENABLED=true
FLOW_MEMORY_CHAR_BUDGET=4000
AUTO_PUSH=false
PR_MODE=draft
PLAYWRIGHT_E2E_DIR=e2e
FLOW_TELEMETRY_ENABLED=true
HANDOFF_JIRA_STATUS=
```

### Branches

`BASE_BRANCH` is the branch new feature branches are created from and
diffed against. Keep it a **bare branch name** (`main`) — every consumer
prepends `origin/` itself (branch-manager creates via
`git checkout -b {branch} origin/{BASE_BRANCH}`; AC verification and the
test planner diff against `origin/{BASE_BRANCH}...HEAD`). Do **not** set
it to `origin/main` — that would produce `origin/origin/main`.

`DIFF_BRANCH` is the base of the diff that Waves D and G read. It is not
a stored key: it comes from `--diff` or `FLOW_DIFF_BRANCH`, and
otherwise equals `BASE_BRANCH`.

`BRANCH_FORMAT` controls feature-branch names; its tokens are listed in
the first-run prompt below and defined by the `branch-manager` agent.

### Spec root — `FLOW_SPEC_ROOT`

`FLOW_SPEC_ROOT` is where every spec artifact lives — the folder the
docs call `{SPEC_ROOT}`. Set it in `.flow/config.md`, or as an
environment variable of the same name; the environment variable wins.
The shipped default is `.flow/.spec` at the consuming repo root.

- **Relative** values are joined with the consuming repo root
  (`git rev-parse --show-toplevel`, or the current directory outside a
  repo). `.flow/.spec` → `~/code/my-app/.flow/.spec`.
- **Absolute** values (`/…`, `C:/…`) and `~/…` are used as given, after
  `~` expansion. Point it at a separate folder or repo to keep specs out
  of your application's history, e.g.
  `FLOW_SPEC_ROOT=~/code/my-specs/.spec`.

Layout under it:

```
{SPEC_ROOT}/
├── features/{ticket}/          ← {CARD_ROOT} (also bugfixes/, hotfixes/, default/)
│   ├── settings.local.json     (BASE_BRANCH, DIFF_BRANCH — written by A3)
│   ├── decision-log.md         (card-level, persists across passes)
│   ├── latest.txt
│   └── p01/, p02/, …           (one folder per pass)
└── reports/                    (/flow:report HTML dashboards, gitignored)

{repo}/.flow/
└── .telemetry/                 (local only, gitignored — see telemetry-schema.md)
```

**Flow never pushes spec artifacts.** It commits them locally, and
only in the full pipeline (Wave F and the Phase 8 closing commit):

- **Spec root inside the consuming repo** (the default) — spec files
  ride on the feature branch in the same commit as the code, so the PR
  carries the spec with the change.
- **Spec root inside a different git repo** — Flow commits there,
  on whatever branch that repo has checked out, and never pushes. Push
  it yourself when you want to share.
- **Spec root not inside any git repo** — no commit; the files are just
  written.

Subcommands (`/flow:spec`, `/flow:test`, …) never commit; what
they write stays uncommitted under `{CARD_ROOT}`.

The plugin's path-guard hook enforces the root: a write into any `.spec/`
folder that is not under the resolved `FLOW_SPEC_ROOT` is blocked.
The hook resolves it the same way (environment variable, then
`.flow/config.md` in the project, then `.flow/.spec`).

### Push and PR — `AUTO_PUSH`, `PR_MODE`

`AUTO_PUSH` and `PR_MODE` control the only thing Flow ever pushes:
the **code feature branch** of the consuming repo, at Phase 5c.

**`AUTO_PUSH` ships as `false`** — a fresh install never pushes without
the developer opting in. Opt in by setting `AUTO_PUSH=true` in
`.flow/config.md` (persistent) or by passing `--push` on one run.

When enabled, a run that produced code commits pushes the feature branch
(`git push -u origin {branch}`); a `--docs-only` run has nothing to push.
`PR_MODE` then governs the pull request into `BASE_BRANCH` (opened with
`gh`): `off` (push only), `draft`, or `ready`. Merging that PR is what
lands the work — Flow never pushes to `main`. Per-run overrides:
`--push` / `--no-push` and `--pr {off|draft|ready}`. Push and PR are
**best-effort** — a failure is logged and the pipeline continues; local
files and commits are never lost to a push problem.

`AUTO_PUSH` has nothing to do with spec artifacts (never pushed) or
telemetry (never committed or pushed).

### Passes — `DEFAULT_PASS_MODE`

`DEFAULT_PASS_MODE` sets the pass-folder behavior for a full-pipeline run
when neither `--iterate` nor `--overwrite` is passed. Ships as `iterate`
(every run lands in a new `p{NN}` folder, preserving prior passes). Set
it to `overwrite` if you'd rather re-runs reuse the latest pass in place.
A per-run flag always wins. See "Pass-index resolution" in
`references/preflight.md`.

### Playwright — `PLAYWRIGHT_E2E_DIR`

`PLAYWRIGHT_E2E_DIR` tells Wave H and `/flow:playwright` where the
consuming codebase keeps its Playwright e2e suite. Relative values are
joined with the consuming repo root; absolute values are used verbatim.
Flow searches that folder and its immediate children for a
`playwright.config.{js,ts,mjs,cjs}`; the folder holding the config is the
suite, so the shipped `e2e` finds a suite at `e2e/my-app-e2e/` without
any setting. Pin it in `.flow/config.md` when the codebase has more
than one suite or keeps it elsewhere; override per run with `--e2e-dir`
or the `FLOW_PLAYWRIGHT_E2E_DIR` environment variable. No suite found
→ Wave H skips with `no-e2e-suite` and `/flow:playwright` stops with
the folders it searched.

**Test credentials never enter Flow config.** The suite's own
environment file (gitignored, typically `.env` in the suite folder)
holds the test login; Flow runs `npx playwright test` from the suite
folder so the suite's config loads it, and `playwright-testing` neither
reads nor logs it. Any credential that leaks into run output is written
as `[redacted]`.

**Pattern library — a convention, not a key.** `playwright-testing`
reads `.flow/{board-key}-playwright-patterns.md` in the consuming
repo when it exists: the team's page-object inventory, fixtures,
test-data helpers, tagging, gotchas and reuse rules (e.g.
`.flow/PROJ-playwright-patterns.md`). It describes the team's e2e
suite, so it lives in the repo beside the suite — never inside the
plugin, never on one developer's machine. Start one from
`assets/playwright-patterns.template.md`. Missing file → generic
Playwright authoring.

### Team memory — `FLOW_MEMORY_ENABLED`, `FLOW_MEMORY_CHAR_BUDGET`

These govern team memory: `.flow/memory.md` at the consuming repo's
root, read once at pre-flight as a frozen snapshot, plus the episodic
recall step at the Wave A join. The budget (ships 4000 characters, about
1500 tokens) is a hard cap — pre-flight warns at 80% and truncates with a
loud warning above 100%. The pipeline **never writes** this file; it
changes only via PR in the consuming repo. Entry format, save/skip rules
and the injection-scan requirements are in
[`docs/memory-design.md`](https://github.com/christie304/flow/blob/main/docs/memory-design.md)
in the Flow repository (not part of the installed plugin). A starter
file ships at `assets/memory.template.md`. Set
`FLOW_MEMORY_ENABLED=false` to skip both the memory load and the
recall step.

### Telemetry — `FLOW_TELEMETRY_ENABLED`

`FLOW_TELEMETRY_ENABLED` controls the event stream Flow emits at
each phase boundary — full contract in `references/telemetry-schema.md`.
Events buffer at `~/.claude/flow/telemetry-buffer/{run_id}.jsonl`
during a run; the last act of every command moves the buffer to
`{repo}/.flow/.telemetry/{YYYY-MM}/{run_id}__{user}__{command}__{ticket}.jsonl`,
where `{user}` is a slug of `git config user.email`
(`jane.doe@example.com` → `jane-doe-example-com`). When Flow creates
the telemetry folder it adds a `.gitignore` (`*`, `!.gitignore`), so the
files stay local unless a team deletes it. Flow never commits or
pushes telemetry. Read it with `/flow:report`.

Set `FLOW_TELEMETRY_ENABLED=false` to emit nothing at all. Telemetry
failures never halt the pipeline.

### Handoff — `HANDOFF_JIRA_STATUS`

`HANDOFF_JIRA_STATUS` is the Jira status a `--handoff` run moves the card
to at Phase 6 — for example `Ready for QA`. Flow looks up the
issue's available transitions through the Atlassian MCP and takes the
one whose target status (or transition name) matches, case-insensitively.
Unset (the shipped default) → Phase 6 is skipped with a note; no match →
a warning listing the available transitions, and the run continues.
Phase 7 then writes the dev→QA packet to
`{CARD_ROOT}/{PASS_DIR}/handoff.md` either way.

### Hook switches (environment only)

The plugin's hooks read two more environment variables. They are not
`.flow/config.md` keys.

- `FLOW_PATH_GUARD_ENABLED` — `false` switches the path guard off.
  Default `true`.
- `FLOW_HOOK_LOG` — where the hooks and `telemetry_flush.py` log
  their decisions. Default `~/.claude/flow/hooks.log`.

**Contribution model.** Install the plugin through Claude Code. To
change Flow itself, fork
[christie304/flow](https://github.com/christie304/flow), make
the change, and open a PR. Using the plugin never requires a clone.

---

## Config resolution order

For each config value, Flow checks in this order:

1. Inline flag passed with the command (`--base`, `--diff`,
   `--branch-format`, `--e2e-dir`).
2. Environment variables: `FLOW_BASE_BRANCH`, `FLOW_DIFF_BRANCH`,
   `FLOW_PLAYWRIGHT_E2E_DIR`, `FLOW_TELEMETRY_ENABLED`,
   `FLOW_SPEC_ROOT`.
3. **Project config** — `.flow/config.md` at the root of the repo
   Flow is running against (same `KEY=VALUE` fenced-block format as
   this file). Locate the root via `git rev-parse --show-toplevel`, not
   the current directory, so Flow behaves the same from a
   subdirectory.
4. `## Shipped defaults` in this file.
5. **Interactive prompt** (last resort — only when everything above is
   empty).

Read the environment layer with a shell probe rather than assuming it is
empty — `$env:FLOW_BASE_BRANCH` in PowerShell, `${FLOW_BASE_BRANCH}`
in bash. Treat unset **and** empty as "not provided" and fall through; a
variable that exists but is blank never blanks out a working value.

Any value collected via prompt is written to `.flow/config.md` in the
consuming repo — creating the file and the `.flow/` directory if
needed — so it is never asked again and the rest of the team gets it on
their next pull. Never write config into this file; the plugin cache is
replaced on update.

Values from an environment variable or an inline flag are **not** written
back — they are deliberately per-session.

After creating `.flow/config.md`, tell the developer it is a new file
they should commit. Do not stage or commit it yourself.

---

## First-run prompt

Show when `.flow/config.md` is absent from the repo root, or when
`JIRA_DEFAULT_BOARD` resolves blank across every layer. Both mean
Flow has not been configured for this repo yet, which is exactly
when guessing is worst.

```
👋 Flow: first-time setup for this repo.

What is your team's base branch? (Leave blank for default: main)

  Base branch:

Default board prefix? (e.g. PROJ — lets you type /flow:run 123 instead of /flow:run PROJ-123)
Leave blank to skip:

  Default board:

Branch naming format? Controls how feature branch names are built.
Available tokens: {type}, {ticket-key}, {board-key}, {ticket-number}, {slug}
  {type} = bugfix | hotfix | feature (from the card's issue type)
  {ticket-key} = full key, case preserved (e.g. PROJ-123)
Note: branches are named from the parent story, not the sub-task.
Leave blank for default: {type}/{ticket-key}-{slug}
  (e.g. feature/PROJ-123-email-opt-in-checkbox)

  Branch format:

Where should spec artifacts live? A path relative to this repo, or an
absolute path such as ~/code/my-specs/.spec to keep specs in their own
folder or repo. Flow commits them locally and never pushes them.
Leave blank for default: .flow/.spec (inside this repo, committed with the code)

  Spec root:

Publish the CODE feature branch + PR when each /flow:run finishes?
Ships OFF — Flow commits locally and lets you decide when to push.
Answer y to have every full-pipeline run push the branch and open a
draft PR against your base branch (AUTO_PUSH=true). You can still
override per run with --push / --no-push.

  Publish code (y/N):
```

After the developer responds:

- Write the answered values to `.flow/config.md` at the repo root,
  creating the directory and file if absent. Write only the keys the
  developer answered — omitted keys fall through to shipped defaults, and
  pinning them now would freeze this repo against future default changes.
  - A spec-root answer writes `FLOW_SPEC_ROOT={answer}`.
  - A `y` answer to the publish question writes `AUTO_PUSH=true`; `n` or
    blank writes nothing.
- Confirm: *"✅ Saved to .flow/config.md — commit it and your team
  inherits it. You won't be asked again."*
- Continue immediately.

---

## Source-mode resolution

Flow decides where card content comes from at **pre-flight step 7**,
before Wave A dispatches. The result is `source_mode` ∈ `{jira, paste,
card_file}`, staged in memory so Wave A · A1 either calls `jira-fetch`
(jira mode) or no-ops with the pre-staged payload (paste / card_file).
See `references/preflight.md` → "Step 7" for the full contract.

| Atlassian MCP | CLI argument | Interactive session | Outcome |
|---------------|--------------|--------------------|---------|
| ✅ | valid ticket key | either | `source_mode: jira` — normal path. |
| ✅ | invalid / missing | interactive | Warn, prompt for paste → `source_mode: paste`. |
| ✅ | invalid / missing | non-interactive | Hard-fail (`bad_ticket_key`). |
| ❌ | valid | interactive | Warn LOUDLY (the developer probably wanted Jira), prompt for paste → `source_mode: paste`. |
| ❌ | valid | non-interactive | Hard-fail (`mcp_down`). |
| ❌ | invalid | interactive | Prompt for paste → `source_mode: paste`. |
| ❌ | invalid | non-interactive | Hard-fail (`mcp_down_and_bad_key`). |
| (any) | (any) with `--card-file` | either | `source_mode: card_file`, MCP not probed, argument not required beyond ticket-key detection. |

**Ticket key normalization** — the CLI argument is uppercased and, if
purely numeric with `JIRA_DEFAULT_BOARD` set, expanded to `{JIRA_DEFAULT_BOARD}-{n}`.
Regex after normalizing: `^[A-Z][A-Z0-9]+-\d+$`.

**MCP probe** — one cheap read (`getAccessibleAtlassianResources`),
10-second wall-clock budget. Project-level permissions are not verified
here — a 403 surfaces at the actual jira-fetch call.

### Atlassian MCP fallback

The interactive paste prompt, shown by pre-flight step 7 on the
interactive `source_mode: paste` routes:

```
⚠️  Flow: could not resolve card content via Atlassian MCP.
    MCP available: {yes/no}     Ticket key valid: {yes/no}

To configure Atlassian MCP, make sure these are allowed in
.claude/settings.local.json:

  { "permissions": { "allow": [
      "mcp__atlassian__getJiraIssue",
      "mcp__atlassian__searchJiraIssuesUsingJql"
  ] } }

Or run /mcp in an interactive Claude Code session to re-auth. To
continue this run without Jira, paste the card content below (title,
description, acceptance criteria; freeform markdown is fine). End with
Ctrl+D / empty line. Type SKIP to generate a minimal placeholder spec.
Ctrl+C to abort.

→ Paste card content now:
```

- Pasted → the freeform parser extracts `{title, description, ACs}`;
  `source_mode: paste`; log `Source: pasted (freeform, {N} chars)`;
  continue.
- SKIP → generate a minimal spec with `[NEEDS CLARIFICATION]`
  placeholders; `source_mode: paste`; log `Source: skipped`; continue.
- The non-interactive path never reaches this prompt — pre-flight
  hard-fails first with an actionable `error_code`.

### `--card-file` scripting path

The recommended path for CI, scripted runs and reproducible tests. The
extension picks the parser:

- `.json` — validated against the `jira-fetch` success-payload schema
  (`ticket`, `title`, `description`, `acceptance_criteria` required;
  `parent`, `parent_card`, `comments`, `labels`, `issue_type` optional
  with sensible defaults).
- `.md` / `.txt` / other — freeform, parsed by the same extractor the
  paste path uses.

With `--card-file`, MCP is not probed and the interactive prompt is not
shown. Ticket key detection: CLI argument first, then the file's own
`ticket` (JSON) or `# PROJ-123 …` header (freeform).

---

## Standards file resolution

`{board-key}` in file names is the ticket's board prefix as typed in the
ticket key, uppercase — `PROJ` for `PROJ-123`. (Branch names use their
own tokens, defined by `branch-manager`.)

- Derive the filename: `.flow/{board-key}-standards.md` **in the
  consuming repo** (root via `git rev-parse --show-toplevel`), beside
  `.flow/config.md` — e.g. `.flow/PROJ-standards.md`. Standards
  describe that repo's codebase and change on that team's cadence;
  inside the plugin they'd be erased by the next update.
- If it exists: load it and pass it to `spec-author`, `implementer` and
  `code-reviewer`.
- If missing: create it there from the template below, log
  `Standards: new file created at .flow/{board-key}-standards.md`,
  and tell the developer it's worth committing so the team shares one
  rule set.

Language- and framework-specific rules (SQL parameterization, currency
formatting helpers, logging conventions, …) belong in this file. Flow
ships no language rules of its own.

### Standards template

```markdown
# {board-key} coding standards

> Auto-created by Flow on first run for the {board-key} board.
> Fill in your team's coding standards so Flow enforces them during
> implementation and code review. Anything left blank is simply not
> enforced — Flow never invents rules you didn't write.

## Language and framework conventions

<!-- e.g. TypeScript: no `any` in exported types; React: function components only;
     SQL: always parameterized queries, never string concatenation -->

## Naming

<!-- variables, functions, files, DB objects -->

## Error handling and logging

<!-- required patterns, forbidden patterns -->

## Security

<!-- input validation, authz checks, secrets handling -->

## Testing expectations

<!-- what must be covered before a card leaves dev -->
```
