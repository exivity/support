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

Use this whenever the user asks for strict behavior:

```use
buffer response = http GET "${url}"
if (${HTTP_STATUS_CODE} !~ /200|202/) {
    print "ERROR: HTTP ${HTTP_STATUS_CODE} from ${url}"
    discard {response}
    terminate with error
}
```

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
