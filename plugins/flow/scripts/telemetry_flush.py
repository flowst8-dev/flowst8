"""
Flow telemetry flush - the last act of every Flow command.

Moves a run's telemetry buffer
(~/.claude/flow/telemetry-buffer/{run_id}.jsonl) into the consuming repo's
telemetry folder:

  {repo}/.flow/.telemetry/{YYYY-MM}/{run_id}__{user}__{command}__{ticket}.jsonl

and deletes the buffer. The folder does not depend on FLOW_SPEC_ROOT. No
git: Flow never commits or pushes telemetry. When the folder does not exist
yet it is created with a .gitignore (`*`, `!.gitignore`) so the files stay
out of version control unless a team deletes that file on purpose.

Usage:
  python telemetry_flush.py flush --run-id RID [--repo PATH]
  python telemetry_flush.py recover [--min-age-minutes N] [--repo PATH]

flush prints one JSON line: {ok, run_id, telemetry_path, error}.
recover flushes every buffer older than N minutes (default 30) - runs that
crashed before their final step - and prints one JSON line per buffer.
Exit code is always 0; telemetry never blocks a command.

The repo is --repo, else the run.start `cwd`, else CLAUDE_PROJECT_DIR or
the current directory.

Env:
  FLOW_TELEMETRY_ENABLED  'false' -> discard buffers, write nothing
  FLOW_HOOK_LOG           log file. Default ~/.claude/flow/hooks.log
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flow_paths import (  # noqa: E402
    BUFFER_DIR,
    FLOW_HOME,
    ensure_ignored_dir,
    find_git_root,
    project_dir,
    telemetry_dir,
    telemetry_enabled,
    telemetry_relpath,
)


def log_line(msg):
    path = Path(os.environ.get("FLOW_HOOK_LOG", str(FLOW_HOME / "hooks.log")))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            fh.write(ts + " telemetry: " + msg + "\n")
    except Exception:
        pass


def read_events(path):
    events = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return events
    for line in text.splitlines():
        if line.strip():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    return events


def repo_for(start, repo, fallback_repo=None):
    if repo:
        return project_dir(repo)
    cwd = start.get("cwd")
    if cwd and Path(cwd).exists():
        return find_git_root(cwd) or Path(cwd)
    return project_dir(fallback_repo)


def flush(run_id, repo=None, fallback_repo=None):
    result = {"ok": False, "run_id": run_id, "telemetry_path": None, "error": None}
    buf = BUFFER_DIR / (run_id + ".jsonl")
    try:
        if not buf.is_file():
            result["ok"] = True
            return result
        data = buf.read_text(encoding="utf-8")
        events = read_events(buf)
        start = next((e for e in events if e.get("event") == "run.start"), {})
        repo_root = repo_for(start, repo, fallback_repo)
        if not data.strip() or not telemetry_enabled(repo_root):
            buf.unlink()
            result["ok"] = True
            return result
        tel_dir = ensure_ignored_dir(telemetry_dir(repo_root))
        dest = tel_dir / telemetry_relpath(run_id, start)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not data.endswith("\n"):
            data += "\n"
        with dest.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(data)
        buf.unlink()
        result["telemetry_path"] = str(dest)
        result["ok"] = True
    except Exception as e:
        result["error"] = str(e)[:300]
        log_line(run_id + " flush failed: " + result["error"])
    return result


def recover(min_age_minutes, repo=None):
    """Flush buffers whose run never reached its final step. A buffer
    younger than min_age_minutes may belong to a live run that spans
    turns (a /flow:brief interview, say), so it is left alone."""
    results = []
    if not BUFFER_DIR.is_dir():
        return results
    cutoff = time.time() - min_age_minutes * 60
    for buf in sorted(BUFFER_DIR.glob("*.jsonl")):
        try:
            if buf.stat().st_mtime > cutoff:
                continue
        except OSError:
            continue
        res = flush(buf.stem, fallback_repo=repo)
        if res.get("telemetry_path"):
            log_line(buf.stem + " recovered -> " + res["telemetry_path"])
        results.append(res)
    return results


def main(argv):
    ap = argparse.ArgumentParser(description="Move Flow telemetry buffers into the local telemetry folder")
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True
    f = sub.add_parser("flush", help="flush one run's buffer")
    f.add_argument("--run-id", required=True)
    f.add_argument("--repo", help="consuming repo root; default: CLAUDE_PROJECT_DIR or cwd")
    r = sub.add_parser("recover", help="flush buffers left by crashed runs")
    r.add_argument("--min-age-minutes", type=int, default=30)
    r.add_argument("--repo", help="fallback consuming repo root")
    args = ap.parse_args(argv)
    if args.cmd == "flush":
        print(json.dumps(flush(args.run_id.strip(), args.repo)))
    else:
        for res in recover(args.min_age_minutes, args.repo):
            print(json.dumps(res))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as e:
        log_line("top-level crash: " + str(e))
        print(json.dumps({"ok": False, "error": str(e)[:300]}))
        sys.exit(0)
