"""
Flow report - summarize local Flow telemetry.

Reads {repo}/.flow/.telemetry/**/*.jsonl (one file per run, written at the end
of every Flow command) and prints a markdown report:

  headline       runs, success / partial / failed, median and p90 duration,
                 tokens, tool calls, agent dispatches
  by command     one row per invocation (run, dry-run, spec, code, ...)
  by ticket      passes, runs, last run, last outcome, retries used
  agent cost     dispatches, tokens, tool calls, time and model per agent
  quality        code-review findings by severity, AC verdicts,
                 escalations, retry-budget use, where failed runs stopped
  recent runs    the latest runs, newest first

Usage:
  python flow_report.py [TICKET] [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                            [--user SLUG] [--command NAME] [--limit N]
                            [--html [PATH]] [--json]
                            [--spec-root PATH] [--repo PATH]

--html writes one self-contained HTML dashboard (inline CSS and SVG, no
network) to {SPEC_ROOT}/reports/flow-report-{YYYYMMDD-HHMM}.html, or
PATH, and prints its location after the markdown. --json prints the
aggregated data instead of markdown.

The repo is --repo, else CLAUDE_PROJECT_DIR, else the current directory.
Telemetry is always read from that repo's .flow/.telemetry. The spec root
(--spec-root, else FLOW_SPEC_ROOT, else .flow/config.md, else .flow/.spec)
only decides where the HTML file goes. Read-only apart from the HTML file;
stdlib only; Python 3.9+.
"""

import argparse
import html
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flow_paths import ensure_ignored_dir, expand_path, project_dir, resolve_spec_root, slug, telemetry_dir  # noqa: E402

STATUSES = ("success", "partial", "failed", "incomplete")
STATUS_ICON = {"success": "✅", "partial": "⚠️", "failed": "❌", "incomplete": "⏳"}
TICKET_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]+-\d+$")
DEFAULT_RETRY_BUDGET = 2

# Phase id -> plugin agent, used only when an event carries no `agent`.
# Orchestrator-only phases (joins, consolidation, settings) map to None.
PHASE_AGENTS = (
    (re.compile(r"\.implementer$"), "implementer"),
    (re.compile(r"\.commit$"), "branch-manager"),
    (re.compile(r"\.(join|consolidate|halted)$"), None),
    (re.compile(r"^wave\.a\.jira_fetch"), "jira-fetch"),
    (re.compile(r"^wave\.a\.decision_logger"), "decision-logger"),
    (re.compile(r"^wave\.b\.branch_manager"), "branch-manager"),
    (re.compile(r"^wave\.b\.spec_author"), "spec-author"),
    (re.compile(r"^wave\.c\.implementer"), "implementer"),
    (re.compile(r"^wave\.e\."), "code-reviewer"),
    (re.compile(r"^wave\.d\."), "ac-verifier"),
    (re.compile(r"^wave\.f\.(spec|code)_commit"), "branch-manager"),
    (re.compile(r"^wave\.g\.test_planner"), "test-planner"),
    (re.compile(r"^wave\.h\.playwright_testing"), "playwright-testing"),
    (re.compile(r"^phase\.5c"), "branch-manager"),
    (re.compile(r"^phase\.8\.spec_commit"), "branch-manager"),
)


# ---------------------------------------------------------------- reading


