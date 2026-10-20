# Flow

> A spec-driven, multi-agent development pipeline for
> [Claude Code](https://claude.com/claude-code), inspired by the flow state.

Flow takes a Jira ticket from card to verified, reviewed, tested
implementation in one command. It writes a spec from the card,
implements it, reviews the code, scores every acceptance criterion
against the diff, writes QA documents and Playwright specs, and keeps an
append-only decision log next to the spec — all as plain files you can
read, diff and commit.

```
/flow:run PROJ-123
```

Built and maintained by [Christie Trent (@christie304)](https://github.com/christie304).

## Why spec-driven

An AI agent that codes straight from a ticket drifts: it fills gaps with
guesses and nobody can tell afterwards what it was aiming at. Flow
makes the spec the contract. Every later step — implementation, review,
verification, test planning — reads the same `spec.md`, and every
verdict cites `path:line` evidence against it. When a run is done you
have the code on a local feature branch and a pass folder that explains
it.

## How a run works

```
Pre-flight → Wave A → Wave B → Wave C → Drift → Wave E → Wave F → Wave D → Wave G → Wave H → Phase 5c → Phases 6–7 → Phase 8
             fetch    spec     code     drift    review   commit   verify   test     e2e      push (opt-in) handoff  close
```

- **Wave A** fetches the card through the Atlassian MCP (or takes a
  pasted card or `--card-file`) and, with `--decisions`, logs decisions
  from meeting notes or threads.
- **Wave B** creates the feature branch and writes `spec.md`.
- **Wave C** implements the spec and returns a manifest of files and
  acceptance criteria.
- **Drift check** compares the card's decision log with the latest pass
  and reports anything the log and the spec disagree on. It only reports
  unless you pass `--drift-block`, which halts the run on a high finding.
- **Wave E** reviews the change — one reviewer, escalating to three with
  a majority vote when it finds anything high or medium.
- **Wave F** commits locally.
- **Wave D** scores every acceptance criterion as pass, partial, fail or
  manual, again escalating to three verifiers on any doubt. Review and
  verification share a retry budget for targeted fixes.
- **Wave G** writes a QA plan, a click-by-click front-end guide and a
  scenario index with one row per criterion.
- **Wave H** authors Playwright specs into your existing e2e suite.
- **Phase 5c** pushes the branch and opens a PR — only if you opt in.
- **Phase 8** closes the run log and writes telemetry locally.

The plugin's own [README](plugins/flow/README.md) has the full
pipeline diagram, the sub-agent roster and every flag.

## Install

In Claude Code:

```
/plugin marketplace add christie304/flow
/plugin install flow@flow
```

Restart Claude Code, then pick up new versions later with
`/plugin marketplace update flow`.

### Requirements

- **Claude Code** with plugin support.
- **Python 3.9+** on `PATH` for the guardrail hooks and the report
  script (standard library only).
- **Git**, with `user.email` set — it names your telemetry files and
  signs each spec as author.
- **Atlassian MCP** (optional) so Flow can read Jira cards. Without
  it, paste the card when prompted or pass `--card-file`.
- **GitHub CLI** (optional) — `gh auth login` — for the opt-in push and
  PR step.
- **Playwright** (optional) — an existing e2e suite in your repo, found
  under `PLAYWRIGHT_E2E_DIR` (default `e2e`).

## Quick start

```
cd ~/code/my-app
/flow:run PROJ-123 --verify
```

The first run asks a few setup questions (base branch, default board
key, branch naming format, whether to push code) and writes
`.flow/config.md`. It also creates `.flow/PROJ-standards.md`
from a template — fill it with your codebase's conventions; the
implementer and the reviewers enforce it. Commit both so your team
shares one setup. `--verify` is a dry run: it prints the resolved
configuration and the plan without writing anything.

Then run it for real:

```
/flow:run PROJ-123
```

Results land in `.flow/.spec/features/PROJ-123/p01/`: `spec.md`,
`code-review.md`, `acceptance-criteria.md`, the three test documents and
`flow-log.md`. The code sits committed on a local feature branch
until you push it.

## Commands

| Command | What it does |
|---|---|
| `/flow:run {ticket}` | The full pipeline. Each run is a new pass folder (`p01`, `p02`, …). |
| `/flow:brief {ticket}` | Ticket-readiness interview before you start. |
| `/flow:spec {ticket}` | Regenerate the latest pass's spec. |
| `/flow:code {ticket}` | Implement the spec, or fix named criteria with `--target-acs`. |
| `/flow:review [ticket]` | One code review against your standards file. |
| `/flow:verify {ticket}` | Score the acceptance criteria against the diff. |
| `/flow:test {ticket}` | Regenerate the QA documents. |
| `/flow:playwright {ticket} [TS-###]` | Author and run Playwright specs for the ticket. |
| `/flow:drift {ticket}` | Report drift between the decision log and the passes' specs, manifests and diffs. `--block` marks high findings as blocking. |
| `/flow:decisions {ticket}` | Append decisions from notes, threads or comments to the decision log — works before the card exists. |
| `/flow:fetch {ticket}` | Print the card as JSON. |
| `/flow:datapoints --tables a,b` | List every code path that writes to the named tables (`--endpoint path` for the reverse). |
| `/flow:log [ticket]` | Show a run log, or list them all. |
| `/flow:report` | Summarize local telemetry — runs, outcomes, cost per agent, review and verification quality. `--html` writes a dashboard. |

## Where things land

Everything Flow writes is a file in your own repos. Nothing is sent
anywhere else.

- **Spec root** — `.flow/.spec/` at your repo root by default, or anywhere
  you point `FLOW_SPEC_ROOT` (for example a separate specs repo). Each
  ticket gets a folder under `features/`, `bugfixes/`, `hotfixes/` or
  `default/` with a `settings.local.json`, a `decision-log.md` and one
  folder per pass (each with `drift.md` once the drift check has run).
- **Telemetry** — `.flow/.telemetry/{YYYY-MM}/` in the repo, one JSONL file per
  run. It stays local: Flow drops a `.gitignore` there and never
  commits or pushes it. Set `FLOW_TELEMETRY_ENABLED=false` to turn
  it off.
- **Your codebase** — the feature branch, the implementation, Playwright
  specs, and the team files in `.flow/` (`config.md`,
  `{board}-standards.md`, `memory.md`,
  `{board}-playwright-patterns.md`).
- **Remotes** — the only push is your code feature branch, and only with
  `--push` or `AUTO_PUSH=true` (off by default).

## Contributing

Issues and pull requests are welcome at
[github.com/christie304/flow](https://github.com/christie304/flow).
Read [CLAUDE.md](CLAUDE.md) before changing the plugin — it covers
version bumps, the files that must change together and the checks to
run before merging.

## License

[MIT](LICENSE) © Christie Trent
