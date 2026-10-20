<!-- Part of the run skill. Read on demand from SKILL.md.
     {SKILL_DIR} = the run skill's base directory; {PLUGIN_ROOT} = the
     flow plugin root. SKILL.md defines both. -->

# Full pipeline, part 2 — Waves E, F and D

### Wave E — Code review (escalated 3-way — 1 reviewer default, 3 on finding)

**Skipped entirely under `--docs-only`** — the code shipped through its
own review cycle. Emit `phase.end` `wave.e.code_review` with
`{skipped: true, reason: "docs-only"}` and proceed to Wave F.

**Escalation model.** Wave E dispatches **one reviewer first**
and only escalates to the full 3-way majority-vote pattern when that
reviewer flags a real problem. Clean code pays the cost of one
reviewer, not three; flagged code still gets the full defensibility of
majority vote before the pipeline decides to burn retry budget on a
fix.

#### Step 1 — Solo reviewer

Dispatch the `flow:code-reviewer` agent as `r1` alone:

```
code-reviewer \
  --files {paths from manifest.files_written} \
  --standards .flow/{board-key}-standards.md \
  --ticket {ticket} \
  --reviewer-id r1 \
  --write {PASS_ROOT}/.review/r1.json
```

If r1 returns with **no `high` or `medium` severity findings**, skip
escalation. Any `low` findings are still recorded in `{REVIEW_PATH}`
with `votes: 1/1` — advisory only, they do not trigger retry. Emit
`phase.end` `wave.e.consolidate` with `{escalated: false,
reviewers_returned: 1, ...}` and proceed to Wave F.

If r1 fails (`ok: false`), fall back to the 3-way pattern in step 2 —
we cannot decide on zero data.

#### Step 2 — Escalate on finding

If r1 flags **any** `high` or `medium` severity finding, dispatch
`flow:code-reviewer` again as `r2` and `r3` concurrently (two Agent
tool calls in one message), identical inputs:

```
code-reviewer \
  --files {paths from manifest.files_written} \
  --standards .flow/{board-key}-standards.md \
  --ticket {ticket} \
  --reviewer-id r{2|3} \
  --write {PASS_ROOT}/.review/r{2|3}.json
```

Wait for both to return. If either fails, continue with whoever
returned — the vote threshold adjusts (2/3 with 3 returned, 2/2 with 2
returned, and if only r1 returned we fall back to r1's judgment alone
with `escalation_degenerated: true` in telemetry).

#### Consolidation

Merge the returned finding sets into `{REVIEW_PATH}`:

1. **Dedupe.** A finding is the same as another if it has the same
   `(file, line, category)` triple. Category comes from `code-reviewer`'s
   output schema (e.g. `null-check`, `sql-injection`, `style-violation`).
2. **Tag with vote count.** Each deduped finding carries `votes: N/M`
   where N is the number of reviewers who flagged it and M is the
   number of reviewers who returned successfully (3/3 on escalated,
   1/1 on non-escalated).
3. **Retain all findings** in `{REVIEW_PATH}` regardless of vote count
   — the reader can see what each reviewer caught. Sort by vote count
   descending, then severity, then file.

#### Retry trigger

Only findings with **`votes` ≥ majority** (i.e. ≥⌈M/2 + 1⌉: 2/3, 3/3, 2/2)
**and** severity `high` or `medium` trigger the retry cycle. 1/3 findings
appear in `{REVIEW_PATH}` as advisory noise but do not decrement the
retry budget or block progress. This is the whole point of the ensemble —
one reviewer's outlier opinion shouldn't stop the pipeline.

When any majority high/medium finding exists (or, in the non-escalated
solo-reviewer case, any 1/1 high/medium finding — solo mode had no
disagreement to reject on):

1. **Record implicated files.** Union the `file` field of every
   qualifying finding into a set `implicated_files`. This is the
   basis for early-halt in step 3.
2. **If retry budget > 0**, decrement and dispatch `flow:implementer` in
   **targeted mode** against the AC numbers implicated by the
   qualifying findings, as phase `wave.e.retry_{n}.implementer`:
   ```
   implementer \
     --spec {SPEC_PATH} \
     --standards .flow/{board-key}-standards.md \
     --mode targeted \
     --target-acs {comma-separated AC numbers} \
     --ticket {ticket}
   ```
