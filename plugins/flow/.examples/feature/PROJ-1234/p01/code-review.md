# Code Review — PROJ-1234

**Reviewed**: 2026-10-20 (sample)  
**Files**: 6  
**Standards**: example only — no consuming-project standards were loaded

> **Illustrative finding, not a real code review.** No source code was inspected.

## Summary

- **High**: 1
- **Medium**: 0
- **Low**: 0

## Findings

### High

| File | Location | Issue | Rule |
|---|---|---|---|
| `src/api/profilePreferences.ts` | `updatePreference()` | The example handler selects the account using a `userId` from the request body. A caller could target another account. Derive the account from the authenticated session and add an ownership test. | PROJ standards → authorization and session identity |

### Medium

| File | Location | Issue | Rule |
|---|---|---|---|
| None. | — | — | — |

### Low

| File | Location | Issue | Rule |
|---|---|---|---|
| None. | — | — | — |

## Clean Files

- `src/components/ProfileNotificationSettings.tsx`
- `src/components/ProfileNotificationSettings.test.tsx`
- `src/api/profilePreferences.test.ts`
- `src/db/schema/user-preferences.ts`
- `db/migrations/20261020_add_product_updates_preference.sql`

This finding is intentionally paired with the failed example verdict for
[AC 3](acceptance-criteria.md).
