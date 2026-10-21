# Spec: Manage email update preferences in the profile

**Ticket**: PROJ-1234  
**Date**: 2026-10-20  
**Author**: Sample author  
**Branch**: feature/PROJ-1234-email-notifications  
**Source**: paste

> **Example only.** Fictional requirements and implementation notes.

## Problem Statement

People cannot control whether they receive product-update emails from their
profile. The preference needs to be visible, saved, and associated with the
signed-in account so it can be honored later.

## Goals

1. Let a signed-in person view and change their product-update email preference.
2. Persist the preference so it remains the same after the profile is reopened.
3. Protect the preference from changes made on behalf of another account.

## Acceptance Criteria

- [ ] 1. A signed-in person can see the current product-update email preference in the profile's Notifications section.
- [ ] 2. Saving a changed preference persists it for that account and the saved value is shown when the profile is reopened.
- [ ] 3. Unauthenticated requests cannot change the preference, and a request cannot change another account's preference.
- [ ] 4. A real preference change creates one audit event with the actor, previous value, new value, and timestamp; saving the same value again does not create another event.

## Out of Scope

- Sending email campaigns or changing the mailing service.
- Preferences for product categories other than product updates.
- An administrator editing another person's preference.

## User Impact

The profile gains one control under **Notifications**. The person's choice is
saved and can be changed later. Existing accounts begin opted out.

## Constraints

1. Default the new preference to `false` for existing and newly created accounts.
2. Derive the account identity from the authenticated session, never from a user ID in the request body.
3. Accept only a boolean preference value; reject malformed input without changing stored data.
4. Do not send emails as part of saving this setting.
5. Create an audit event only when the stored preference actually changes.

## Open Questions

None for this example.

## Implementation Prerequisites

### Database Objects

| Object Name | Type | Schema | Status | Notes |
|---|---|---|---|---|
| `user_preferences.product_updates_enabled` | Column | Boolean, non-null | New | Default to `false`; associate with the authenticated account. |
| `user_preference_audit` | Table | Account, actor, field, old value, new value, timestamp | New | Record actual changes only; follow the consuming project's audit conventions. |

### SQL Scripts

No SQL file is included in this sample. The implementation should use the
consuming project’s migration tooling.

### Other Prerequisites

- The profile page and API use the existing authentication/session mechanism.

See the [decision log](../decision-log.md) for the example decisions behind
the defaults and authorization rule.
