# Decision Log Template — Canonical

This is the single source of truth for the decision log Flow writes at the
**card level** (one per Jira card, persisting across passes). Any phase or
sub-agent that references the decision-log template loads it from this file.

Write the populated decision log to `{DECISION_PATH}` — the resolved `{CARD_ROOT}/decision-log.md` (card-level, sits **above** the per-pass `p01/`, `p02/`, ... folders). `CARD_ROOT` is `{SPEC_ROOT}/{type}/{ticket}`; see `references/preflight.md` → "Spec path resolution" for how `SPEC_ROOT` and the type folder are resolved.

---

## Template

```markdown
# Decision Log — {full-ticket}

**Card**: {full-ticket} — {CARD TITLE}
**Jira URL**: {card.url or "[NEEDS CLARIFICATION] — pre-card mode"}
**Latest pass ACs**: [./p01/acceptance-criteria.md](./p01/acceptance-criteria.md)
**Latest pass spec**: [./p01/spec.md](./p01/spec.md)
**Created**: {YYYY-MM-DD}
**Last updated**: {YYYY-MM-DD}

> ## Append-only — never edit, never delete
>
> This log is the historical record of decisions made about this card.
> Rows are **never** removed or modified once written. When a decision is
> revised, add a **new row** that references the prior decision number in
> the **Notes** column (e.g. "Revisits row 4 — supersedes that approach").
> The earlier row remains as a record of what was decided at that point in
> time. Any tool that touches this file must preserve this invariant.

---

## Decisions

| # | Date | Topic | Decision | Owners | Notes |
|---|------|-------|----------|--------|-------|

---

## How to add to this log

1. Run one of:
   - `/flow:run {ticket} --decisions "paste text here"`
   - `/flow:run {ticket} --decisions ./path/to/notes.txt`
   - `/flow:run {ticket} --decisions {jira-comment-url}`
   - `/flow:decisions {ticket}` then paste content when prompted
2. Flow's `decision-logger` sub-agent extracts decisions from the content,
   dedupes against existing rows by Date+Topic+Decision (with a
   safety bias: when in doubt, add a new row rather than skip), and appends
   new rows only.
3. To revise an earlier decision, just paste content describing the change.
   The logger will add a new row referencing the original in **Notes** —
   never modifying the earlier row.

---

## Acceptance Criteria coverage

The latest pass's `acceptance-criteria.md` is the canonical AC list for this
card. This log deliberately does **not** copy the AC text inline — that would
go stale the moment the Jira card is edited. Instead, ac-verifier (Phase 4)
produces an advisory **Decision Log Coverage** section in the AC checklist
that names which decision rows reference each AC, and which ACs have no
matching decision row yet.

A row references an AC by mentioning it in the **Topic**, **Decision**, or
**Notes** column — for example `"AC 3 — audit log entry"` or
`"covers AC 1 and AC 2"`.

---

## Pre-card mode

This log can exist **before** the Jira card is created. When invoked via
`/flow:decisions {placeholder-ticket}` with no card present, Flow writes a
log with `Jira URL: [NEEDS CLARIFICATION] — pre-card mode` in the header.
When the real card is later created and `/flow:run {ticket}` runs for the first
time, the existing log is picked up and the header is updated with the
fetched card title and URL. Existing rows are never disturbed.
```

---

## Authoring rules for the decision-logger sub-agent

1. Use the full ticket key (e.g. `PROJ-123`) as `{full-ticket}`.
2. The `#` column is the row number — auto-incrementing, never reused even
   if a row is later marked as superseded.
3. Date format is `YYYY-MM-DD`. If the source content has no date, infer the
   nearest defensible date: the meeting subject line, the email send date,
   the Jira comment timestamp, or "today" as a last resort. Note inference
   in the **Notes** column.
4. Keep the **Decision** column to a single sentence when possible — the
   *what* of the decision.
5. **Owners** is comma-separated names or roles. If unclear, write
   `[NEEDS CLARIFICATION]` rather than guessing.
6. **Notes** carries everything else worth recording: the *why*, caveats,
   impact or risk, links (Jira ticket, wiki page, chat thread or document
   link, system name), and cross-references like `Revisits row N`. Always
   include `Source: {source-label}` so the row can be traced back. Keep
   the prose tight — bullets or sentence fragments are fine.
7. Never invent a decision. If the source is ambiguous about whether a
   decision was actually made (vs. just discussed), do not add a row —
   surface it in the sub-agent's return payload as a candidate the user
   should confirm.

---

## Why append-only matters

Decision logs are an audit trail. Their value depends on being trusted. If
rows can disappear or change retroactively, the log stops being a record and
becomes a moving narrative. By making append-only the strongest invariant of
this template, we keep the log usable for things like:

- Showing a stakeholder what was decided when
- Proving an AC mismatch is real (the decision really was X back then)
- Letting future passes see how thinking evolved
- Surfacing reversals openly rather than silently

If a row is genuinely wrong (e.g. a typo or a logger hallucination), the fix
is a new row that says so explicitly — never a quiet edit.
