# Acceptance Criteria Checklist — PROJ-1234

**Verified**: 2026-10-20 (sample)  
**Branch**: feature/PROJ-1234-email-notifications  
**Diff**: origin/main...HEAD (illustrative)  
**Decision log**: present ([../decision-log.md](../decision-log.md))

> **Example checklist only.** The verdicts and evidence are fictional and do not mean a real implementation was verified.

| # | AC Summary | Verdict | Evidence | Decision Log |
|---|---|---|---|---|
| 1 | Signed-in person can see the current preference | ✅ Pass | Example diff renders the stored setting in Profile → Notifications. | covered by row 1 |
| 2 | Saved preference persists after reopening the profile | ✅ Pass | Example diff saves the boolean and loads it with the profile. | covered by row 4 |
| 3 | Unauthenticated or cross-account updates are rejected | ❌ Fail | Example handler uses `request.body.userId` instead of the authenticated session identity. | covered by row 2 |
| 4 | Only a real change creates an audit event with the required fields | ✅ Pass | Example diff records the actor, old and new values, and timestamp only when the value changes. | covered by row 3 |

## Summary

- **Pass**: 3
- **Partial**: 0
- **Fail**: 1
- **Manual**: 0

## Decision log gaps

None. Decision-log coverage is advisory; it does not change a criterion's
verdict.

See the separate [code-review findings](code-review.md) and
[planned test coverage](spec-testing.md).
