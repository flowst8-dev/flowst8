"""
Flow path resolution, shared by the plugin's hooks and scripts.

Stdlib only, Python 3.9+, no git calls. Every Flow script resolves the
spec root the same way the skills do (see
skills/run/references/preflight.md -> "Spec path resolution"):

  1. the FLOW_SPEC_ROOT environment variable, when set and non-empty;
  2. FLOW_SPEC_ROOT in {repo}/.flow/config.md;
  3. the default, `.flow/.spec` at the consuming repo root.

`~` and environment variables are expanded. A relative value is joined
with the consuming repo root: the nearest ancestor of the project
directory (CLAUDE_PROJECT_DIR, else the current directory) that holds a
`.git` entry, or the project directory itself when there is none.
"""

import os
import re
from pathlib import Path

FLOW_HOME = Path.home() / ".claude" / "flow"
BUFFER_DIR = FLOW_HOME / "telemetry-buffer"
DEFAULT_SPEC_ROOT = ".flow/.spec"

# Written into {repo}/.flow/.telemetry/ and {SPEC_ROOT}/reports/ when Flow
# creates them, so local data stays out of git unless a team deletes it.
IGNORE_ALL = "*\n!.gitignore\n"

_KEY_LINE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$")


def _resolve(path):
    try:
        return Path(path).expanduser().resolve()
    except (OSError, RuntimeError):
        return Path(os.path.abspath(str(Path(path).expanduser())))


def find_git_root(start):
    """Nearest ancestor of `start` (inclusive) holding a .git entry, or None.
    Walks up from the nearest existing ancestor, so `start` need not exist."""
    p = _resolve(start)
    for cand in [p] + list(p.parents):
        if (cand / ".git").exists():
            return cand
    return None


def project_dir(explicit=None):
    """The consuming repo root for this process."""
    base = explicit or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    base = _resolve(base)
    return find_git_root(base) or base


def read_config(repo_root):
    """KEY=VALUE pairs from {repo_root}/.flow/config.md.

    When the file has fenced code blocks only lines inside them count, so
    prose that happens to contain `KEY=value` is ignored. Last value wins."""
    path = Path(repo_root) / ".flow" / "config.md"
    values = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return values
    fenced = any(line.lstrip().startswith("```") for line in lines)
    inside = False
    for line in lines:
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if fenced and not inside:
            continue
        m = _KEY_LINE.match(line)
        if m:
            values[m.group(1)] = m.group(2).strip().strip("\"'")
    return values


def config_value(key, repo_root, default=None):
    """Environment variable, then .flow/config.md, then `default`.
    Unset and empty both fall through."""
    env = os.environ.get(key, "").strip()
    if env:
        return env
    value = read_config(repo_root).get(key, "").strip()
    return value or default


def expand_path(raw, base):
    """Expand ~ and $VARS; join a relative result with `base`."""
    text = os.path.expandvars(os.path.expanduser(str(raw).strip().strip("\"'")))
    p = Path(text)
    if not p.is_absolute():
        p = Path(base) / p
    return _resolve(p)


def resolve_spec_root(repo_root=None, override=None):
    repo_root = Path(repo_root) if repo_root else project_dir()
    raw = override or config_value("FLOW_SPEC_ROOT", repo_root, DEFAULT_SPEC_ROOT)
    return expand_path(raw, repo_root)


def telemetry_enabled(repo_root):
    return str(config_value("FLOW_TELEMETRY_ENABLED", repo_root, "true")).lower() != "false"


def telemetry_dir(repo_root):
    """Local run telemetry for one consuming repo. Not spec-root-relative, so
    it stays in the repo whatever FLOW_SPEC_ROOT points at."""
    return Path(repo_root) / ".flow" / ".telemetry"


def ensure_ignored_dir(path):
    """Create `path` if missing. Only on that first creation, drop a
    .gitignore that ignores everything in it; a folder that already exists
    is left as the team configured it."""
    path = Path(path)
    if path.is_dir():
        return path
    path.mkdir(parents=True, exist_ok=True)
    try:
        (path / ".gitignore").write_text(IGNORE_ALL, encoding="utf-8", newline="\n")
    except OSError:
        pass
    return path


def is_within(candidate, root):
    """Case-insensitive on Windows; False across drives."""
    a = os.path.normcase(str(_resolve(candidate)))
    b = os.path.normcase(str(_resolve(root)))
    try:
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


def slug(value, fallback="unknown"):
    s = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return s or fallback


def ticket_part(value):
    v = str(value or "").strip()
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*-\d+", v):
        return v.upper()
    return "no-ticket"


def telemetry_relpath(run_id, start_event):
    """{YYYY-MM}/{run_id}__{user}__{command}__{ticket}.jsonl"""
    start = start_event or {}
    user = slug(start.get("user"))
    command = slug(start.get("invocation"))
    ticket = ticket_part(start.get("ticket"))
    month = run_id[:4] + "-" + run_id[4:6] if re.match(r"\d{6}", run_id) else "unknown"
    return month + "/" + run_id + "__" + user + "__" + command + "__" + ticket + ".jsonl"
