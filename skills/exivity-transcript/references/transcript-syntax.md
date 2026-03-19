# Transcript syntax and caveats

This file distills the shared Exivity language reference into the parts that most often matter when ChatGPT writes or repairs Transcript code.

## Core syntax

- Transcript tasks live in `system/config/transcript/`.
- Each statement must be on a single line.
- Comments start with `#`.
- Variables use `${name}`.
- Column references use `[ColumnName]` or fully qualified `source.alias.ColumnName`.
- Common automatic variables include `${dataDate}`, `${dataYear}`, `${dataMonth}`, `${dataDay}`, `${homeDir}`, and `${exportDir}`.

## DSET handling

- Import syntax usually creates DSETs as `source.alias`.
- Set `default dset source.alias` once a main dataset is known.
- Use fully qualified references when more than one DSET is active.

## Functions and expressions

- Transcript functions use `@FUNCTION(...)`.
- In `var` assignments, bare `@FUNCTION(...)` is valid.
- In `set` expressions, column values are usually referenced as `[ColumnName]`.

## Important statements

- `import`
- `default dset`
- `create`
- `set`
- `calculate`
- `rename`
- `replace`
- `correlate`
- `aggregate`
- `services`
- `export`
- `finish`

## Aggregate behavior

- `aggregate` reduces rows while preserving information according to chosen functions.
- `EXIVITY_AGGR_COUNT` is created automatically and is useful for post-aggregation averages.

## Correlation behavior

- `correlate ... using KeyColumn [assuming dset] [default value]`
- Prefer explicit default handling when lookups may be missing.
- A common cleanup step is:
  - correlate with `default EXIVITY_NOT_FOUND`
  - replace or set friendlier fallback values in a later `where` block.

## Where-block limits

Inside `where`, keep to supported statements such as:

- `set`
- `calculate`
- `replace`
- `round`
- `split`
- `timerender`
- `copy rows`
- `move rows`
- `delete rows`
- `create mergedcolumn`

## Frequent failure modes

- Missing `default dset` when many unqualified column references are used.
- Aggregating too early and losing detail needed for later calculations.
- Using unsupported statements inside a `where` block.
- Mixing up `${variable}` syntax and `[ColumnName]` syntax.
- Forgetting to handle missing correlations.