3. **Early-halt check.** Compute `files_intersect =
   set(implementer.files_written) ∩ implicated_files`.
   - `files_intersect` empty → the fix did not touch anything the
     review flagged. Halt the retry loop. Emit `phase.end`
     `wave.e.retry_{n}.halted` with `{reason: "fix_no_op",
     implicated_files: [...], files_written: [...]}`. Log to
     `{LOG_PATH}`. Do NOT re-run the reviewer(s). The findings remain
     in `{REVIEW_PATH}` for human triage.
   - `files_intersect` non-empty → commit the fix as phase
     `wave.e.retry_{n}.commit` (`branch-manager --repo {codebase}
     --commit "{ticket}: address Wave E finding {round}"`), then re-run
     Wave E from Step 1 —
     including the escalation gate; a clean re-run's solo reviewer
     can end the loop early without another 3-way.
4. Repeat until budget is exhausted, no majority high/medium findings
   remain, or early-halt fires.

`low` severity findings are reported at every vote count but never trigger
a retry. The retry budget is **shared** with Wave D — total fix cycles
across both waves cap at `--retry-budget` (default 2).

### Wave F — Commit spec + code (local only)

Wave F commits what the run has written so far. Nothing is pushed here —
the only push Flow ever makes is the opt-in code push at Phase 5c,
and spec artifacts are never pushed at all. Which lanes run depends on
`SPEC_COMMIT_MODE` from pre-flight ("Spec path resolution"):

| `SPEC_COMMIT_MODE` | F1 — spec lane | F2 — consuming-repo lane |
|--------------------|----------------|--------------------------|
| `same-repo` (spec root inside the consuming repo) | Skipped (`reason: "same-repo"`) — two concurrent commits on one repo would race | One commit carrying the code **and** the spec files under `{CARD_ROOT}`. Runs under `--docs-only` too, carrying only the spec files |
| `separate` (spec root inside another git repo) | `branch-manager --repo {SPEC_ROOT}`, commit only, **never** `--push` | Code only; skipped under `--docs-only` |
| `none` (spec root not in a git repo) | Skipped (`reason: "no-git"`) | Code only; skipped under `--docs-only` |

In `separate` mode the two lanes target different repos and run
concurrently. F2 must land before Wave D: the implementation (Wave C)
and any Wave E fixes are still **uncommitted** in the consuming repo's
working tree, and Waves D and G diff `origin/{diff-branch}...HEAD`, which
only sees *committed* work.

```
# F1 — spec lane (separate mode only)
branch-manager \
  --repo {SPEC_ROOT} \
  --commit "{ticket}: spec pass {PASS_DIR}"

# F2 — consuming-repo lane
branch-manager \
  --repo {consuming codebase repo} \
  --commit "{ticket}: {card title}"        # docs-only, same-repo: "{ticket}: spec pass {PASS_DIR}"
```

`branch-manager` stages the target repo's changes and commits on its
current branch; it unstages telemetry `*.jsonl` files, which in any case
sit behind the telemetry folder's `.gitignore`. Results that are **not**
errors:

- `commit: "NOTHING_TO_COMMIT"` — the tree was clean. If F2 returns it
  on a spec-only / investigation pass, Wave D legitimately sees an empty
  diff and scores everything Manual.
- `commit: "NOT_A_GIT_REPO"` (`ok: true`) — the target is not a git
  repo; record `committed: false` and move on.

### Wave F join

Wait for the lanes that ran. Log each lane's status. A lane returning an
error is logged non-fatal and the pipeline continues; the uncommitted
files stay on disk for the developer.

Proceed to Wave D.

### Wave D — Acceptance Criteria verification (escalated 3-way — 1 verifier default, 3 on partial/fail)

**Skipped entirely under `--docs-only`** — the diff would contain only
docs and cannot verify code ACs. The ACs shipped through the original
PR's verification. Emit `phase.end` `wave.d.ac_verify` with
`{skipped: true, reason: "docs-only"}` and proceed to Wave G.
`{AC_PATH}` is not produced under docs-only; the Phase 8 AC tally reads
`— (docs-only)`.

**Escalation model.** Wave D dispatches **one verifier first**
and only escalates to the full 3-way majority-vote pattern when that
verifier reports any AC as `partial` or `fail`. ACs are usually less
ambiguous than code-review findings, so most passes land clean under a
single verifier; when a real failure surfaces, the full defensibility
of majority vote kicks in before the pipeline burns retry budget on a
fix.

#### Step 1 — Solo verifier

Dispatch the `flow:ac-verifier` agent as `r1` alone:

