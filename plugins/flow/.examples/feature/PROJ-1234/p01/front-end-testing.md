# Front-End Test Guide — PROJ-1234

**For**: manual verification in the running app  
**Branch**: feature/PROJ-1234-email-notifications

> **Example guide only.** The steps have not been run against a live app.

## What changed (in plain terms)

Your profile now has a Notifications section with a product-update email
preference. You can change the setting, save it, and see the saved choice when
you return to your profile.

## Before you start

- **Where**: Open your profile and choose **Notifications**.
- **Sign in as**: A regular account that can edit its own profile.
- **You'll need**: A test account with the setting initially turned off.

## Test steps

### 1. Change and save the preference

1. Open **Profile → Notifications**.
2. Turn on **Product update emails** and select **Save**.
3. **You should see**: A save confirmation, and the control remains on.

- [ ] Pass  - [ ] Fail — notes: __________

### 2. Confirm the saved choice is restored

1. Leave the profile, then open **Profile → Notifications** again.
2. **You should see**: **Product update emails** is still on.

- [ ] Pass  - [ ] Fail — notes: __________

### 3. Turn the preference off

1. Turn off **Product update emails** and select **Save**.
2. **You should see**: A save confirmation, and the control remains off after reopening the page.

- [ ] Pass  - [ ] Fail — notes: __________

## If something looks wrong

Capture the page URL, a screenshot, and the exact message shown, then attach
them to the ticket.

For API, authorization, migration, and audit checks, see
[validation.md](validation.md).
