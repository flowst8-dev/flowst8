---
name: datapoints
description: Flow subcommand. Catalogs every code path in the consuming codebase that writes (INSERT/UPDATE/DELETE/MERGE/UPSERT) to one or more named database tables — raw SQL in any language, query builders, ORM model writes and stored-procedure calls — and follows import/include chains up to the entry point (route, controller, handler, page, CLI command or job) that a user or system triggers. Produces a reviewer-ready markdown table so you can trace a user action to the exact columns written. Run as /flow:datapoints --tables name1,name2 (or --endpoint path/to/file for reverse lookup).
argument-hint: "--tables name1,name2[,...] | --endpoint path/to/file [--schema-glob \"db/**/*.sql\"] [--save-to-spec | --output path.md]"
disable-model-invocation: true
---

# /flow:datapoints — Data write path catalog

Arguments: `$ARGUMENTS`

**Paths.** `${CLAUDE_PLUGIN_ROOT}` is the flow plugin root. This skill is
self-contained — no run-pipeline pre-flight, no spec required, no telemetry.
It is read-only against the consuming codebase: it searches and reads, and
writes only its own report.

The skill is language-agnostic. It recognises writes in four shapes, and a
single codebase usually mixes several of them:

- **Raw SQL** — DML in string literals, template strings, heredocs,
  `.sql` files, and markup-embedded query tags (e.g. ColdFusion `<cfquery>`,
  JSP/ASP inline SQL).
- **Query builders** — fluent table-first APIs (Knex, Laravel `DB::table`,
  Drizzle, jOOQ, GORM, SQLAlchemy Core, Dapper/ADO.NET command text).
- **ORM model writes** — `save` / `create` / `update` / `delete` on a model
  class that maps to the target table (ActiveRecord, Django, SQLAlchemy ORM,
  Prisma, TypeORM, Sequelize, Entity Framework, Hibernate/JPA, Eloquent and
  similar).
- **Stored procedures and database code** — application calls to a proc
  whose body writes to the table, plus procs and triggers in the repo's DDL
  that write to it.

## 1. Parse arguments

Split `$ARGUMENTS` on whitespace, keeping text inside double quotation marks together. Recognise these flags:

| Flag | Default | Meaning |
|---|---|---|
| `--tables name1,name2[,…]` | — | **Forward lookup**: table names (comma-separated, spaces OK inside quotation marks, each name case-insensitive, optionally schema-qualified like `public.users`). At least one of `--tables` or `--endpoint` is required. |
| `--endpoint path/to/file` | — | **Reverse lookup**: any source file (`.ts`, `.py`, `.rb`, `.java`, `.cs`, `.php`, `.go`, `.cfm`, `.sql`, …), relative to the repo root or absolute. Lists every table that file — and everything it imports, includes or calls — writes to. |
| `--repo-path /abs/path` | `git rev-parse --show-toplevel` of the current working directory | Repo root to search. The skill searches recursively from here. |
| `--schema-glob "db/**/*.sql"` | `**/*.sql` | Where the repo keeps DDL, migrations and stored-procedure source. Used to resolve proc bodies and find database-side writers. Relative to `--repo-path`. |
| `--save-to-spec` | off | Save to `{CARD_ROOT}/{PASS_DIR}/data-write-paths.md` (resolve via `${CLAUDE_PLUGIN_ROOT}/skills/run/references/preflight.md` → "Spec path resolution", with `PASS_DIR` = the latest existing pass). Requires a Jira-style ticket key as the current branch's prefix or segment (e.g. `feature/PROJ-123-email-opt-in`). |
| `--output path.md` | off | Save to an explicit path (overrides `--save-to-spec`). Absolute or relative to cwd. |
| `--op INSERT,UPDATE,DELETE,MERGE,UPSERT` | all five | Filter the output to specific operations. Comma-separated. |
| `--format markdown\|json` | `markdown` | Output format. JSON produces a structured object for piping. |
| `--force` | off | Required to proceed when more than 10 tables are requested. |

**Validation.**

- If neither `--tables` nor `--endpoint` is provided, stop with: `⚠️  /flow:datapoints requires --tables name1[,name2,…] or --endpoint path/to/file`.
- If `--tables` and `--endpoint` are both provided, run the reverse lookup from the endpoint and keep only writes to the named tables.
- If `--endpoint` does not exist, stop with: `⚠️  --endpoint not found: {path}`.
- Normalise table names case-insensitively for searching but preserve the user's casing in the output.

