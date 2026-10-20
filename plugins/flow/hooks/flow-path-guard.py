"""
Flow path guard hook - PreToolUse.

Shipped with the flow plugin and registered by hooks/hooks.json, so it
is active whenever the plugin is enabled. No manual install.

Rules:
- Write / Edit / NotebookEdit into ~/.claude/plugins/cache/**  -> block.
  That directory is replaced on every plugin update; edits vanish.
- Write / Edit / NotebookEdit into a `.spec/` folder that is not under
  the resolved spec root                                    -> block.
- Write / Edit / NotebookEdit into a `.flow/` folder, unless the
  file is one of the repo-scoped team files (config.md, memory.md,
  {board-key}-standards.md, {board-key}-playwright-patterns.md) -> block.
- Read of per-user memory (~/.claude/projects/*/memory/,
  ~/.claude/CLAUDE.md, ~/.claude/memory/)                   -> block.
- Bash commands are heuristic to parse, so a violation there is only a
  stderr warning (exit 0), never a block.

Spec root, resolved the same way the skills do it:
  1. FLOW_SPEC_ROOT environment variable;
  2. FLOW_SPEC_ROOT in {CLAUDE_PROJECT_DIR}/.flow/config.md;
  3. {CLAUDE_PROJECT_DIR}/.flow/.spec.
Relative values are joined with the project's repo root; ~ is expanded.

Env:
  FLOW_SPEC_ROOT           spec root override (see above)
  FLOW_PATH_GUARD_ENABLED  'false' disables the guard (exit 0)
  FLOW_HOOK_LOG            decision log. Default ~/.claude/flow/hooks.log

Exit codes:
  0 - allow
  2 - block; stderr becomes a system reminder to Claude.

Python 3.9+, stdlib only. Any internal error allows the call: a guard bug
must never wedge a session.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

try:
    from flow_paths import is_within, project_dir, resolve_spec_root
except Exception:  # fall back to a minimal resolver
    def project_dir(explicit=None):
        return Path(explicit or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())

    def resolve_spec_root(repo_root=None, override=None):
        raw = os.environ.get("FLOW_SPEC_ROOT", "").strip() or ".flow/.spec"
        p = Path(os.path.expanduser(raw))
        if not p.is_absolute():
            p = Path(repo_root or project_dir()) / p
        return p.resolve()

    def is_within(candidate, root):
        a = os.path.normcase(os.path.abspath(str(candidate)))
        b = os.path.normcase(os.path.abspath(str(root)))
        try:
            return os.path.commonpath([a, b]) == b
        except ValueError:
            return False


WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
GUARDED_TOOLS = WRITE_TOOLS | {"Bash", "Read"}

SEP = r"[/\\]"
PLUGIN_CACHE = re.compile(SEP + r"\.claude" + SEP + "plugins" + SEP + "cache" + SEP, re.IGNORECASE)
SPEC_DIR = re.compile(r"(?:^|" + SEP + r")\.spec" + SEP, re.IGNORECASE)
FLOW_DIR = re.compile(r"(?:^|" + SEP + r")\.flow" + SEP, re.IGNORECASE)
FLOW_TEAM_FILE = re.compile(
    SEP + r"\.flow" + SEP
    + r"(?:config\.md|memory\.md|[a-z0-9]+-standards\.md|[a-z0-9]+-playwright-patterns\.md)$",
    re.IGNORECASE,
)
USER_MEMORY = [
    re.compile(SEP + r"\.claude" + SEP + "projects" + SEP + r"[^/\\]+" + SEP + "memory" + SEP, re.IGNORECASE),
    re.compile(SEP + r"\.claude" + SEP + r"CLAUDE\.md$", re.IGNORECASE),
    re.compile(SEP + r"\.claude" + SEP + "memory" + SEP, re.IGNORECASE),
]

BASH_PATH_TOKEN = re.compile(
    r"[A-Za-z]:[/\\][^\s'\"|<>&;]+"
    r"|~[/\\][^\s'\"|<>&;]+"
    r"|/[^\s'\"|<>&;]+"
    r"|\.{1,2}[/\\][^\s'\"|<>&;]+"
)


def log_line(msg):
    path = Path(os.environ.get("FLOW_HOOK_LOG", str(Path.home() / ".claude" / "flow" / "hooks.log")))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            fh.write(ts + " path-guard: " + msg + "\n")
    except Exception:
        pass


def absolute(raw, cwd):
    p = Path(os.path.expanduser(str(raw)))
    if not p.is_absolute():
        p = Path(cwd) / p
    return p


def classify(raw, tool, spec_root, cwd):
    """Return (verdict, reason); verdict is 'allow' or 'block'."""
    if not raw:
        return "allow", ""
    text = str(raw)

    if tool == "Read":
        if any(p.search(str(absolute(text, cwd))) for p in USER_MEMORY):
            return (
                "block",
                "path is per-user memory (~/.claude/projects/*/memory/, ~/.claude/CLAUDE.md "
                "or ~/.claude/memory/). Flow reads repo-scoped context only; a rule that "
                "should shape Flow belongs in the plugin or in the consuming repo's "
                ".flow/ files, where teammates see it. See the run skill's "
                "references/context-boundaries.md.",
            )
        return "allow", ""

    full = absolute(text, cwd)
    full_text = str(full)

    if PLUGIN_CACHE.search(full_text):
        return (
            "block",
            "path is inside ~/.claude/plugins/cache/, which is replaced on every plugin "
            "update - the edit would silently vanish. Edit the plugin's source repo instead.",
        )

    if is_within(full, spec_root):
        return "allow", ""

    if SPEC_DIR.search(full_text):
        return (
            "block",
            "path is inside a .spec/ folder that is not the resolved spec root ("
            + str(spec_root)
            + "). Flow writes spec artifacts only under FLOW_SPEC_ROOT (env var, "
            ".flow/config.md, or the default .flow/.spec at the repo root). Fix the path, or "
            "set FLOW_SPEC_ROOT if this repo keeps its specs elsewhere.",
        )

    if FLOW_DIR.search(full_text) and not FLOW_TEAM_FILE.search(full_text):
        return (
            "block",
            "only the team files config.md, memory.md, {board-key}-standards.md and "
            "{board-key}-playwright-patterns.md belong in .flow/. Spec artifacts go under "
            "the spec root (" + str(spec_root) + ").",
        )

    return "allow", ""


def paths_for(tool, tool_input):
    if tool in WRITE_TOOLS or tool == "Read":
        fp = tool_input.get("file_path") or tool_input.get("notebook_path")
        return [fp] if fp else []
    if tool == "Bash":
        return BASH_PATH_TOKEN.findall(tool_input.get("command", "") or "")
    return []


def main():
    if os.environ.get("FLOW_PATH_GUARD_ENABLED", "true").strip().lower() == "false":
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        log_line("malformed stdin: " + str(e))
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    if tool not in GUARDED_TOOLS:
        return 0

    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        spec_root = resolve_spec_root(project_dir(os.environ.get("CLAUDE_PROJECT_DIR") or cwd))
    except Exception as e:
        log_line("spec root unresolved, allowing: " + str(e))
        return 0

    for raw in paths_for(tool, tool_input):
        try:
            verdict, reason = classify(raw, "Write" if tool == "Bash" else tool, spec_root, cwd)
        except Exception as e:
            log_line("classify error, allowing " + str(raw) + ": " + str(e))
            continue
        if verdict != "block":
            continue
        if tool == "Bash":
            sys.stderr.write(
                "[flow-path-guard] warning: bash argument " + str(raw)
                + " looks like it breaks a Flow path rule: " + reason
                + " Ignore this if it is a false positive.\n"
            )
            log_line("WARN Bash " + str(raw) + ": " + reason)
            continue
        sys.stderr.write("[flow-path-guard] blocked " + tool + " on " + str(raw) + ": " + reason + "\n")
        log_line("BLOCK " + tool + " " + str(raw) + ": " + reason)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
