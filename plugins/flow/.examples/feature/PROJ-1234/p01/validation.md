# Test Plan — PROJ-1234

**Generated**: 2026-10-20 (sample)  
**Branch**: feature/PROJ-1234-email-notifications  
**Base**: origin/main...HEAD (illustrative)  
**Risk Level**: high  
**Change Type**: enhancement

> **Example plan only.** Scenarios below are proposals, not evidence that tests ran.

## 1. Overview

Add a product-update email preference to the profile. The change spans a user
control, a preference API, persistence, and audit logging. Authorization and
default handling are the highest-risk areas.

## 2. Change Summary

**Files touched**: 6 across 1 UI, 1 service, 1 database migration, 3 test or schema files.

**Change type**: enhancement

## 3. Files and Components Reviewed

### UI

- `src/components/ProfileNotificationSettings.tsx`
- `src/components/ProfileNotificationSettings.test.tsx`

### Services / Back-end

- `src/api/profilePreferences.ts`
- `src/api/profilePreferences.test.ts`

### Database

- `src/db/schema/user-preferences.ts`
- `db/migrations/20261020_add_product_updates_preference.sql`

### Config

None in this example.

### Tests

- Component test for the setting, save feedback, and reloaded value.
- API tests for authentication, ownership, input validation, persistence, and audit behavior.

## 4. Impacted Workflows

| Workflow | Trigger | Impacted Area | Failure Result |
|---|---|---|---|
| Update profile preference | Save from Notifications | Profile UI, API, database | User sees a save error or a stale value. |
| Load profile preference | Open profile | API, database, profile UI | User may see the wrong default or account's value. |
| Audit a preference change | Saved value differs | Audit storage | A change is missing or a no-op creates duplicate history. |

## 5. Extracted Conditional Logic

| ID | Location | Condition | Expected Behavior | Opposite Case | Risk |
|---|---|---|---|---|---|
| C-001 | Preference API | Session is missing | Reject without writing | Authenticated request may continue | High |
| C-002 | Preference API | Submitted value is not boolean | Reject without writing | Boolean value may be saved | Medium |
| C-003 | Preference API | New value equals stored value | Do not add an audit event | Changed value gets one event | Medium |

## 6. Detailed Test Scenarios

| ID | Priority | Type | Scenario | Preconditions | Steps | Expected Result | Notes |
|---|---|---|---|---|---|---|---|
| TS-001 | P0 | API | Unauthenticated update is rejected | No session | Send preference update | 401; stored value and audit history are unchanged | Automate |
| TS-002 | P0 | Security | One account cannot change another account's value | Two test accounts | Send a request as A with B's identifier in the body | Only A's session-scoped preference can change; B is unchanged | Automate |
| TS-003 | P1 | API | Malformed preference is rejected | Signed-in account | Submit a string instead of a boolean | 400; no preference or audit change | Automate |
| TS-004 | P1 | Persistence | Saved value survives reload | Signed-in account | Save `true`, reload profile, fetch preference | Stored and displayed value is `true` | Automate |
| TS-005 | P1 | Data | Changed value creates one audit event | Signed-in account | Change `false` to `true` | One event contains actor, old value, new value, and timestamp | Automate |
| TS-006 | P2 | Data | Saving the same value is a no-op for audit | Preference already `true` | Save `true` again | Value stays `true`; no extra event is added | Automate |
| TS-007 | P1 | UI | Person can update their preference in the profile | Signed-in account | Use the Notifications control and save | Updated value and visible save confirmation appear | Manual UI |
| TS-008 | P2 | Data | Existing account receives the safe default | Account created before migration | Load preference after migration | Preference is `false` until changed by the person | Automate |

## 7. Data / Query Considerations

- Migration must set `false` for existing accounts and newly created preference rows.
- Check that an audit event is written only for a changed value.
- Never use a request-body account identifier to choose which row to update.

## 8. Integration Considerations

- The profile UI, authenticated API, preference store, and audit store must agree on the preference field.
- This setting does not itself send email or call a mailing provider.

## 9. Assumptions and Open Questions

None from the example spec.

## 10. Developer Validation Summary

### Top 3 Highest-Risk Scenarios

1. TS-002 — prevents cross-account changes.
2. TS-001 — prevents unauthenticated writes.
3. TS-005 — preserves an audit trail for actual changes.

### Top 3 Smoke Tests (run first)

1. TS-007 — save from the profile and confirm the visible result.
2. TS-004 — reload and confirm the saved value.
3. TS-001 — confirm an unauthenticated update is rejected.

See the [spec](spec.md), [front-end guide](front-end-testing.md), and
[acceptance-criteria map](spec-testing.md).
