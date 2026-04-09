# USE syntax and caveats

This file distills the shared Exivity language reference into the parts that most often matter when ChatGPT writes or repairs USE code.

## Core syntax

- USE scripts live in `<basedir>/system/config/use/`.
- Each statement must be on a single line.
- Comments start with `#`.
- Variables use `${name}`.
- Buffers use `{buffer}`.
- Automatic variables include `${ARGC}`, `${ARG_N}`, `${HTTP_STATUS_CODE}`, `${YEAR}`, `${MONTH}`, `${DAY}`, `${SCRIPTNAME}`, and `${NEWLINE}`.

## Functions in USE

- USE functions use `@FUNCTION(...)` syntax.
- In `var` assignments, function calls must be parenthesized:
  - correct: `var year = (@SUBSTR(${date}, 1, 4))`
  - wrong: `var year = @SUBSTR(${date}, 1, 4)`
- In `if` expressions, functions can be used directly without extra parentheses.

## JSON handling

- Direct access: `$JSON{buffer}.[field]`
- Nested access: `$JSON{buffer}.[a].[b]`
- Iterator access inside foreach: `$JSON(item).[field]`
- Missing paths return `EXIVITY_NOT_FOUND`.

## Looping

- JSON loop pattern:
  `foreach $JSON{buffer}.[items] as item { ... }`
- Loop count is available as `${item.COUNT}`.

## CSV handling

- `csv label = filename`
- `csv add_headers label ...`
- `csv fix_headers label`
- `csv write_field` and `csv write_fields` are both valid.
- `csv close label`

## HTTP handling

- Common pattern:
  - `clear http_headers`
  - `set http_header "Accept: application/json"`
  - `buffer response = http GET "${url}"`
- Validate `${HTTP_STATUS_CODE}` after every request.
- Extract headers with `http get_header "HeaderName" as varName` when needed.

## Public and encrypted variables

- `public var` exposes a variable in the Exivity GUI.
- `public encrypt var` exposes and encrypts a secret.
- The encrypted value extends from the first non-whitespace character after `=` to end of line.
- Do not leave trailing spaces after encrypted plaintext values.
- Encrypted values are machine-specific.

## Supported functions

- USE only supports the following `@FUNCTION(...)` calls: `@MIN`, `@MAX`, `@ROUND`, `@CONCAT`, `@SUBSTR`, `@STRLEN`, `@PAD`, `@EXTRACT_BEFORE`, `@EXTRACT_AFTER`, `@CURDATE`, `@DATEADD`, `@DATEDIFF`, `@DTADD`, `@FILE_EXISTS`.
- There is **no** `@MATH` function. Arithmetic must be done via `var` expressions or operators:
  - Expression form: `var x = (${x} + 2)` — supports integer and floating point.
  - Operator form: `var x += 10` — integer only. Also `-=`, `*=`, `/=`, `%=`.

## Variables vs buffers

- Variables are referenced as `${name}`. The `.LENGTH` suffix (`${name.LENGTH}`) returns the string length and works **only on variables**.
- Buffers are referenced as `{name}`. There is no `.LENGTH`, `.SIZE`, or `.EXISTS` suffix for buffers.
- You **cannot** use `${buffername.LENGTH}` to check buffer size — that treats it as a variable, not a buffer, and will error with "Undefined variable" if the buffer name is not also a variable.

## Loop statement

- Syntax: `loop label [count] [timeout ms] { ... }`
- The loop automatically creates `${label.COUNT}` (starts at 1, increments each iteration).
- Use `exit_loop` to break out early.
- Both `count` and `timeout` are optional; omitting both creates an infinite loop.

## ODBC error handling

- A failed `buffer name = odbc_direct "query"` immediately sets a fatal error status (`S_ERROR`) and **terminates the script**. There is no way to catch, trap, or recover from an ODBC failure within a USE script.
- Unlike HTTP (which has `set http_retry_count` / `set http_retry_delay` for automatic retries), there is **no** `set odbc_retry_count` or `set odbc_retry_delay`. ODBC has no built-in retry mechanism.
- When the ODBC call fails, the buffer is never created. Attempting to reference a non-existent buffer (via `match`, `save`, `discard`, etc.) also causes `S_ERROR`.
- **Do not** attempt to wrap `odbc_direct` in a `loop` with `pause` for retry — the `S_ERROR` from the first failure kills the script before the loop can iterate.
- If ODBC retry is needed, it must happen **outside** the USE script (e.g. via a PowerShell/batch wrapper that re-invokes the extractor, or via Workflow scheduling with multiple runs).

## HTTP retry (built-in)

- `set http_retry_count N` — number of retries after initial attempt (default: 1, so 2 total attempts).
- `set http_retry_delay N` — delay in milliseconds between retries (default: 5000).
- These only apply to HTTP requests, **not** to ODBC.
- After HTTP failure you can still check `${HTTP_STATUS_CODE}` and branch — HTTP does not set `S_ERROR` on transport failure, it sets `${HTTP_STATUS_CODE}` to `-1`.

## Frequent failure modes

- Attempting multiline statements with `\`.
- Missing capture group in `match` regex.
- Forgetting parentheses around functions in `var` assignments.
- Comparing unquoted string variables inside `if` when values may contain parentheses.
- Forgetting to handle `EXIVITY_NOT_FOUND` for optional JSON fields.
- Using `@MATH` — this function does not exist. Use `var` arithmetic instead.
- Trying to retry ODBC calls in a loop — `S_ERROR` is fatal and terminates the script immediately.
- Confusing variable syntax `${x}` with buffer syntax `{x}` — they are different namespaces.