def parse_ts(value):
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def read_events(root):
    warnings = []
    events = []
    for path in sorted(root.rglob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as e:
            warnings.append(f"{path.name}: unreadable ({e})")
            continue
        for n, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                warnings.append(f"{path.name}:{n} is not valid JSON")
                continue
            if isinstance(ev, dict):
                events.append(ev)
    return events, warnings


def agent_for(ev):
    if ev.get("agent"):
        return ev["agent"]
    phase = ev.get("phase") or ""
    for pattern, agent in PHASE_AGENTS:
        if pattern.search(phase):
            return agent
    return None


def counts(d, keys):
    if not isinstance(d, dict) or not any(k in d for k in keys):
        return None
    return {k: int(num(d.get(k)) or 0) for k in keys}


def build_runs(events):
    by_run = defaultdict(list)
    for ev in events:
        if ev.get("run_id"):
            by_run[ev["run_id"]].append(ev)

    runs, dispatches = [], []
    for run_id, evs in by_run.items():
        evs.sort(key=lambda e: e.get("ts") or "")
        start = next((e for e in evs if e.get("event") == "run.start"), {})
        end = next((e for e in reversed(evs) if e.get("event") == "run.end"), None)
        t0 = parse_ts(start.get("ts") or evs[0].get("ts"))
        t1 = parse_ts(end.get("ts")) if end else None
        duration = int((t1 - t0).total_seconds() * 1000) if t0 and t1 else None
        if duration is None or duration < 0:
            duration = num((end or {}).get("duration_ms"))

        model = start.get("model") or "unknown"
        agent_models = start.get("agent_models") if isinstance(start.get("agent_models"), dict) else {}
        flags = start.get("flags") if isinstance(start.get("flags"), dict) else {}

        tokens = tool_uses = agent_ms = 0
        n_dispatch = n_missing = 0
        ac = review = None
        ac_fallback = review_fallback = None
        review_escalated = verify_escalated = False
        degenerated = halts = 0
        retries_from_outcome = 0
        errors = []
        pr_url = None
        handoff = None

        for ev in evs:
            kind = ev.get("event")
            phase = ev.get("phase") or ""
            outputs = ev.get("outputs") if isinstance(ev.get("outputs"), dict) else {}
            if kind == "outcome":
                if ev.get("kind") == "ac_verify":
                    ac = counts(ev.get("results"), ("pass", "partial", "fail", "manual")) or ac
                elif ev.get("kind") == "code_review":
                    review = counts(ev.get("results"), ("high", "medium", "low")) or review
                retries_from_outcome = max(retries_from_outcome, int(num(ev.get("retries_used")) or 0))
                continue
            if kind == "artifact":
                if ev.get("kind") == "pull_request":
                    pr_url = ev.get("path")
                elif ev.get("kind") == "handoff":
                    handoff = ev.get("path")
                continue
            if kind not in ("phase.end", "phase.error"):
                continue
            if kind == "phase.error":
                errors.append({"phase": phase, "error_code": ev.get("error_code") or "unknown",
                               "terminal": bool(ev.get("terminal"))})
            if phase.endswith(".halted"):
                halts += 1
            if phase in ("wave.e.consolidate", "wave.d.consolidate"):
                if outputs.get("escalated"):
                    if phase.startswith("wave.e"):
                        review_escalated = True
                    else:
                        verify_escalated = True
                if outputs.get("escalation_degenerated"):
                    degenerated += 1
                if phase == "wave.d.consolidate":
                    ac_fallback = counts(outputs, ("pass", "partial", "fail", "manual")) or ac_fallback
            agent = agent_for(ev)
            if agent == "ac-verifier" and kind == "phase.end":
                ac_fallback = counts(outputs, ("pass", "partial", "fail", "manual")) or ac_fallback
            if agent == "code-reviewer" and kind == "phase.end":
                review_fallback = counts(outputs.get("findings"), ("high", "medium", "low")) or review_fallback
            if outputs.get("skipped") or not agent:
                continue
            usage = ev.get("usage") if isinstance(ev.get("usage"), dict) else None
            n = int(num((usage or {}).get("dispatches")) or 1)
            row = {
                "run_id": run_id,
                "agent": agent,
                "model": (usage or {}).get("model") or agent_models.get(agent) or model,
                "dispatches": n,
                "tokens": num((usage or {}).get("tokens")),
                "tool_uses": num((usage or {}).get("tool_uses")),
                "duration_ms": num((usage or {}).get("duration_ms")),
                "error": kind == "phase.error",
            }
            if row["model"] == "inherit":
                row["model"] = model
            dispatches.append(row)
            n_dispatch += n
            if row["tokens"] is None and row["tool_uses"] is None and row["duration_ms"] is None:
                n_missing += n
            tokens += row["tokens"] or 0
            tool_uses += row["tool_uses"] or 0
            agent_ms += row["duration_ms"] or 0

        totals = (end or {}).get("usage_totals")
        if isinstance(totals, dict):
            if num(totals.get("tokens")) is not None:
                tokens = num(totals.get("tokens"))
            if num(totals.get("tool_uses")) is not None:
                tool_uses = num(totals.get("tool_uses"))
            if num(totals.get("agent_duration_ms")) is not None:
                agent_ms = num(totals.get("agent_duration_ms"))

        status = (end or {}).get("status") or "incomplete"
        if status not in STATUSES:
            status = "incomplete"
        retries = num((end or {}).get("retry_budget_used"))
        if retries is None:
            retries = retries_from_outcome
        budget = num(flags.get("retry_budget"))
        user = start.get("user") or "unknown"
        runs.append({
            "run_id": run_id,
            "started": t0.strftime("%Y-%m-%d %H:%M") if t0 else "",
            "date": t0.date().isoformat() if t0 else "",
            "ticket": start.get("ticket") or "no-ticket",
            "command": start.get("invocation") or "unknown",
            "user": user,
            "user_slug": slug(user),
            "host": start.get("host"),
            "model": model,
            "flow_version": start.get("flow_version") or start.get("specflow_version"),
            "pass_dir": start.get("pass_dir"),
            "status": status,
            "terminal_phase": (end or {}).get("terminal_phase"),
            "duration_ms": duration,
            "tokens": tokens,
            "tool_uses": tool_uses,
            "agent_duration_ms": agent_ms,
            "dispatches": n_dispatch,
            "dispatches_missing_usage": n_missing,
            "retries_used": int(retries or 0),
            "retry_budget": int(budget) if budget is not None else DEFAULT_RETRY_BUDGET,
            "ac": ac or ac_fallback,
            "review": review or review_fallback,
            "review_escalated": review_escalated,
            "verify_escalated": verify_escalated,
            "escalation_degenerated": degenerated,
            "retry_halts": halts,
            "errors": errors,
            "pull_request": pr_url,
            "handoff": handoff,
        })
    runs.sort(key=lambda r: (r["started"], r["run_id"]))
    return runs, dispatches


def keep(run, args):
    if args.ticket and run["ticket"].upper() != args.ticket.upper():
        return False
    if args.since and run["date"] < args.since:
        return False
    if args.until and run["date"] > args.until:
        return False
    if args.command and run["command"].lower() != args.command.lower():
        return False
    if args.user and slug(args.user) not in run["user_slug"]:
        return False
    return True


# ------------------------------------------------------------ aggregation


def percentile(values, p):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    k = (len(values) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def status_counts(runs):
    c = Counter(r["status"] for r in runs)
    return {s: c.get(s, 0) for s in STATUSES}


def success_rate(sc):
    finished = sc["success"] + sc["partial"] + sc["failed"]
    return sc["success"] / finished if finished else None


def aggregate(runs, dispatches, limit):
    finished = [r for r in runs if r["status"] != "incomplete"]
    sc = status_counts(runs)
    headline = dict(
        runs=len(runs),
        **sc,
        success_rate=success_rate(sc),
        median_duration_ms=median(r["duration_ms"] for r in finished),
        p90_duration_ms=percentile([r["duration_ms"] for r in finished], 0.9),
        tokens=sum(r["tokens"] or 0 for r in runs),
        tool_uses=sum(r["tool_uses"] or 0 for r in runs),
        agent_duration_ms=sum(r["agent_duration_ms"] or 0 for r in runs),
        dispatches=sum(r["dispatches"] for r in runs),
        dispatches_missing_usage=sum(r["dispatches_missing_usage"] for r in runs),
        tickets=len({r["ticket"] for r in runs if r["ticket"] != "no-ticket"}),
        users=len({r["user_slug"] for r in runs}),
        first=runs[0]["started"] if runs else None,
        last=runs[-1]["started"] if runs else None,
    )

    by_cmd = defaultdict(list)
    for r in runs:
        by_cmd[r["command"]].append(r)
    commands = []
    for cmd, g in sorted(by_cmd.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        done = [r for r in g if r["status"] != "incomplete"]
        gsc = status_counts(g)
        commands.append(dict(
            command=cmd, runs=len(g), **gsc, success_rate=success_rate(gsc),
            median_duration_ms=median(r["duration_ms"] for r in done),
            p90_duration_ms=percentile([r["duration_ms"] for r in done], 0.9),
            tokens=sum(r["tokens"] or 0 for r in g),
            tool_uses=sum(r["tool_uses"] or 0 for r in g),
        ))

    by_ticket = defaultdict(list)
    for r in runs:
        by_ticket[r["ticket"]].append(r)
    tickets = []
    for t, g in by_ticket.items():
        last = g[-1]
        full = [r for r in g if r["command"] == "run"]
        passes = {r["pass_dir"] for r in full if r["pass_dir"]}
        tickets.append({
            "ticket": t, "runs": len(g), "passes": len(passes) or len(full),
            "last_run": last["started"], "last_command": last["command"], "last_status": last["status"],
            "retries_used": sum(r["retries_used"] for r in g),
            "tokens": sum(r["tokens"] or 0 for r in g),
        })
    tickets.sort(key=lambda t: t["last_run"], reverse=True)

    by_agent = defaultdict(list)
    for d in dispatches:
        by_agent[d["agent"]].append(d)
    agents = []
    for a, g in by_agent.items():
        measured = [d for d in g if d["tokens"] is not None]
        tok = sum(d["tokens"] for d in measured)
        models = Counter(d["model"] for d in g if d["model"])
        agents.append({
            "agent": a,
            "dispatches": sum(d["dispatches"] for d in g),
            "tokens": tok,
            "avg_tokens": tok / sum(d["dispatches"] for d in measured) if measured else None,
            "tool_uses": sum(d["tool_uses"] or 0 for d in g),
            "duration_ms": sum(d["duration_ms"] or 0 for d in g),
            "model": ", ".join(m for m, _ in models.most_common(2)) or "-",
            "errors": sum(1 for d in g if d["error"]),
        })
    agents.sort(key=lambda a: (-(a["tokens"] or 0), -a["dispatches"], a["agent"]))

    reviewed = [r for r in runs if r["review"]]
    verified = [r for r in runs if r["ac"]]
    findings = {k: sum(r["review"][k] for r in reviewed) for k in ("high", "medium", "low")}
    verdicts = {k: sum(r["ac"][k] for r in verified) for k in ("pass", "partial", "fail", "manual")}
    scored = verdicts["pass"] + verdicts["partial"] + verdicts["fail"]
    pipeline = [r for r in runs if r["command"] == "run"]
    stops = Counter(r["terminal_phase"] for r in runs if r["status"] == "failed" and r["terminal_phase"])
    codes = Counter(e["error_code"] for r in runs for e in r["errors"])
    quality = {
        "review": dict(runs=len(reviewed), **findings,
                       escalated_runs=sum(1 for r in reviewed if r["review_escalated"])),
        "ac": dict(runs=len(verified), **verdicts,
                   pass_rate=verdicts["pass"] / scored if scored else None,
                   escalated_runs=sum(1 for r in verified if r["verify_escalated"])),
        "escalation_degenerated": sum(r["escalation_degenerated"] for r in runs),
        "retries": {
            "pipeline_runs": len(pipeline),
            "runs_using_retries": sum(1 for r in pipeline if r["retries_used"] > 0),
            "cycles": sum(r["retries_used"] for r in pipeline),
            "budget": sum(r["retry_budget"] for r in pipeline),
            "exhausted": sum(1 for r in pipeline if r["retry_budget"] and r["retries_used"] >= r["retry_budget"]),
            "early_halts": sum(r["retry_halts"] for r in runs),
        },
        "stopped_at": stops.most_common(5),
        "error_codes": codes.most_common(5),
    }

    recent = list(reversed(runs))[:limit]
    return {"headline": headline, "commands": commands, "tickets": tickets, "agents": agents,
            "quality": quality, "recent": recent}


# ------------------------------------------------------------- formatting


def fmt_ms(ms):
    if ms is None:
        return "–"
    s = int(round(ms / 1000))
    if s >= 3600:
        return f"{s // 3600}h {s % 3600 // 60:02d}m"
    if s >= 60:
        return f"{s // 60}m {s % 60:02d}s"
    return f"{s}s"


def fmt_tokens(n):
    if n is None:
        return "–"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 10_000:
        return f"{n / 1000:.1f}k"
    return f"{int(n):,}"


def fmt_int(n):
    return "–" if n is None else f"{int(n):,}"


def fmt_pct(x):
    return "–" if x is None else f"{x:.0%}"


def status_label(s):
    return f"{STATUS_ICON.get(s, '')} {s}".strip()


def md_table(head, rows, align=None):
    align = align or ["l"] + ["r"] * (len(head) - 1)
    sep = ["---:" if a == "r" else "---" for a in align]
    out = ["| " + " | ".join(head) + " |", "| " + " | ".join(sep) + " |"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in rows]
    return "\n".join(out)


def describe_filters(args):
    parts = []
    if args.ticket:
        parts.append(f"ticket {args.ticket.upper()}")
    if args.command:
        parts.append(f"command {args.command}")
    if args.user:
        parts.append(f"user ~{slug(args.user)}")
    if args.since:
        parts.append(f"since {args.since}")
    if args.until:
        parts.append(f"until {args.until}")
    return ", ".join(parts)


def render_markdown(data, tel_dir, args, ticket_limit=20):
    h, q = data["headline"], data["quality"]
    out = ["# Flow report", ""]
    sub = (f"_{h['runs']} runs · {h['first'][:10]} → {h['last'][:10]} · {h['tickets']} tickets · "
           f"{h['users']} users · `{tel_dir}`_")
    filters = describe_filters(args)
    if filters:
        sub += f"  \n_Filters: {filters}_"
    out += [sub, "", "## Headline", ""]
    out.append(md_table(
        ["Runs", "✅ Success", "⚠️ Partial", "❌ Failed", "⏳ Incomplete", "Success rate",
         "Median time", "p90 time", "Tokens", "Tool calls", "Dispatches"],
        [[h["runs"], h["success"], h["partial"], h["failed"], h["incomplete"], fmt_pct(h["success_rate"]),
          fmt_ms(h["median_duration_ms"]), fmt_ms(h["p90_duration_ms"]), fmt_tokens(h["tokens"]),
          fmt_int(h["tool_uses"]), fmt_int(h["dispatches"])]],
        ["r"] * 11))
    if h["dispatches_missing_usage"]:
        out += ["", f"_{h['dispatches_missing_usage']} of {h['dispatches']} agent dispatches reported no usage, "
                    "so token and tool-call totals undercount._"]

    out += ["", "## By command", ""]
    out.append(md_table(
        ["Command", "Runs", "✅", "⚠️", "❌", "⏳", "Success rate", "Median time", "p90 time", "Tokens", "Tool calls"],
        [[f"`{c['command']}`", c["runs"], c["success"], c["partial"], c["failed"], c["incomplete"],
          fmt_pct(c["success_rate"]), fmt_ms(c["median_duration_ms"]), fmt_ms(c["p90_duration_ms"]),
          fmt_tokens(c["tokens"]), fmt_int(c["tool_uses"])] for c in data["commands"]]))

    tickets = data["tickets"]
    out += ["", "## By ticket", ""]
    out.append(md_table(
        ["Ticket", "Passes", "Runs", "Last run (UTC)", "Last command", "Outcome", "Retries used", "Tokens"],
        [[t["ticket"], t["passes"], t["runs"], t["last_run"], f"`{t['last_command']}`",
          status_label(t["last_status"]), t["retries_used"], fmt_tokens(t["tokens"])]
         for t in tickets[:ticket_limit]],
        ["l", "r", "r", "l", "l", "l", "r", "r"]))
    if len(tickets) > ticket_limit:
        out += ["", f"_…and {len(tickets) - ticket_limit} more tickets (narrow with a ticket or --since)._"]

    out += ["", "## Agent cost", ""]
    if data["agents"]:
        out.append(md_table(
            ["Agent", "Dispatches", "Tokens", "Avg tokens", "Tool calls", "Agent time", "Model", "Errors"],
            [[a["agent"], a["dispatches"], fmt_tokens(a["tokens"]), fmt_tokens(a["avg_tokens"]),
              fmt_int(a["tool_uses"]), fmt_ms(a["duration_ms"]), a["model"], a["errors"]] for a in data["agents"]],
            ["l", "r", "r", "r", "r", "r", "l", "r"]))
    else:
        out.append("_No agent dispatches in these runs._")

    rv, ac, rt = q["review"], q["ac"], q["retries"]
    out += ["", "## Quality signals", ""]
    if rv["runs"]:
        out.append(f"- **Code review** ({rv['runs']} runs, final round): 🔴 {rv['high']} high · "
                   f"🟠 {rv['medium']} medium · ⚪ {rv['low']} low")
    else:
        out.append("- **Code review**: no reviewed runs")
    if ac["runs"]:
        out.append(f"- **AC verification** ({ac['runs']} runs): {ac['pass']} pass · {ac['partial']} partial · "
                   f"{ac['fail']} fail · {ac['manual']} manual — pass rate {fmt_pct(ac['pass_rate'])}")
    else:
        out.append("- **AC verification**: no verified runs")
    out.append(f"- **Escalations**: review {rv['escalated_runs']}/{rv['runs']} runs · verification "
               f"{ac['escalated_runs']}/{ac['runs']} runs · {q['escalation_degenerated']} degenerated")
    if rt["pipeline_runs"]:
        out.append(f"- **Retry budget** ({rt['pipeline_runs']} pipeline runs): {rt['runs_using_retries']} used retries · "
                   f"{rt['cycles']} of {rt['budget']} cycles spent · {rt['exhausted']} exhausted · "
                   f"{rt['early_halts']} early halts (fix touched no flagged file)")
    if q["stopped_at"]:
        out.append("- **Failed runs stopped at**: " + ", ".join(f"`{p}` ×{n}" for p, n in q["stopped_at"]))
    if q["error_codes"]:
        out.append("- **Phase errors**: " + ", ".join(f"`{c}` ×{n}" for c, n in q["error_codes"]))

    out += ["", "## Recent runs", ""]
    out.append(md_table(
        ["Started (UTC)", "Ticket", "Command", "Status", "Time", "Tokens", "Tool calls", "User"],
        [[r["started"], r["ticket"], f"`{r['command']}`", status_label(r["status"]), fmt_ms(r["duration_ms"]),
          fmt_tokens(r["tokens"]), fmt_int(r["tool_uses"]), r["user_slug"]] for r in data["recent"]],
        ["l", "l", "l", "l", "r", "r", "r", "l"]))
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------- html


def esc(value):
    return html.escape(str(value), quote=True)


def hbar_chart(rows, unit_fmt=str, label_w=150, width=560, bar_h=22, gap=8):
    """rows: [(label, [(value, css_class, title)])] - stacked horizontal bars."""
    rows = [r for r in rows if sum(v for v, _, _ in r[1]) > 0]
    if not rows:
        return '<p class="empty">No data.</p>'
    total_max = max(sum(v for v, _, _ in segs) for _, segs in rows) or 1
    plot_w = width - label_w - 70
    height = len(rows) * (bar_h + gap) + gap
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" class="chart">']
    for i, (label, segs) in enumerate(rows):
        y = gap + i * (bar_h + gap)
        parts.append(f'<text x="{label_w - 8}" y="{y + bar_h / 2 + 4}" class="lbl" text-anchor="end">'
                     f'{esc(label)}</text>')
        x = label_w
        total = 0
        for value, cls, title in segs:
            w = plot_w * value / total_max
            if w > 0:
                parts.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w, 1.5):.1f}" height="{bar_h}" rx="3" '
                             f'class="{cls}"><title>{esc(title)}: {esc(unit_fmt(value))}</title></rect>')
            x += w
            total += value
        parts.append(f'<text x="{x + 6:.1f}" y="{y + bar_h / 2 + 4}" class="val">{esc(unit_fmt(total))}</text>')
    parts.append("</svg>")
    return "".join(parts)


