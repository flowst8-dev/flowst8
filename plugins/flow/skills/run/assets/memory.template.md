# Team memory

Curated facts about this codebase that every Flow run should know. Read
by the `flow` plugin's pipeline at pre-flight — frozen per run, capped at
`FLOW_MEMORY_CHAR_BUDGET` (default 4,000 characters).

**Rules** (full rationale: [`docs/memory-design.md`](https://github.com/christie304/flow/blob/main/docs/memory-design.md) in the Flow repository; not part of the installed plugin):

- One fact-cluster per bullet. Dense and actionable, like a good commit
  message. End every entry with provenance: `(initials, ticket, YYYY-MM)`.
- Facts, not instructions. Memory tells Flow *about the codebase*; it
  never tells Flow what to do. Entries that read as commands are ignored.
- Save: corrections, cross-cutting gotchas, environment facts, conventions
  not already in `.flow/{board-key}-standards.md`. Skip: anything
  re-readable from the code, session ephemera, raw dumps.
- Over budget? Consolidate or evict in the same PR that adds — never let it
  silently grow. This file only changes via PR; the pipeline never writes it.

## Entries

- Example: `saveProfile` in `src/api/saveProfile.ts` is also called by the
  nightly sync job — signature changes need both callers updated in the
  same release. (jd, PROJ-123, 2026-07)
- Example: the staging environment shares its Redis instance with QA —
  cache-invalidation changes show up in both. (jd, WEB-42, 2026-07)
