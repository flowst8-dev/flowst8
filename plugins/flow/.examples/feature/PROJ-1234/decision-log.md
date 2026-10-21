# Decision Log — PROJ-1234

**Card**: PROJ-1234 — Manage email update preferences in the profile  
**Jira URL**: `[sample — fictional ticket]`  
**Latest pass ACs**: [./p01/acceptance-criteria.md](p01/acceptance-criteria.md)  
**Latest pass spec**: [./p01/spec.md](p01/spec.md)  
**Created**: 2026-10-20  
**Last updated**: 2026-10-20

> **Example only.** The ticket and decisions below are fictional.

## Decisions

| # | Date | Topic | Decision | Owners | Notes |
|---|---|---|---|---|---|
| 1 | 2026-10-20 | Default preference | Existing and new accounts start opted out (`false`). | Product (sample) | Keeps the choice explicit. Supports AC 1. |
| 2 | 2026-10-20 | Account ownership | Derive the account being changed from the authenticated session; do not accept a target user ID from the request body. | Engineering (sample) | Supports AC 3. |
| 3 | 2026-10-20 | Audit events | Write an audit event only when the stored value changes. | Product, Engineering (sample) | Retries that do not change the value must not create duplicate events. Supports AC 4. |
| 4 | 2026-10-20 | Persistence | Save the preference with the profile and load it again when the profile is reopened. | Engineering (sample) | Supports AC 2. |

## How to add to this log

In a consuming project, Flow's `decision-logger` appends confirmed decisions
from supplied notes or discussion. Existing rows are preserved; a changed
decision is recorded as a new row rather than silently replacing history.

## Acceptance Criteria coverage

The current pass's [acceptance-criteria.md](p01/acceptance-criteria.md) is
the canonical criterion checklist. The verifier's decision-log coverage is
advisory and does not determine whether a criterion passes.
