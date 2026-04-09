# USE extractor patterns

## Common extractor structure

### REST + token auth

1. Validate `${ARGC}` and required arguments.
2. Parse dates with `@SUBSTR` if the input is `yyyyMMdd`.
3. Declare public variables for base URLs, tenant IDs, usernames, client IDs, or API keys.
4. Authenticate first and parse token values from JSON or headers.
5. Reset headers before each logically distinct request.
6. Fetch the payload.
7. Fail fast on unexpected HTTP status.
8. Iterate with `foreach`.
9. Write CSV rows.
10. Close CSV, optionally `save` to final nested path, discard buffers, terminate.

## Error-handling pattern

### HTTP errors

Use this whenever the user asks for strict behavior:

```use
buffer response = http GET "${url}"
if (${HTTP_STATUS_CODE} !~ /200|202/) {
    print "ERROR: HTTP ${HTTP_STATUS_CODE} from ${url}"
    discard {response}
    terminate with error
}
```

HTTP supports built-in retry via `set http_retry_count` and `set http_retry_delay` (milliseconds). After all retries are exhausted, `${HTTP_STATUS_CODE}` is `-1` on transport failure — the script can still branch on this.

### ODBC errors

ODBC errors are **fatal and immediate** — a failed `buffer name = odbc_direct "query"` terminates the script with `S_ERROR`. There is:

- No ODBC status variable (unlike `${HTTP_STATUS_CODE}` for HTTP).
- No `set odbc_retry_count` or `set odbc_retry_delay`.
- No way to catch the error inside a `loop` or `if` block.
- No way to check whether a buffer was created after an ODBC call (the script is already dead).

**Never** generate a retry loop around `odbc_direct` — it cannot work. If the user asks for ODBC retry, explain the limitation and suggest retrying outside the USE script (e.g. PowerShell wrapper, Exivity Workflow scheduling).

## Auth patterns to prefer

- Bearer token from JSON token endpoint.
- Basic auth via base64 only when the API genuinely uses basic auth.
- `public encrypt var` for secrets the operator should edit.
- `environment name` when the same extractor should run in multiple customer environments.

## Path conventions

- Extracted files typically belong under `system/extracted/<source>/<yyyy>/<MM>/<dd>_<source>.csv`.
- Temporary output in `exported/` is acceptable when a direct CSV target path is awkward.

## Template guidance from Exivity materials

The public `exivity/templates` repository contains both extractor (`.use`) and transformer (`.trs`) templates and is explicitly described as a library for integrating Exivity with many usage APIs. Use that repository as a style signal: prefer practical, integration-ready scripts over abstract examples.

Useful prompt framing for this skill:

- “Write a complete USE extractor for this API.”
- “Refactor this example into valid USE syntax.”
- “Repair this extractor but keep its original logic.”
