# Spec Template — Canonical

This is the single source of truth for the spec file Flow writes in Phase 2.
Any phase that references the spec template loads it from this file.
Do not duplicate this template in SKILL.md or anywhere else.

Write the populated spec to `{CARD_ROOT}/{PASS_DIR}/spec.md`
(for a first pass, `{CARD_ROOT}/p01/spec.md`).

---

## Template

```markdown
# Spec: {CARD TITLE}

**Ticket**: {full-ticket}
**Date**: {TODAY YYYY-MM-DD}
**Author**: {git user.name} <{git user.email}>
**Branch**: {resolved branch name}
**Source**: jira-mcp | pasted

## Problem Statement
{2-4 sentences from card description}

## Goals
1. {Primary goal}
2. {Secondary goal}

## Acceptance Criteria
- [ ] 1. {AC from card}
- [ ] 2. {AC from card}

## Out of Scope
1. {Explicitly excluded items, or "None stated"}

## User Impact
{Who is affected and how}

## Constraints
1. {Technical or business constraint}

## Open Questions
1. {Anything that cannot be resolved from the card alone, or "None"}

## Implementation Prerequisites

### Database Objects
| Object Name | Type | Schema | Status | Notes |
|-------------|------|--------|--------|-------|

### SQL Scripts
- [ ] {script name and purpose, or "None"}

### Other Prerequisites
- [ ] {Config changes, env setup, or "None"}
```

---

## Authoring rules

1. Use the full ticket (e.g. `PROJ-123`) as `{full-ticket}` throughout.
2. Combine git name/email as `Name <email>`. Today's date is the spec date.
3. Number all list items for easy reference.
4. If a field cannot be confidently populated from the card, write `[NEEDS CLARIFICATION]`.
5. Never commit to the base branch. Writing the spec file is the whole job.

---

## Board-specific flag checks (optional)

If a board-specific standards file exists at
`.flow/{board-key}-standards.md` in the consuming repo, load it and use
any rules it defines for user-facing text, currency, timezone,
roles/permissions, caching, environment-specific config, and database
conventions when populating the **Constraints** section.

---

## Database dependency scan

Before populating **Implementation Prerequisites**, scan both the card content and
any referenced code files for database objects:

1. In the card content — look for mentions of stored procedures, views, triggers,
   functions, table names, migrations, or SQL scripts (e.g. `CREATE`, `ALTER`,
   `EXEC` / `CALL`, schema-qualified names such as `dbo.` or `public.`, and
   common prefixes such as `usp_`, `vw_`, `fn_`, `tr_`).
2. In the codebase — if the card names specific code files or features, search
   those files for queries, ORM models, migrations, and procedure/view/function
   references.
3. Classify each object: Stored Procedure, View, Function, Trigger, Table DDL,
   Migration, or SQL Script. Note whether it is **existing** (needs modification)
   or **new** (needs creation), and which schema it belongs to.
4. Populate the Implementation Prerequisites section with these findings. If
   nothing is found, write `None — no database dependencies identified.`
