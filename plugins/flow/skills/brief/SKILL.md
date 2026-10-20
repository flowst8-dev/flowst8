---
name: brief
description: Flow subcommand. Ticket-readiness interview for one Jira card — asks your role (pre-dev, dev, QA), interviews you on the requirements for that role, gives a verdict, saves a brief manifest beside the spec, and offers to post a summary comment. Run as /flow:brief {ticket}.
argument-hint: "{ticket}"
disable-model-invocation: true
---

# brief — Ticket Readiness Interview

> **Version:** 2.0.0

> `/flow:brief` runs in the main conversation rather than as a
> sub-agent, because the interview needs the developer and plugin agents
> cannot talk to them. The main `/flow` skill also routes
> `/flow brief {ticket}` here.

> **One ticket. One role. One honest verdict.**
> Know what you're building — or testing, or defining — before you start.

Ten minutes of the right questions now beats a day of rework later. `/flow:brief`
walks you through your ticket from the perspective of your phase of work,
surfaces the gaps while they're still cheap to fix, and gives you a verdict
you can actually act on.

---

## Input

A Jira ticket key with board prefix: `PROJ-123`, `WEB-42`, `OPS-7`, etc.

```
/flow:brief PROJ-123
/flow:brief WEB-42
```

The ticket is `$ARGUMENTS`.

---

## Phase 0 — Pre-flight

Run the shared pre-flight in
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/preflight.md` in
**subcommand mode**: config, source mode, `CARD_ROOT` and the
`run.start` event with `invocation: "brief"`. No pass folder is created.

---

## Phase 1 — Fetch the card

Dispatch the `flow:jira-fetch` agent (Agent tool,
`subagent_type: "flow:jira-fetch"`) with this prompt:

```
jira-fetch {ticket} --comments 5 --epic
```

On `source_mode: paste | card_file` from pre-flight, skip the dispatch and
use the staged payload.

**On `ok: true`:**
Read `title`, `description`, `acceptance_criteria`, `issue_type`, `labels`,
`status`, `parent`, `parent_card`, `comments`.

If `parent_card` is populated, treat the **parent's description and ACs** as
the primary source of requirements. Tell the user upfront:
*"This is a sub-task of {parent}. I'll be interviewing you on the parent's
requirements as they apply to your phase."*

**On `ok: false`:**
Show the error in one line and offer the paste fallback:
*"Jira isn't reachable ({error_code}) — paste the ticket content here and
we'll keep going."*

Do not retry. One fetch, one fallback.

---

## Phase 2 — Establish role

Ask the user which phase of the work they're responsible for:

```
What's your role on this ticket?

  [ Pre-dev ]    BA, PM, analyst — you define or refine the work
  [ Dev ]        Developer — you build it
  [ Post-dev ]   QA, UAT tester — you verify it
```

Wait for their selection. The entire interview adapts from this answer.

---

## Phase 3 — The interview

### Rules of engagement (all roles)

1. **One question at a time.** Never batch questions. Wait for the answer.
2. **Always provide a recommended answer.** Ground it in the ticket, any codebase
   context, and best practice. An interview with no recommended answers is just an exam.
3. **Explore before asking.** If a question can be answered from the card or
   related tickets, do that first.
4. **Walk the tree in order.** Resolve parent questions before asking dependent ones.
5. **Match the card's complexity.** Don't pad; don't rush.
6. **Use comments as context.** PM scope decisions, QA notes, and clarifications
   live in comments — surface that context in your recommended answers.
7. **Flag card problems openly.** Ambiguous, contradictory, or missing ACs should
   be called out clearly.

---

### Pre-dev interview (BA / PM / Analyst)

**Axis 1 — Requirements clarity**
- Can they explain the business problem in one sentence?
- For each AC: is it specific enough for a developer to implement without guessing?
  Is it specific enough for QA to verify without guessing?
- Are any ACs ambiguous, contradictory, or untestable?
- Is the "Definition of Done" clear — who signs off, and on what?

**Axis 2 — Scope and boundaries**
- What is explicitly out of scope for this ticket?
- Are there adjacent features that could cause confusion?
- Has scope been approved by the right stakeholders?
- What's the smallest version that still delivers value?

**Axis 3 — Dependencies and risks**
- Does this depend on another ticket being done first?
- What decisions are still open that could change requirements?

**Axis 4 — Handoff readiness**
- Is there enough information for a developer to start without a meeting?
- What questions will the developer definitely ask — are the answers on the card?

---

### Dev interview (Developer)

**Axis 1 — AC understanding**
- Can they restate each AC in their own words?
- What does "done" look like concretely?
- Is any AC ambiguous or under-specified?

**Axis 2 — Scope and boundaries**
- What is explicitly not part of this ticket?
- Which parts of the codebase should they not touch?
- What's the smallest change that satisfies all ACs?

**Axis 3 — Edge cases and failure modes**
- What happens on null, empty, malformed, or duplicate input?
- What happens when an upstream dependency fails?
- Permission, auth, and audit implications?

**Axis 4 — Implementation approach**
- Which files, components, or endpoints will change?
- What pattern are they planning to follow — does it match the existing codebase?
- What database or stored proc changes are required?
- What's the rollback path if this goes wrong in production?

---

### Post-dev interview (QA / UAT Tester)

**Axis 1 — AC coverage**
- For each AC: what is the specific test scenario that proves it passes?
- Are there ACs verifiable only at runtime? Flag as manual-only.

**Axis 2 — Test scenario completeness**
- For each AC: happy path, negative path, and at least one edge case?
- Role or permission variants? Data state variants?

**Axis 3 — Environment and data**
- What environment are they testing in?
- What test data is needed and does it exist?
- Dependencies that need to be in place before testing?

**Axis 4 — Sign-off and handoff**
- Who has final sign-off authority?
- What's the process if a bug is found?
- Regression areas at risk from this change?

---

## Phase 4 — Verdict

```
═══════════════════════════════════════════════════════════
  BRIEF: {ticket} — {title}
  Role: {Pre-dev | Dev | Post-dev}
  {timestamp}
