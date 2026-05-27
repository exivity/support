---
name: exivity-use
description: create, review, debug, and explain exivity use extractor scripts for rest apis, files, web pages, and odbc databases. use when a user asks for a .use extractor, wants help fixing http/json/csv/odbc logic, needs exivity-specific syntax, or wants generic integration code converted into correct use style. especially relevant for exivity data pipeline work involving public or encrypted variables, date parsing, response validation, json iteration, csv output, and saving extracted data to system/extracted.
---

# Exivity USE

Use this skill to produce real USE scripts, not pseudocode. Favor complete extractor scripts that can be pasted into `system/config/use/` with only endpoint names, credentials, SQL, or field names adjusted.

## Working style

1. Identify the source type: REST API, local file, web page, or ODBC.
2. Identify the runtime inputs and operator-editable settings.
3. Build the script in valid USE syntax with one statement per line.
4. Add Exivity-native handling for auth, HTTP headers, JSON access, loops, CSV output, and error termination.
5. When details are missing, make the smallest practical assumption, mark it with a comment, and keep the script executable.

## Non-negotiable USE rules

- Keep every statement on a single line. Do not use backslash as a line continuation.
- In `var` assignments, wrap USE function calls in parentheses: `var year = (@SUBSTR(${date}, 1, 4))`.
- In `if` expressions, quote string-valued variables when special characters may appear: `if ("${name}" == "")`.
- For `match`, always include at least one capture group in the regex.
- Treat missing JSON paths as `EXIVITY_NOT_FOUND` and handle optional fields explicitly.
- **Optional JSON arrays must be probed before `foreach`.** A `foreach` over a missing path raises a fatal "JSON path becomes invalid" error and halts the script — it does **not** silently iterate zero times. Read the path into a `var` first and only enter the `foreach` when it is not `EXIVITY_NOT_FOUND`.
- Use `public var` for operator-editable settings and `public encrypt var` for secrets that should appear in the GUI.
- **Prefer plain `public var` for secrets sourced from environment variables.** `public encrypt var` can corrupt externally-supplied secrets in some Exivity installs (the value gets re-encrypted machine-specifically and the wire value becomes unusable). When the secret comes from a `${ENV_VAR}` reference, default to `public var` unless the operator explicitly wants GUI-encrypted storage.
- Remember that `encrypt` and `encrypted` are preprocessor directives and encrypted values are machine-specific.
- Prefer `clear http_headers` before setting a fresh header set for a different request.
- Validate HTTP responses immediately after each request. If the task requires strict failure handling, terminate with error on non-success status.
- **`set http_retry_count` / `set http_retry_delay` only retry on transport failure (`${HTTP_STATUS_CODE} == -1`), NOT on application-level statuses like 429 / 500 / 503.** To handle rate limiting or server errors, hand-roll a retry loop around the request and branch on `${HTTP_STATUS_CODE}` explicitly. Expose retry knobs as `public var` (e.g. `retry_count`, `retry_delay_ms`) so operators can tune.
- **Expose operationally-tunable HTTP behavior as `public var`**: page size, retry count, retry delay, timeouts, granularity (`daily`/`hourly`), and any optional inclusion switches. Hard-coded values force script edits for routine tuning.

### Strict function and syntax rules

- The **only** supported `@FUNCTION` calls are: `@MIN`, `@MAX`, `@ROUND`, `@CONCAT`, `@SUBSTR`, `@STRLEN`, `@PAD`, `@EXTRACT_BEFORE`, `@EXTRACT_AFTER`, `@CURDATE`, `@DATEADD`, `@DATEDIFF`, `@DTADD`, `@FILE_EXISTS`. **Never** use `@MATH` or any other function not in this list — they do not exist.
- For arithmetic, use `var` expressions: `var x = (${x} + 2)` (integer and float) or operators: `var x += 10` (integer only, also `-=`, `*=`, `/=`, `%=`).
- Variables use `${name}` syntax. Buffers use `{name}` syntax. These are **different namespaces** — never confuse them. The `.LENGTH` suffix only works on variables, not buffers.
- `loop label [count] [timeout ms] { ... }` auto-creates `${label.COUNT}` — no manual counter needed.

### ODBC limitations

- A failed `buffer name = odbc_direct "query"` **immediately terminates the script**. There is no way to catch, trap, or recover from an ODBC failure in USE.
- There is **no** `set odbc_retry_count` or `set odbc_retry_delay` — ODBC has no retry mechanism (unlike HTTP which has `set http_retry_count` / `set http_retry_delay`).
- **Never** generate a retry/wait loop around `odbc_direct` — the fatal error kills the script before the loop can iterate. If the user asks for ODBC retry, explain the limitation and suggest retrying outside USE (PowerShell wrapper, Workflow scheduling, etc.).

## Preferred output patterns

### REST extractors

Default to this shape unless the user asks for something else:

1. Validate arguments.
2. Parse date parts with `@SUBSTR` when the script uses `yyyyMMdd` input.
3. Declare public variables for URLs and credentials.
4. Authenticate and extract token/header values.
5. Call data endpoints.
6. Loop over JSON or XML payloads with `foreach`.
7. Write CSV output using Exivity CSV commands.
8. Save the result under the expected `system/extracted/...` path.
9. Discard large buffers and terminate cleanly.

### ODBC extractors

Prefer:

- `set odbc_connect "..."` plus `buffer result = odbc_direct "${query}"` for direct connection strings.
- DSN form only when the user explicitly wants DSN-based access.
- Clear separation between query construction, query execution, and file save steps.

### CSV writing

- Prefer repeated `csv add_headers` or repeated `csv write_field` lines instead of trying to split a single statement over multiple lines.
- Use `csv fix_headers` after defining headers.
- If nested target directories may not exist, it is acceptable to write to `exported/` first and then `save` a file buffer into the final `system/extracted/...` destination.

## What to include in answers

When generating or repairing a USE script:

- Return a full `.use` script in a code block.
- Keep comments brief and practical.
- Preserve Exivity terminology such as buffer, foreach, environment, public variable, and extracted path.
- Explain only the tricky parts after the script, such as auth flow, JSON shape assumptions, or places the user must substitute values.

When reviewing a USE script:

- Call out exact syntax problems first.
- Then fix Exivity-specific logic issues such as multiline statements, incorrect function syntax, missing capture groups, unsafe `if` comparisons, or missing HTTP status validation.
- Prefer concrete corrected snippets over generic advice.

## Example user requests this skill should handle

- “Write a USE extractor for this REST API and save the csv into system/extracted.”
- “Convert this Python API integration into USE.”
- “Fix this extractor; Exivity says unbalanced parentheses.”
- “Review my ODBC extractor and make the variables public.”
- “Generate a USE script that authenticates, loops through JSON, and writes all fields to csv.”

## References to consult

- Read `references/use-syntax.md` for the distilled USE rules and gotchas.
- Read `references/use-patterns.md` for extractor patterns and repo/template guidance.
