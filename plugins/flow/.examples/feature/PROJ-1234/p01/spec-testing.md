# Spec Testing Index — PROJ-1234

> **Example map only.** It links each criterion to a proposed scenario; it does not record test results.

| AC | Scenario | Classification | Covered in |
|---|---|---|---|
| 1 | Display the current preference in the profile Notifications section | Manual · UI | [TS-007 in validation.md](validation.md) and [step 1 in front-end-testing.md](front-end-testing.md) |
| 2 | Save the preference and restore it after reopening the profile | Automate · API/data | [TS-004 in validation.md](validation.md) and [step 2 in front-end-testing.md](front-end-testing.md) |
| 3 | Reject unauthenticated requests and prevent cross-account updates | Automate · security | [TS-001 and TS-002 in validation.md](validation.md) |
| 4 | Add an audit event only when the preference changes | Automate · data | [TS-005 and TS-006 in validation.md](validation.md) |

Every acceptance criterion from the example spec appears once. The linked
scenarios are plans only; run them in the consuming project before reporting
results.
