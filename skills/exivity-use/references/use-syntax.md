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

## Frequent failure modes

- Attempting multiline statements with `\`.
- Missing capture group in `match` regex.
- Forgetting parentheses around functions in `var` assignments.
- Comparing unquoted string variables inside `if` when values may contain parentheses.
- Forgetting to handle `EXIVITY_NOT_FOUND` for optional JSON fields.