def vbar_chart(points, width=560, height=180):
    """points: [(label, {status: n})] - stacked columns by status."""
    if not points:
        return '<p class="empty">No data.</p>'
    top = max(sum(p.values()) for _, p in points) or 1
    pad_l, pad_b, pad_t = 28, 24, 10
    plot_w, plot_h = width - pad_l - 6, height - pad_b - pad_t
    step = plot_w / len(points)
    bw = max(min(step * 0.7, 28), 2)
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" class="chart">',
             f'<text x="{pad_l - 6}" y="{pad_t + 8}" class="axis" text-anchor="end">{top}</text>',
             f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{width - 6}" y2="{pad_t + plot_h}" class="grid"/>']
    every = max(1, len(points) // 8)
    for i, (label, segs) in enumerate(points):
        x = pad_l + i * step + (step - bw) / 2
        y = pad_t + plot_h
        for status in STATUSES:
            v = segs.get(status, 0)
            if not v:
                continue
            h = plot_h * v / top
            y -= h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" class="s-{status}">'
                         f'<title>{esc(label)}: {v} {status}</title></rect>')
        if i % every == 0:
            short = label[5:] if len(label) == 10 else label
            parts.append(f'<text x="{x + bw / 2:.1f}" y="{height - 6}" class="axis" text-anchor="middle">'
                         f'{esc(short)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def html_table(head, rows, numeric=()):
    numeric = set(numeric)
    th = "".join(f'<th class="{"num" if i in numeric else ""}">{esc(h)}</th>' for i, h in enumerate(head))
    body = []
    for row in rows:
        tds = "".join(f'<td class="{"num" if i in numeric else ""}">{c}</td>' for i, c in enumerate(row))
        body.append(f"<tr>{tds}</tr>")
    return (f'<div class="tbl"><table class="sortable"><thead><tr>{th}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def badge(status):
    return f'<span class="badge s-{esc(status)}">{esc(status)}</span>'


def timeline(runs):
    days = defaultdict(Counter)
    for r in runs:
        if r["date"]:
            days[r["date"]][r["status"]] += 1
    keys = sorted(days)
    if len(keys) > 45:  # roll up by ISO week
        weeks = defaultdict(Counter)
        for d in keys:
            y, w, _ = datetime.strptime(d, "%Y-%m-%d").isocalendar()
            weeks[f"{y}-W{w:02d}"].update(days[d])
        return [(k, dict(weeks[k])) for k in sorted(weeks)]
    return [(k, dict(days[k])) for k in keys]


CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;
--ok:#2e8b57;--warn:#c98500;--bad:#c8402f;--idle:#9a9aa0;--accent:#3b6fd8}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1d1d20;--fg:#ececef;--muted:#9a9aa3;
--line:#2e2e33;--ok:#4cc38a;--warn:#e9b13b;--bad:#ef6a57;--idle:#7a7a82;--accent:#6f9cf5}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 16px 48px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:16px;margin:0 0 12px}.sub{color:var(--muted);margin:0 0 24px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.kpi,.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi .v{font-size:24px;font-weight:650;font-variant-numeric:tabular-nums}.kpi .k{color:var(--muted);font-size:12px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(420px,100%),1fr));gap:16px;margin-bottom:16px}
section.card{margin-bottom:16px}.chart{width:100%;height:auto;display:block}
.chart .lbl,.chart .val{fill:var(--fg);font-size:12px}.chart .axis{fill:var(--muted);font-size:10px}
.chart .grid{stroke:var(--line)}
.s-success{fill:var(--ok)}.s-partial{fill:var(--warn)}.s-failed{fill:var(--bad)}.s-incomplete{fill:var(--idle)}
.c-accent{fill:var(--accent)}
.sev-high{fill:var(--bad)}.sev-medium{fill:var(--warn)}.sev-low{fill:var(--idle)}
.ac-pass{fill:var(--ok)}.ac-partial{fill:var(--warn)}.ac-fail{fill:var(--bad)}.ac-manual{fill:var(--accent)}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin-top:6px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.tbl{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:12px;cursor:pointer;user-select:none}
th.num,td.num{text-align:right}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;color:#fff}
.badge.s-success{background:var(--ok)}.badge.s-partial{background:var(--warn)}
.badge.s-failed{background:var(--bad)}.badge.s-incomplete{background:var(--idle)}
ul.q{margin:0;padding-left:18px}ul.q li{margin:4px 0}.empty,.foot{color:var(--muted)}
code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12.5px}
"""

JS = r"""
document.querySelectorAll('table.sortable th').forEach(function(th,i){th.addEventListener('click',function(){
var tb=th.closest('table').tBodies[0],rows=[].slice.call(tb.rows),asc=th.dataset.dir!=='asc';
th.closest('tr').querySelectorAll('th').forEach(function(o){delete o.dataset.dir});th.dataset.dir=asc?'asc':'desc';
function key(r){var t=r.cells[i].innerText.trim(),m=/^([\d.]+)([kM])$/.exec(t),n=parseFloat(t.replace(/[,%]/g,''));
if(m)n=parseFloat(m[1])*(m[2]==='M'?1e6:1e3);return isNaN(n)?t.toLowerCase():n}
rows.sort(function(a,b){var x=key(a),y=key(b);return (x>y?1:x<y?-1:0)*(asc?1:-1)});
rows.forEach(function(r){tb.appendChild(r)})})});
"""


def legend(items):
    return '<div class="legend">' + "".join(
        f'<span><i style="background:var(--{v})"></i>{esc(k)}</span>' for k, v in items) + "</div>"


def render_html(data, runs, tel_dir, args):
    h, q = data["headline"], data["quality"]
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    filters = describe_filters(args)
    kpis = [
        ("Runs", fmt_int(h["runs"])), ("Success rate", fmt_pct(h["success_rate"])),
        ("Median time", fmt_ms(h["median_duration_ms"])), ("p90 time", fmt_ms(h["p90_duration_ms"])),
        ("Tokens", fmt_tokens(h["tokens"])), ("Tool calls", fmt_int(h["tool_uses"])),
        ("Tickets", fmt_int(h["tickets"])), ("Agent dispatches", fmt_int(h["dispatches"])),
    ]
    status_legend = legend([("success", "ok"), ("partial", "warn"), ("failed", "bad"), ("incomplete", "idle")])
    status_rows = [(s, [(h[s], f"s-{s}", s)]) for s in STATUSES]
    cmd_rows = [(c["command"], [(c[s], f"s-{s}", s) for s in STATUSES]) for c in data["commands"]]
    agent_rows = [(a["agent"], [(a["tokens"] or 0, "c-accent", "tokens")]) for a in data["agents"]]
    rv, ac, rt = q["review"], q["ac"], q["retries"]
    review_rows = [(k, [(rv[k], f"sev-{k}", k)]) for k in ("high", "medium", "low")]
    ac_rows = [(k, [(ac[k], f"ac-{k}", k)]) for k in ("pass", "partial", "fail", "manual")]

    quality = [
        f"<li><b>Code review</b>: {rv['runs']} runs reviewed, {rv['escalated_runs']} escalated to three reviewers</li>",
        f"<li><b>AC verification</b>: {ac['runs']} runs verified, pass rate {fmt_pct(ac['pass_rate'])}, "
        f"{ac['escalated_runs']} escalated</li>",
        f"<li><b>Degenerated escalations</b>: {q['escalation_degenerated']}</li>",
    ]
    if rt["pipeline_runs"]:
        quality.append(f"<li><b>Retry budget</b>: {rt['runs_using_retries']} of {rt['pipeline_runs']} pipeline runs "
                       f"used retries; {rt['cycles']} of {rt['budget']} cycles spent; {rt['exhausted']} exhausted; "
                       f"{rt['early_halts']} early halts</li>")
    if q["stopped_at"]:
        quality.append("<li><b>Failed runs stopped at</b>: " + ", ".join(
            f"<code>{esc(p)}</code> ×{n}" for p, n in q["stopped_at"]) + "</li>")
    if q["error_codes"]:
        quality.append("<li><b>Phase errors</b>: " + ", ".join(
            f"<code>{esc(c)}</code> ×{n}" for c, n in q["error_codes"]) + "</li>")

    cmd_table = html_table(
        ["Command", "Runs", "Success", "Partial", "Failed", "Incomplete", "Success rate", "Median", "p90",
         "Tokens", "Tool calls"],
        [[f"<code>{esc(c['command'])}</code>", c["runs"], c["success"], c["partial"], c["failed"], c["incomplete"],
          fmt_pct(c["success_rate"]), fmt_ms(c["median_duration_ms"]), fmt_ms(c["p90_duration_ms"]),
          fmt_tokens(c["tokens"]), fmt_int(c["tool_uses"])] for c in data["commands"]],
        numeric=range(1, 11))
    ticket_table = html_table(
        ["Ticket", "Passes", "Runs", "Last run (UTC)", "Last command", "Outcome", "Retries used", "Tokens"],
        [[esc(t["ticket"]), t["passes"], t["runs"], esc(t["last_run"]), f"<code>{esc(t['last_command'])}</code>",
          badge(t["last_status"]), t["retries_used"], fmt_tokens(t["tokens"])] for t in data["tickets"]],
        numeric=(1, 2, 6, 7))
    agent_table = html_table(
        ["Agent", "Dispatches", "Tokens", "Avg tokens", "Tool calls", "Agent time", "Model", "Errors"],
        [[esc(a["agent"]), a["dispatches"], fmt_tokens(a["tokens"]), fmt_tokens(a["avg_tokens"]),
          fmt_int(a["tool_uses"]), fmt_ms(a["duration_ms"]), esc(a["model"]), a["errors"]] for a in data["agents"]],
        numeric=(1, 2, 3, 4, 5, 7))
    recent_table = html_table(
        ["Started (UTC)", "Ticket", "Command", "Status", "Time", "Tokens", "Tool calls", "Retries", "User", "Run id"],
        [[esc(r["started"]), esc(r["ticket"]), f"<code>{esc(r['command'])}</code>", badge(r["status"]),
          fmt_ms(r["duration_ms"]), fmt_tokens(r["tokens"]), fmt_int(r["tool_uses"]), r["retries_used"],
          esc(r["user_slug"]), f"<code>{esc(r['run_id'])}</code>"] for r in data["recent"]],
        numeric=(4, 5, 6, 7))

    first = (h["first"] or "")[:10]
    last = (h["last"] or "")[:10]
    filter_text = (" · filters: " + esc(filters)) if filters else ""
    tiles = "".join(f'<div class="kpi"><div class="v">{esc(v)}</div><div class="k">{esc(k)}</div></div>'
                    for k, v in kpis)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Flow report</title><style>{CSS}</style></head>
<body><main>
<h1>Flow report</h1>
<p class="sub">{h['runs']} runs · {esc(first)} → {esc(last)} · {h['tickets']} tickets · {h['users']} users{filter_text}</p>
<section class="kpis">{tiles}</section>
<section class="grid2">
<div class="card"><h2>Runs by outcome</h2>{hbar_chart(status_rows, fmt_int)}</div>
<div class="card"><h2>Runs over time</h2>{vbar_chart(timeline(runs))}{status_legend}</div>
</section>
<section class="grid2">
<div class="card"><h2>Runs by command</h2>{hbar_chart(cmd_rows, fmt_int)}{status_legend}</div>
<div class="card"><h2>Tokens by agent</h2>{hbar_chart(agent_rows, fmt_tokens)}</div>
</section>
<section class="grid2">
<div class="card"><h2>Code-review findings (final round)</h2>{hbar_chart(review_rows, fmt_int)}</div>
<div class="card"><h2>AC verdicts</h2>{hbar_chart(ac_rows, fmt_int)}</div>
</section>
<section class="card"><h2>Quality signals</h2><ul class="q">{''.join(quality)}</ul></section>
<section class="card"><h2>By command</h2>{cmd_table}</section>
<section class="card"><h2>Agent cost</h2>{agent_table}</section>
<section class="card"><h2>By ticket</h2>{ticket_table}</section>
<section class="card"><h2>Recent runs</h2>{recent_table}</section>
<p class="foot">Generated {esc(generated)} from <code>{esc(tel_dir)}</code> by /flow:report. Click a column header to sort.</p>
</main><script>{JS}</script></body></html>
"""


# -------------------------------------------------------------------- main


def date_arg(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}")
    return value


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="flow_report.py", description="Summarize local Flow telemetry")
    ap.add_argument("ticket", nargs="?", help="only this ticket, e.g. PROJ-123")
    ap.add_argument("--since", type=date_arg, help="first run date to include (UTC), YYYY-MM-DD")
    ap.add_argument("--until", type=date_arg, help="last run date to include (UTC), YYYY-MM-DD")
    ap.add_argument("--user", help="user slug, or part of it, e.g. jane-doe")
    ap.add_argument("--command", help="run, dry-run, spec, code, review, verify, test, playwright, ...")
    ap.add_argument("--limit", type=int, default=15, help="rows in the recent-runs list (default 15)")
    ap.add_argument("--html", nargs="?", const="", default=None, metavar="PATH",
                    help="also write an HTML dashboard (default "
                         "{SPEC_ROOT}/reports/flow-report-{YYYYMMDD-HHMM}.html)")
    ap.add_argument("--json", action="store_true", help="print the aggregated data as JSON instead of markdown")
    ap.add_argument("--spec-root", help="spec root for the default HTML path; default: resolved like every Flow command")
    ap.add_argument("--repo", help="consuming repo root; telemetry is read from its .flow/.telemetry. Default: CLAUDE_PROJECT_DIR or the current directory")
    args = ap.parse_args(argv)

    # `--html PROJ-123` almost certainly meant the ticket, not a file name.
    if args.html and not args.ticket and TICKET_RE.match(args.html):
        args.ticket, args.html = args.html, ""

    if args.spec_root:
        spec_root = expand_path(args.spec_root, Path.cwd())
    else:
        spec_root = resolve_spec_root(project_dir(args.repo))
    tel_dir = telemetry_dir(project_dir(args.repo))

    events, warnings = read_events(tel_dir) if tel_dir.is_dir() else ([], [])
    for w in warnings[:10]:
        print(f"warning: {w}", file=sys.stderr)
    if len(warnings) > 10:
        print(f"warning: ...and {len(warnings) - 10} more unreadable lines", file=sys.stderr)

    all_runs, dispatches = build_runs(events)
    runs = [r for r in all_runs if keep(r, args)]
    kept = {r["run_id"] for r in runs}
    dispatches = [d for d in dispatches if d["run_id"] in kept]

    if not runs:
        if not all_runs:
            msg = (f"No Flow telemetry yet in {tel_dir}.\n\n"
                   "Every /flow command writes one file there when it finishes (unless "
                   "FLOW_TELEMETRY_ENABLED=false). Run something like /flow:run PROJ-123, "
                   "then try /flow:report again.")
        else:
            msg = (f"No runs match the filters ({describe_filters(args)}). {len(all_runs)} runs "
                   f"exist in {tel_dir}; loosen the filters and try again.")
        if args.json:
            print(json.dumps({"telemetry_dir": str(tel_dir), "runs": 0, "message": msg}, indent=2))
        else:
            print(msg)
        return 0

    data = aggregate(runs, dispatches, max(args.limit, 1))
    data["telemetry_dir"] = str(tel_dir)
    data["filters"] = describe_filters(args)

    html_path = None
    if args.html is not None:
        if args.html:
            html_path = expand_path(args.html, Path.cwd())
            html_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
            html_path = ensure_ignored_dir(spec_root / "reports") / f"flow-report-{stamp}.html"
        html_path.write_text(render_html(data, runs, tel_dir, args), encoding="utf-8")

    if args.json:
        data["runs"] = runs
        if html_path:
            data["html"] = str(html_path)
        print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
        return 0

    print(render_markdown(data, tel_dir, args), end="")
    if html_path:
        print(f"\nHTML dashboard: {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