```
ac-verifier \
  --spec {SPEC_PATH} \
  --diff-range origin/{diff-branch}...HEAD \
  --branch {branch_name} \
  --ticket {ticket} \
  --decision-log {DECISION_PATH} \
  --reviewer-id r1 \
  --write {PASS_ROOT}/.verify/r1.json
```

If **every AC** in r1's verdicts is `pass` or `manual`, skip
escalation. Write the final `{AC_PATH}` directly from r1's payload
(with `votes: 1/1` on each AC's line). Emit `phase.end`
`wave.d.consolidate` with `{escalated: false, verifiers_returned: 1,
...}` and proceed to Wave G.

If r1 fails (`ok: false`), fall back to the 3-way pattern in step 2 —
we cannot decide on zero data.

#### Step 2 — Escalate on partial/fail

If r1 reports **any** AC as `partial` or `fail`, dispatch
`flow:ac-verifier` again as `r2` and `r3` concurrently (two Agent tool
calls in one message), identical inputs to r1 except `--reviewer-id`:

```
ac-verifier \
  --spec {SPEC_PATH} \
  --diff-range origin/{diff-branch}...HEAD \
  --branch {branch_name} \
  --ticket {ticket} \
  --decision-log {DECISION_PATH} \
  --reviewer-id r{2|3} \
  --write {PASS_ROOT}/.verify/r{2|3}.json
```

Wait for both to return. If either fails, continue with whoever
returned. If only r1 returned, fall back to r1's judgment alone with
`escalation_degenerated: true` in telemetry.

#### Consolidation

Merge the returned verdict sets into `{AC_PATH}`:

1. **Group by AC number.** Each AC has one, two, or three verdicts
   depending on how many verifiers returned: `pass`, `partial`, `fail`,
   or `manual`.
2. **Compute the AC's final verdict.**
   - **Non-escalated (1 verifier):** the verdict is r1's directly.
   - **Escalated (2–3 verifiers):** if ≥⌈M/2 + 1⌉ verifiers (2/3, 3/3,
     2/2) agree on `fail` or `partial`, that is the final. If ≥majority
     agree on `pass` or `manual`, that is the final. On a 3-way split
     (each verifier says something different — rare), the
     most-conservative verdict wins: `fail` > `partial` > `manual` >
     `pass`.
3. **Tag with vote count.** Each row in `{AC_PATH}` shows the verdict
   distribution (e.g. `AC 4 · fail (3/3)`, `AC 7 · partial (2/3, 1
   pass)`, `AC 1 · pass (1/1, no escalation)`) so the reader can see
   whether escalation happened.

#### Retry trigger

If any AC's final verdict is `fail` or `partial` **and** the shared
retry budget (from Wave E) is > 0:

1. **Record implicated files.** Union the `file` paths from each
   failing AC's `evidence` list into `implicated_files`. (Every
   ac-verifier verdict carries evidence as `path:line` entries per the
   agent contract; strip line numbers, dedupe.)
2. **Decrement the budget** and dispatch `flow:implementer` in
   **targeted mode** against the failing ACs, as phase
   `wave.d.retry_{n}.implementer`.
3. **Early-halt check.** Compute `files_intersect =
   set(implementer.files_written) ∩ implicated_files`.
   - `files_intersect` empty → the fix did not touch anything the
     verifier flagged. Halt the retry loop. Emit `phase.end`
     `wave.d.retry_{n}.halted` with `{reason: "fix_no_op",
     implicated_files: [...], files_written: [...]}`. Log to
     `{LOG_PATH}`. Do NOT re-run the verifier(s). The failing ACs
     remain in `{AC_PATH}` for human triage.
   - `files_intersect` non-empty → commit the fix as phase
     `wave.d.retry_{n}.commit` (`branch-manager --repo {codebase}
     --commit "{ticket}: address AC {n} verification feedback"`) so the
     re-verification diffs the
     corrected code, not the pre-fix state. Then re-run Wave D from
     Step 1 — including the escalation gate; a clean re-run's solo
     verifier can end the loop early without another 3-way.
4. Repeat until budget is exhausted, all AC final verdicts are `pass`
   / `manual`, or early-halt fires.

The `decision_log_coverage` block in each verifier's response is
**advisory only** — it surfaces ACs that have no matching decision-log
row but does not block the pipeline. Union the coverage gaps across
returned verifiers and append them to `{LOG_PATH}` so the user can
decide whether to back-fill the decision log.

`low` severity coverage gaps are reported but never trigger a retry.
The retry budget is **shared** with Wave E — total fix cycles across
Wave D + Wave E cap at `--retry-budget` (default 2).
