# Flow hooks

Two Claude Code hooks back Flow's guardrails. They ship inside the
plugin and are registered by `hooks.json`, so they switch on when the
`flow` plugin is enabled and update with it. There is nothing to copy
into `~/.claude/hooks/` and nothing to add to `settings.json`.

| Script | Event | What it does |
|---|---|---|
| `flow-path-guard.py` | `PreToolUse` on `Write`, `Edit`, `NotebookEdit`, `Bash`, `Read` | Blocks writes into `~/.claude/plugins/cache/**`, writes into any `.spec/` folder outside the resolved spec root, `.flow/` files other than the team files (`config.md`, `memory.md`, `{board-key}-standards.md`, `{board-key}-playwright-patterns.md`), and `Read` calls on per-user memory. Bash commands only get a warning, since parsing paths out of shell text is heuristic. |
| `flow-telemetry-recover.py` | `Stop` | Moves telemetry buffers older than 30 minutes — left by runs that crashed before their final step — from `~/.claude/flow/telemetry-buffer/` into `{repo}/.flow/.telemetry/`, via `scripts/telemetry_flush.py recover`. No git, no network. A fast no-op when the buffer folder is empty. |

The recovery hook is deliberately not registered on `SubagentStop`.
Flow's sub-agents are plugin agents, and recovering after every lane
would race the live run. The 30-minute age check keeps it off the buffer
of a run that spans several turns, such as a `/flow:brief` interview.

## Spec root

Both hooks resolve the spec root the way the skills do:

1. the `FLOW_SPEC_ROOT` environment variable;
2. `FLOW_SPEC_ROOT` in `{project}/.flow/config.md`;
3. `{project}/.flow/.spec`.

`{project}` is the git root of `CLAUDE_PROJECT_DIR`. Relative values are
joined with it; `~` is expanded. The shared resolver is
`scripts/flow_paths.py`.

## Requirements

Both hooks run in exec form, as `python` plus the script path from
`${CLAUDE_PLUGIN_ROOT}`, so they need Python 3.9+ on `PATH` under the
name `python`. Standard library only; Windows, macOS and Linux. On
systems that only ship `python3` (many macOS and Linux installs), add a
`python` alias or install your distribution's `python-is-python3`
package.

## Environment variables

| Var | Default | What it does |
|---|---|---|
| `FLOW_SPEC_ROOT` | unset (config, then `.flow/.spec`) | Overrides the spec root for the guard and for telemetry placement. |
| `FLOW_PATH_GUARD_ENABLED` | `true` | Set to `false` to switch the guard off. |
| `FLOW_TELEMETRY_ENABLED` | `true` | Set to `false` to stop writing telemetry; leftover buffers are discarded. |
| `FLOW_HOOK_LOG` | `~/.claude/flow/hooks.log` | Where hook decisions are logged. |

## Troubleshooting

- **`python` not found** — install Python 3.9+ and put it on `PATH` as
  `python`.
- **A spec write is blocked** — the reason names the resolved spec root.
  Either the path is wrong, or this repo keeps its specs elsewhere: set
  `FLOW_SPEC_ROOT` in `.flow/config.md` or the environment.
- **Telemetry from a crashed run is missing** — look for a buffer under
  `~/.claude/flow/telemetry-buffer/` and `telemetry:` lines in
  `hooks.log`. Buffers younger than 30 minutes are left alone on purpose.
- **Hooks don't seem to fire** — check `/plugin` for load errors on the
  `flow` plugin, and run `/reload-plugins` after updating.