═══════════════════════════════════════════════════════════

  AC Understanding       🟢 / 🟡 / 🔴   one-line note
  Scope Clarity          🟢 / 🟡 / 🔴   one-line note
  Edge Cases             🟢 / 🟡 / 🔴   one-line note
  Approach / Plan        🟢 / 🟡 / 🔴   one-line note

  ─────────────────────────────────────────────────────────
  ✈️  READY FOR TAKEOFF   — Good to proceed
  🔄  GAPS FOUND          — Resolve these before starting
  ─────────────────────────────────────────────────────────

  Open items
  → {item} (owner: {who})
```

| Score | Meaning |
|-------|---------|
| 🟢 | Answered clearly, grounded in the ticket or codebase |
| 🟡 | Answered with gaps, assumptions, or hedging |
| 🔴 | Couldn't answer, or the answer was wrong |

Be honest. A verdict that always says Ready for Takeoff is worse than no verdict.

---

## Phase 5 — Close

After the verdict, ask: **"Any questions before we wrap up?"**

Give them space to ask anything the interview surfaced.

---

## Phase 6 — Save the manifest

Write to the card folder resolved at pre-flight (never the consuming
codebase):
```
{CARD_ROOT}/manifest.md
```

If a `manifest.md` already exists, rename it first:
```
manifest-{YYYY-MM-DD-HHMM}.md
```

Never silently overwrite.

### Manifest structure

```markdown
# Brief Manifest — {ticket}

**Ticket**: {ticket}
**Title**: {title}
**URL**: {url}
**Role**: {Pre-dev | Dev | Post-dev}
**Timestamp**: {ISO timestamp}
**Status at brief**: {status}

---

## Acceptance Criteria (verbatim from card)

{AC list exactly as fetched — or from parent_card if sub-task}

---

## Interview Transcript

### Q1: {question}
**Recommended**: {what brief suggested}
**Answer**: {what the person said}

### Q2: ...

---

## Verdict

{full verdict block}

---

## Recommended Card Update

Based on everything surfaced during the interview, a suggested rewrite the
reporter or PM could paste directly into Jira.

**Suggested Description Update**
- Steps to reproduce (numbered, specific)
- Actual behavior
- Expected behavior
- Environment
- Suspected root cause (hypothesis — clearly marked)

**Suggested Acceptance Criteria**
Write as testable, unambiguous statements a QA engineer can execute.

---

## Open Items

{list with owners}
```

---

## Phase 7 — Post to Jira

After saving the manifest, offer to post a comment. Always show the
suggested comment to the user first. Never auto-post. On a clear yes,
dispatch the `flow:jira-commenter` agent (`subagent_type:
"flow:jira-commenter"`) with the ticket and the comment body, and show
its payload.

```
✈️ Brief complete — {READY FOR TAKEOFF | GAPS FOUND}
Role: {role} | {score icons}
Open items: {N}
Manifest: {CARD_ROOT}/manifest.md

---
🔍 Notes
{1–3 sentences summarizing what was found or hypothesized}

---
📋 Recommended Card Update

**Steps to Reproduce**
{numbered steps}

**Actual Behavior** / **Expected Behavior** / **Environment**
{details}

---
✅ Suggested Acceptance Criteria
1. {AC}
```

`jira-commenter` enforces the assignee check — if the ticket isn't assigned
to the current user, the post will be refused. Surface that refusal clearly.

---

## What this skill does NOT do

- Does not auto-post to Jira — offers, then waits for confirmation
- Does not block anyone from proceeding — Gaps Found is a strong recommendation, not a hard stop
- Does not invent requirements — only interviews on what the card says
- Does not write or modify production code

Close with `phase.start` / `phase.end` for `brief` and `run.end`, per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/emission-map.md` →
"Subcommand runs", then move the run's telemetry buffer into the local
telemetry file per
`${CLAUDE_PLUGIN_ROOT}/skills/run/references/telemetry-schema.md` →
"Where events go". The brief manifest stays where it was written under
`{CARD_ROOT}`; Flow does not commit or push it.

---

## Tone

The goal is to surface the misunderstanding that would cost a day of rework — in ten
minutes of conversation, before any work gets started. Keep it collegial and
constructive. A sharp co-worker helping you think it through, not an examiner.

---

## Example invocations

```
/flow:brief PROJ-123
/flow brief WEB-42            # same skill, through the /flow router
brief me on PROJ-123
am I ready to start on this ticket?
quiz me on OPS-7
```