**Search scope.** Search every text file under `{REPO_PATH}` except
dependency, build and tooling output: `.git/`, `node_modules/`, `vendor/`,
`dist/`, `build/`, `out/`, `target/`, `bin/`, `obj/`, `.venv/`, `venv/`,
`__pycache__/`, `.next/`, `coverage/`, minified bundles (`*.min.js`),
lockfiles, `.flow/`, and the resolved spec root when it sits inside the
repo. Test files and fixtures are searched but labelled `(test)` in the
Action column so reviewers can filter them out.

## 2. Map models to tables

Before searching, build an **alias set** for each target table: the bare
name, its schema-qualified and delimited forms (`users`, `public.users`,
`dbo.users`, `"users"`, `[users]`, `` `users` ``), and every ORM model or
table object that maps to it.

Find model mappings by searching for explicit table declarations first,
then falling back to each framework's naming convention:

| Ecosystem | Explicit mapping | Convention when no mapping is declared |
|---|---|---|
| ActiveRecord (Ruby) | `self.table_name = "users"` | class `User < ApplicationRecord` → snake_case plural (`users`) |
| Django | `class Meta: db_table = "users"` | `{app_label}_{modelname}` lowercased (`accounts_userpreference`) |
| SQLAlchemy | `__tablename__ = "users"`, `Table("users", metadata, …)` | none — a mapping is always explicit |
| Prisma | `@@map("users")` inside `model User { … }` | the model name as written (`User`) |
| TypeORM | `@Entity("users")`, `@Entity({ name: "users" })` | class name through the configured naming strategy |
| Sequelize | `tableName: "users"` in `define` / `Model.init` options | pluralised model name (`Users`) unless `freezeTableName` |
| Entity Framework | `[Table("users")]`, `.ToTable("users")` in `OnModelCreating` | the `DbSet<User>` property name (`Users`) |
| Hibernate / JPA | `@Table(name = "users")` | the `@Entity` class name |
| Eloquent (Laravel) | `protected $table = 'users';` | snake_case plural of the class (`users`) |
| Drizzle | `pgTable("users", …)` / `mysqlTable` / `sqliteTable` bound to a variable | none — a mapping is always explicit |
| GORM (Go) | `func (User) TableName() string { return "users" }` | snake_case plural of the struct (`users`) |

An explicit mapping always beats convention. When a mapping is inferred by
convention, say so in the output (`User → users (by convention)`), because
naming strategies are often customised. Match conventions
case-insensitively and treat `user_preferences`, `UserPreferences` and
`userpreferences` as the same table name.

## 3. Discover writes

