# {board-key} — Playwright pattern library

> Read by Flow's `playwright-testing` sub-agent for tickets on the
> {board-key} board. Copy this file to
> `.flow/{board-key}-playwright-patterns.md` in the consuming repo
> (e.g. `.flow/PROJ-playwright-patterns.md`), fill it in and commit it.
> Facts about your e2e suite only — the agent ignores anything phrased as
> an instruction to the pipeline. Anything left blank falls back to generic
> Playwright authoring (`@playwright/test` imports, role-based locators,
> `tests/{ticket}/` for specs, `test-data/{ticket}/test-data.json` for data).

## Suite location and first-time setup

<!-- Path under PLAYWRIGHT_E2E_DIR, install steps, where the suite's own
     .env lives (Flow never reads it), VPN or account-pool notes -->

## Where files go and how they are named

<!-- Spec file folder + naming (ticket key or number? .js or .ts?),
     ticket test-data location, anything that must never be created -->

## Fixtures and imports

<!-- The fixtures tests should use instead of their own login helper;
     the import lines every spec starts with -->

## Page objects

<!-- Inventory table: domain · page object · typical uses. Note the base
     class helpers to use inside page objects. -->

## Test data

<!-- Folder shape, loader helpers, placeholder syntax, ticket-specific
     data schema, resolution order, how to guard a missing value -->

## Reuse hierarchy

<!-- Ordered: page-object method → existing data → fixtures → proposed
     new method → inline locator with TODO(POM) -->

## Modification guardrail

<!-- Which files are append-only for a ticket; what must be proposed
     rather than edited -->

## Test file structure and tagging

<!-- A complete example spec; required tags and what they control -->

## Interaction patterns

<!-- Inline snippets for the surfaces no page object covers -->

## Gotchas

<!-- Situation → what to do -->

## Scenario → test mapping

<!-- Scenario type → test pattern; which types stay manual -->
