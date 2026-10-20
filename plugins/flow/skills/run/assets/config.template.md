# Flow — project config

Per-repo settings for the `flow` plugin's pipeline. Copy this file to
`.flow/config.md` at your repo root and fill in your team's values, or
just run `/flow:run` on any ticket and answer the first-run prompts —
Flow writes this file for you.

Commit it. Everyone on the repo then inherits the same board and branch
conventions, and new hires get them by cloning.

Only include keys you actually want to override. Anything omitted falls
through to the plugin's shipped defaults, so a short file is a healthy file.

```
JIRA_DEFAULT_BOARD=
BASE_BRANCH=main
BRANCH_FORMAT={type}/{ticket-key}-{slug}
```

## Worked example

A team on the `PROJ` board that keeps its specs in a separate folder and
moves cards to "Ready for QA" on `--handoff`:

```
JIRA_DEFAULT_BOARD=PROJ
BASE_BRANCH=main
FLOW_SPEC_ROOT=~/code/my-specs/.spec
HANDOFF_JIRA_STATUS=Ready for QA
```

## The rest of the knobs

Everything documented in the plugin's `skills/run/references/credentials.md`
is valid here too, and project config wins over shipped defaults:
`FLOW_SPEC_ROOT`, `DEFAULT_PASS_MODE`, `AUTO_PUSH`, `PR_MODE`,
`PLAYWRIGHT_E2E_DIR`, `HANDOFF_JIRA_STATUS`, `FLOW_MEMORY_ENABLED`,
`FLOW_MEMORY_CHAR_BUDGET` and `FLOW_TELEMETRY_ENABLED`.

Other team files live next to this one. `{board-key}` is the ticket's
board prefix, uppercase:

- `.flow/{board-key}-standards.md` — the team's coding standards, e.g.
  `.flow/PROJ-standards.md`. They describe your codebase and change on
  your cadence, so they live here rather than in the plugin.
- `.flow/{board-key}-playwright-patterns.md` — the e2e pattern library
  Wave H and `/flow:playwright` follow, e.g.
  `.flow/PROJ-playwright-patterns.md`. Starter: the plugin's
  `skills/run/assets/playwright-patterns.template.md`.
- `.flow/memory.md` — optional team memory: curated codebase facts
  every run loads at pre-flight. Starter: the plugin's
  `skills/run/assets/memory.template.md`. Changes go through PR; the
  pipeline reads it but never writes it.