For each table, run the Grep tool against `{REPO_PATH}` with `-i: true`,
first with `output_mode: files_with_matches`, then with `output_mode: content`
and `-C 15` on each matching file to capture the full statement or call.
Below, `{T}` is any member of the table's alias set (regex-escaped, with an
optional schema prefix `([\w"\[\]`]+\.)?` and optional identifier delimiters).

**3a. Raw SQL** (any file type, including `.sql`):

```
INSERT\s+(INTO\s+)?{T}\b
UPDATE\s+{T}\b
DELETE\s+(FROM\s+)?{T}\b
MERGE\s+(INTO\s+)?{T}\b
(UPSERT|REPLACE)\s+INTO\s+{T}\b
```

Some dialects name the target through an alias (`UPDATE u SET … FROM users u`,
`DELETE u FROM users u JOIN …`). When an UPDATE or DELETE target is a short
identifier, resolve it against the statement's `FROM` clause before ruling
the file out. Classify `INSERT … ON CONFLICT … DO UPDATE` and `INSERT … ON DUPLICATE KEY
UPDATE` as `UPSERT`. SQL split across concatenated strings or lines will
not match one regex — when a file references the table name near a DML
keyword, read the surrounding code and reassemble the statement before
deciding.

**3b. Query builders** — a table-first call followed by a write method:

```
(knex|db|trx|this\.db)\(\s*['"]{T}['"]\s*\)[\s\S]{0,200}?\.(insert|update|del|delete|upsert|merge)\b
DB::table\(\s*['"]{T}['"]\s*\)[\s\S]{0,200}?->(insert|insertOrIgnore|update|updateOrInsert|upsert|delete)\b
\.(insert|update|delete)\(\s*{TableObject}\s*\)          # Drizzle, SQLAlchemy Core
\.(insertInto|update|deleteFrom|mergeInto)\(\s*{TableObject}\b   # jOOQ
\.Table\(\s*"{T}"\s*\)[\s\S]{0,200}?\.(Create|Save|Update|Updates|Delete)\b   # GORM
```

`{TableObject}` is the variable or constant bound to the table in step 2
(e.g. `users` from `pgTable("users", …)`, `USERS` in jOOQ).

**3c. ORM model writes** — for each model mapped to the table in step 2,
search for its write calls:

| Ecosystem | Write calls |
|---|---|
| ActiveRecord | `User.create`, `.insert_all`, `.upsert_all`, `.update`, `.update_all`, `.destroy`, `.delete_all`; `record.save` / `update` / `destroy` |
| Django | `User.objects.create` / `bulk_create` / `update` / `update_or_create` / `get_or_create` / `delete`; `instance.save()` / `delete()` |
| SQLAlchemy ORM | `session.add(User(…))`, `session.merge`, `session.delete`, `session.execute(insert(User) / update(User) / delete(User))` |
| Prisma | `prisma.user.create` / `createMany` / `update` / `updateMany` / `upsert` / `delete` / `deleteMany` |
| TypeORM | `getRepository(User)` or an injected `Repository<User>` → `.save` / `.insert` / `.update` / `.upsert` / `.delete` / `.remove`; `manager.save(User, …)` |
| Sequelize | `User.create` / `bulkCreate` / `update` / `upsert` / `destroy`; `instance.save()` / `destroy()` |
| Entity Framework | `context.Users.Add` / `AddRange` / `Update` / `Remove` / `RemoveRange`, then `SaveChanges` / `SaveChangesAsync`; `ExecuteUpdate` / `ExecuteDelete` |
| Hibernate / JPA | `entityManager.persist` / `merge` / `remove`; Spring Data `userRepository.save` / `saveAll` / `delete*` |
| Eloquent | `User::create` / `insert` / `update` / `upsert` / `updateOrCreate` / `destroy`; `$user->save()` / `update()` / `delete()` |

Calls on a class or a typed repository are confirmed writes. Calls on an
instance (`record.save()`) are only confirmed when the variable's type can
be resolved from nearby code — its constructor, a type annotation, a
repository generic, or the query that loaded it. List anything you cannot
resolve under **Unresolved candidates** instead of guessing.

**3d. Extract** for every confirmed write:

- The **operation** — `INSERT`, `UPDATE`, `DELETE`, `MERGE` or `UPSERT`
  (ORM `create`/`add`/`persist` → INSERT, `update`/dirty `save` → UPDATE,
  `delete`/`destroy`/`remove` → DELETE, `upsert`/`update_or_create`/`merge`
  → UPSERT; a `save` that may insert or update is `UPSERT` unless context
  settles it).
- The **target table** as written, including any schema prefix.
- The **column list** — for INSERT, the column list and the matching
  `VALUES (…)` or `SELECT`; for UPDATE, the `SET col = value` pairs; for
  DELETE, no columns, just the `WHERE` clause. For ORM and query-builder
  calls, the keys of the object, kwargs or setters passed; when a whole
  entity is saved, the fields assigned in the same function, or
  `(all mapped fields of {Model})` when they cannot be narrowed.
- The **mechanism** — `sql`, `query_builder`, `orm` or `stored_proc` —
  and, for ORM writes, the model name.

## 4. Follow stored-procedure calls

For each file found in step 3, and for every file in the reverse lookup's
reach, also search for stored-procedure call sites:

```
\b(EXEC|EXECUTE)\s+(\[?\w+\]?\.)?\[?(\w+)\]?
\bCALL\s+(\w+\.)?(\w+)\s*\(
\{\s*call\s+(\w+)                              # JDBC escape syntax
callproc\(\s*['"](\w+)['"]                     # Python DB-API
CommandType\.StoredProcedure                   # ADO.NET — read the CommandText / SqlCommand name nearby
@Procedure|createStoredProcedureQuery\(\s*"(\w+)"   # JPA
<cfstoredproc\s+[^>]*procedure\s*=\s*["']([^"']+)["']   # ColdFusion
```

For each unique procedure name:

1. Search the files matched by `--schema-glob` (default `**/*.sql`) for its
   definition: `CREATE [OR REPLACE | OR ALTER] PROC[EDURE] [schema.]{name}`
   or `ALTER PROC[EDURE] [schema.]{name}`. If several definitions exist
   (environment folders, a migration history), use the latest one — the
   highest-ordered migration, otherwise the most recently modified file —
   and note the others as `also defined in {path}, {path}` for
   verification.
2. Search the proc body for the step 3a patterns against each target
   table. Follow `EXEC` / `CALL` inside the body to nested procs, up to
   three levels.
3. For each hit, record the calling file, the proc name, the op and
   columns inside the proc, and a chain such as
   `src/api/saveProfile.ts → CALL save_user_profile → db/procs/save_user_profile.sql`.

If the proc body isn't in the repo (third-party, legacy or DBA-owned
procs), still list the call and write
`(proc body not found under {schema-glob}; verify manually)` in the
columns cell.

## 5. Follow chains to an entry point

A write deep inside a helper means little on its own. From each file and
function containing a write, walk callers upward until you reach an
**entry point** — something a user, client or scheduler triggers:

- **Routes and controllers** — Express/Fastify/Koa route registrations,
  Next.js `pages/api/**` and `app/**/route.ts`, server actions, Django
  `urls.py` views, Rails `routes.rb` + controllers, Flask/FastAPI
  decorators, Spring `@*Mapping`, ASP.NET controller actions, Laravel
  routes, GraphQL resolvers and mutations.
- **Pages and form handlers** — server-rendered pages that execute on
  request (`.php`, `.cfm`, `.jsp`, `.aspx`, `.erb`), form `action` targets.
- **CLI commands, scheduled jobs and queue workers** — cron entries,
  job classes, message consumers, management commands, rake tasks.
- **Migrations and seeds** — label them as such; they are writers, but not
  user actions.

Walk callers through whatever the language uses to connect files:
`import` / `require` / `from … import`, `using` / namespaces,
`include` / `require_once`, ColdFusion `<cfinclude template="…">` and
`createObject("component", …)`, dependency-injected services, and plain
function-name references. Stop after six hops; a chain that reaches the
limit ends with `…` and the Action reads `(entry point not reached)`.
One write reachable from several entry points gets one row per entry
point.

Infer the **user-visible action** from, in order: the route's method and
path (`POST /api/profile`), the UI that calls it (a component posting to
that path), the entry file or handler name (`src/api/saveProfile.ts` →
"User saves profile settings"), doc comments, and the form fields or
request body read on the way in. A file that is clearly an internal helper
is labelled `(internal helper, called by {parent action})` and attributed
to the parent action when traceable.

**Reverse lookup (`--endpoint`).** Start at the endpoint file and walk the
other direction: everything it imports, includes or calls, to the same
six-hop limit, collecting every write from step 3 and every proc from
step 4. Group the results by table. The endpoint itself is the entry for
every row.

## 6. Find database-side writers without an app caller

For the forward lookup only, also search the `--schema-glob` files
directly for the step 3a patterns on each target table: procs, functions
and triggers (`CREATE TRIGGER … ON {table}` or on another table, whose body
writes to the target). Any that **no application call site found in steps
3–5** reaches go in a separate
`### Writes from database code (no application caller found)` sub-section
under the table, with the source path and the note
`(no application caller found; may be invoked by a trigger, scheduler, batch job, or a system outside this repo)`
in the Action column.

## 7. Build output

### Markdown format (default)

```markdown
# Data Write Paths

Scope: {list of target tables, or "all tables written by {endpoint}"}
Repo: {REPO_PATH}
Schema glob: {schema-glob}
Generated: {YYYY-MM-DD HH:MM} by /flow:datapoints

## Model mappings

- `{Model}` → `{table}` ({explicit in path:line | by convention})

## 1. Writes to `{table}`

| Action | Entry + chain | Op | Columns / Data saved |
|---|---|---|---|
| {action} | {entry} [→ {file}] [→ {Model}.{method} \| CALL {proc}] | {op} | {col list} |
| … |

### Writes from database code (no application caller found)

| Action | Source | Op | Columns / Data saved |
|---|---|---|---|

(Repeat per target table.)

## Unresolved candidates

- {path:line} — `{call}`: {why it could not be confirmed}

## Observations

- {Tables with zero writers}
- {Tables written only through stored procs or triggers}
- {Files or actions that write to several target tables}
- {Model mappings inferred by convention that a reviewer should confirm}
- {With --endpoint, a summary of that endpoint's full write surface}
```

### JSON format (`--format json`)

```json
{
  "generated_at": "2026-10-15T12:34:56Z",
  "repo_path": "/abs/path",
  "schema_glob": "**/*.sql",
  "tables": ["users", "user_preferences"],
  "endpoint_filter": null,
  "model_mappings": [
    {"model": "UserPreference", "table": "user_preferences", "source": "prisma/schema.prisma:42", "by_convention": false}
  ],
  "writes": [
    {
      "table": "user_preferences",
      "action": "User saves profile settings (POST /api/profile)",
      "entry": "src/api/saveProfile.ts",
      "chain": ["src/api/saveProfile.ts", "src/services/profileService.ts"],
      "mechanism": "orm",
      "model": "UserPreference",
      "stored_proc": null,
      "op": "UPSERT",
      "columns": [
        {"name": "user_id", "value": "session.userId"},
        {"name": "email_opt_in", "value": "body.emailOptIn"},
        {"name": "updated_at", "value": "now()"}
      ],
      "where": "user_id = ?"
    }
  ],
  "unresolved_candidates": [
    {"location": "src/jobs/syncUsers.ts:88", "call": "record.save()", "reason": "type of record not resolvable"}
  ]
}
```

`mechanism` is one of `sql`, `query_builder`, `orm`, `stored_proc` or
`db_code` (a proc or trigger with no application caller). `model` is
`null` unless `mechanism` is `orm`; `stored_proc` is `null` unless the
write happens inside a proc.

## 8. Output location

- **Default:** print to chat.
- **`--save-to-spec`:** resolve `{CARD_ROOT}` and the latest `{PASS_DIR}` via `${CLAUDE_PLUGIN_ROOT}/skills/run/references/preflight.md` → "Spec path resolution". Write to `{CARD_ROOT}/{PASS_DIR}/data-write-paths.md`. If the file already exists, overwrite it silently (regenerating is cheap). If the ticket has no pass folder yet, stop with `⚠️  No pass folder for {ticket} — run /flow:run {ticket} first, or use --output.` Nothing is committed.
- **`--output /path/to/file.md`:** write to the explicit path. If the parent directory does not exist, hard-fail with `⚠️  --output parent directory does not exist: {dir}`.

## 9. Scoping and performance

- A forward lookup across three tables in a mid-sized codebase typically touches 20–60 files and a handful of procs.
- If the user supplies more than 10 tables, warn: `⚠️  {N} tables requested. This may be slow and produce a very large output. Continue? (confirm by re-running with --force)`. Require `--force` to proceed.
- All searching is direct Grep / Glob / Read in the main conversation. Do not dispatch sub-agents.

## 10. Examples

```
# Forward lookup across two tables, print to chat
/flow:datapoints --tables users,user_preferences

# Only inserts and upserts, saved to the current spec pass
/flow:datapoints --tables user_preferences --op INSERT,UPSERT --save-to-spec

# Reverse lookup: every table one endpoint writes to
/flow:datapoints --endpoint src/api/saveProfile.ts

# Scope a forward lookup to one endpoint
/flow:datapoints --tables users --endpoint src/api/saveProfile.ts

# Point proc resolution at the repo's DDL folder
/flow:datapoints --tables users --schema-glob "db/**/*.sql"

# JSON for piping / further processing
/flow:datapoints --tables users --format json --output /tmp/writes.json
```

## 11. Non-goals

- **No "formerly wrote" callouts.** It does not compare the branch against the base branch to surface writes a change removed.
- **No permission or role analysis.** Who can trigger each action is out of scope.
- **No query performance analysis.** Table hints, locking, transaction wrapping and index usage are not inspected.
- **No cross-table dependency graph.** Tables written together are listed per writer, not joined into a graph.
- **No runtime tracing.** Dynamically built table names (`INSERT INTO ${table}`), reflection and metaprogrammed models are reported under Unresolved candidates, never guessed.

## 12. Error handling

- Files that fail to parse (unbalanced markup, syntax errors) — ignore and continue; this skill is read-only searching.
- Binary, generated or minified files — skip.
- Missing proc source — surface it with the `(proc body not found …)` note; don't block.
- Zero matches — produce the table heading with `_No writes found._` so the user knows the search ran.
- Any flag parse failure — stop with a specific error message naming the offending flag.
