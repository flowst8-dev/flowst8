# Writing style — shared conventions for Flow sub-agents that generate lists and specs

> Loaded by sub-agents and skills that produce list-shaped or
> spec-shaped output: `spec-author`, `brief`, `decision-logger`,
> `test-planner`, `playwright-testing`, `code-reviewer` (its findings),
> `ac-verifier` (its verdicts).
>
> These are style rules for Flow's own outputs — they are not opinions
> about how developers should write code, nor how consuming repos
> should structure their docs.

---

## 1. Atomic bullets

When generating a bulleted list from prose or unstructured input,
every bullet is one idea in 5–10 words. No compound sentences, no
run-ons. Split before bulleting.

**Rules:**

- Split compound sentences on `, and`, `, but`, `so that`, `because`,
  `where`, and `and + <subject pronoun>` before bulleting.
- Lowercase the first letter of every bullet (unless it's an acronym
  like LLM/API/UI/SQL/AC).
- Drop leading articles (`the`, `a`, `an`) for punch.
- Aim for 5–10 words per bullet.
- Strip leading modal phrases (`the tool could`, `it should`,
  `we can`) — keep the action.
- Dedupe near-duplicates by normalized prefix.

**Where this applies:**
- Acceptance criteria lists inside spec.md
- Findings/verdicts in code-review.md and acceptance-criteria.md
- Test scenarios in validation.md and spec-testing.md
- Bullet points inside decision-log rows

**Where it does NOT apply:**
- Body prose (spec problem statements, decision-log context, brief
  narratives). Prose stays prose.
- Verbose lists the user has explicitly asked for.

---

## 2. Tight one-line-per-field for structured records

When a sub-agent produces a structured record with well-known fields
(decision log rows, brief cards, AC verdict rows, playwright scenario
metadata), each field is one line. Prefer:

```
**Problem** — one line
**Solution** — one imperative line
**Success** — one line: the "so that" benefit
```

Over:

```
## Problem
paragraph of prose describing the problem in detail…

## Solution
paragraph of prose describing what to build…
```

**Why:** the record is a scannable data view; prose bloats it and
buries the fields.

**Filler-stripping pipeline** (apply to every one-liner):
- Remove `hey`, `so basically`, `I would like to`, `it would be great
  if`, `essentially`, `just`, `basically`.
- Rewrite `we could look into <X>` → `<X>`.
- Rewrite `there is a need to <X>` → `<X>`.

**Scope note:** the canonical `spec.md` template at
`references/spec-template.md` currently uses prose sections
(`## Problem Statement\n{paragraph}`) rather than the tight one-liner
form above. That's a deliberate current-state choice for downstream
parsers (`test-planner`, `ac-verifier`, `playwright-testing` all read
that shape). If the spec.md format is ever rewritten to the tight
one-liner form, all downstream parsers must be updated in the same
release. Until then: this rule applies to *records inside* the spec
(decision-log rows, AC test scenarios, spec-testing.md rows), not to
the spec.md's top-level sections themselves.

---

## 3. Titles

- Imperative verb + object phrase, ≤10 words.
- Sentence case.
- No trailing punctuation.
- Never a truncated first sentence.

Good: `Prevent duplicate profile submissions`
Bad: `The profile form needs to prevent duplicate submissions`

---

## 4. Sentence case in headings

All headings — H1, H2, H3, table headers, list-item leads — use
sentence case, never Title Case, never ALL CAPS. This applies to
sub-agent output, not to the plugin's own source docs (which have
their own house style).

---

## Why these rules live here

The style rules ship with the plugin so every developer's runs produce
the same shape of output, and changes to them are reviewable via PR
rather than living on individual developers' machines.
