# CLAUDE.md — Flow plugin repo

Guardrails for anyone (AI agent or human) editing the Flow plugin
source in this repo. If you're just *using* Flow against your own
codebase, this file doesn't apply to you — read the README instead.

---

## 1. Where edits go

- **Plugin source** lives at `plugins/flow/`: skills in `skills/`,
  sub-agents in `agents/`, hooks in `hooks/`, helper scripts in
  `scripts/`. Never edit `~/.claude/plugins/cache/**` — Claude Code
  replaces that directory on every plugin update and edits vanish
  silently.
- **Rules about Flow's behavior** belong in this repo, where they
  ship with the plugin. Don't put them in per-user memory
  (`~/.claude/projects/*/memory/`, `~/.claude/CLAUDE.md`) — another
  user would never see them.

## 2. Version bumps (semver, informal)

- **Patch** — prose cleanup, no behavior change.
- **Minor** — new phase, new flag, new default that keeps prior
  invocations working.
- **Major** — breaking rename or removal (phase renamed, config key
  retired, flag semantics changed).

Bump `version:` in `plugins/flow/skills/run/SKILL.md` **and**
`"version"` in `plugins/flow/.claude-plugin/plugin.json` to the same
string before merging to `main`. Claude Code only ships a release to
users when the `plugin.json` version changes.

Sub-agent versions live at the top of each `plugins/flow/agents/*.md`
file (`> **Version:** X.Y.Z`). Bump one when that agent's contract
changes.

## 3. Cross-file synchronization

Some changes touch several files and must land in the same commit:

- **`references/emission-map.md` ↔ `references/telemetry-schema.md`** —
  every event id, field and outcome in the emission map (and the
  pipeline and subcommand files it points at) must exist in the schema,
  and every schema entry must be emitted somewhere. The report script
  (`scripts/flow_report.py`) reads the schema's events, so keep it
  in step too.
- **Config keys ↔ `references/credentials.md`** — every key mentioned in
  a skill, an agent or a reference must be documented in
  credentials.md.
- **Agent flags ↔ invocation snippets** — if an agent gains, renames or
  drops a flag, update every invocation block that dispatches it (in
  `references/pipeline-*.md`, `references/dry-run.md` and
  `skills/*/SKILL.md`) and bump the agent's version line.

## 4. CHANGELOG required

Every plugin-affecting commit adds an entry to
`plugins/flow/CHANGELOG.md` under a
`## vX.Y.Z — YYYY-MM-DD — headline` heading, using `### Added`,
`### Changed`, `### Removed`, `### Fixed` and `### Follow-ups` as
needed.

## 5. Telemetry stays local

Flow writes telemetry only to the consuming repo's `.flow/.telemetry/`
folder and never commits or pushes it. Don't add any code path that sends telemetry or
spec artifacts to a remote. If the schema changes, bump
`schema_version` rather than rewriting the meaning of an existing
field, so old run files still read correctly.

## 6. Testing before merge

- Every `SKILL.md` frontmatter parses (a malformed skill fails silently
  on reload).
- `claude plugin validate .` passes from the repo root.
- `python -m py_compile` passes for every file in `hooks/` and
  `scripts/`.
- Run `/flow:run {ticket} --verify` against a real ticket in a test
  repo and read the trace for stale references — leftover phase names,
  drifted config keys, flags that no longer exist.
- The CHANGELOG entry exists.

## 7. Branches

Work on a `vX.Y.Z-{slug}` branch and open a PR, even for a one-line
`SKILL.md` tweak — the emission map or a sub-agent may depend on that
line. Docs-only fixes (typos, README) can go straight to `main`.

## 8. Style

`plugins/flow/skills/run/references/writing-style.md` is the style
guide for what Flow's sub-agents produce (atomic bullets, tight
one-liners for records, sentence-case headings). The plugin source
itself — this file, the skills, credentials.md, the CHANGELOG — uses
prose paragraphs, lowercase-first bullets in explanatory lists and code
blocks for anything runnable.
