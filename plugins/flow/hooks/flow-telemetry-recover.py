"""
Flow telemetry recovery hook - Stop.

Shipped with the flow plugin and registered by hooks/hooks.json, so it
is active whenever the plugin is enabled. No manual install.

Every Flow command ends by moving its telemetry buffer into the repo's
.flow/.telemetry folder (scripts/telemetry_flush.py flush). This hook recovers
buffers from runs that never got that far (crash, abort): at the end of
each turn it runs `telemetry_flush.py recover`, which moves any buffer
older than 30 minutes into {repo}/.flow/.telemetry/. The age check leaves
alone a live run that spans several turns, such as a /flow:brief
interview.

No git, no network. A fast no-op when the buffer folder is empty (the
common case). Deliberately not registered on SubagentStop: Flow's
sub-agents are plugin agents, and recovering after every lane would race
the live run.

Exit code: always 0. A hook must never block the end of a turn on our own
bug.
"""

import json
import subprocess
import sys
from pathlib import Path

BUFFER_DIR = Path.home() / ".claude" / "flow" / "telemetry-buffer"
SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "telemetry_flush.py"


def payload_cwd():
    try:
        data = json.load(sys.stdin)
        cwd = data.get("cwd")
        return cwd if isinstance(cwd, str) and cwd else None
    except Exception:
        return None


def main():
    if not BUFFER_DIR.is_dir() or not any(BUFFER_DIR.glob("*.jsonl")):
        return 0
    if not SCRIPT.is_file():
        return 0
    cmd = [sys.executable, str(SCRIPT), "recover", "--min-age-minutes", "30"]
    cwd = payload_cwd()
    if cwd:
        cmd += ["--repo", cwd]
    subprocess.run(cmd, capture_output=True, timeout=50)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
