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

### `set` value sources

- Literal string: `set col to "value"`
- Variable: `set col to "${var}"`
- **Another column (column-to-column copy): `set col as other_col`** (no brackets).
- `set col to [other_col]` is **wrong** — it stores the literal text `[other_col]` instead of copying the column value.

## Import patterns with `pattern enabled`

- Regex matching applies only to the **filename portion** of the import path.
- The **directory portion must be literal** — built from `${dataYear}`, `${dataMonth}`, etc.
- Example:
  ```trs
  var dir = "system/extracted/MySource/${dataYear}/${dataMonth}"
  import "${dir}/${dataDate}_[^_]+_MySource\\.csv" source mysrc alias data options {
      pattern enabled
  }
  ```
- Operator-supplied identifiers used in regex-matched filename segments (e.g. host alias matched by `[^_]+`) must not contain the regex separator character (typically underscore).

## Aggregate behavior

- `aggregate` reduces rows while preserving information according to chosen functions.
- `EXIVITY_AGGR_COUNT` is created automatically and is useful for post-aggregation averages.

## Correlation behavior

- `correlate ... using KeyColumn [assuming dset] [default value]`
- Prefer explicit default handling when lookups may be missing.
- A common cleanup step is:
  - correlate with `default EXIVITY_NOT_FOUND`
  - replace or set friendlier fallback values in a later `where` block.
- **When extending a `correlate` with a new field, propagate the change**:
  1. Add the field to the `correlate` field list.
  2. Add `match <field>` to every subsequent `aggregate` on that dset.
  3. Remove any later `create column <field>` that would reset it to empty.
- **Fallback to a related column when enrichment is empty**:
  ```trs
  where ([cluster_name] == "") { set cluster_name as cluster_uuid }
  where ([cluster_name] == "EXIVITY_NOT_FOUND") { set cluster_name as cluster_uuid }
  ```

## Services block

- The `services {}` block at the end of the transformer must reference the **final** column names — i.e. names after all `rename`, lowercase, or post-aggregate adjustments.
- When renaming `Usage` → `quantity`, also update `consumption_col = quantity`.
- When lowercasing operational columns, also update `unit_label_col`, `category_col`, `set_rate_using`, `set_cogs_using`, etc.
- A mismatched name here typically produces no error but no services either.

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
- **Treating import paths as regex.** With `pattern enabled`, only the filename portion is regex-matched — the directory portion must be a literal path. Build it from `${dataYear}` / `${dataMonth}` etc.
- **Parsing hour/date from `EXIVITY_FILE_NAME`** with nested `@EXTRACT_AFTER` / `@EXTRACT_BEFORE` on underscores. This breaks as soon as another filename segment contains an underscore. Use hourly-stamped imports + aggregation instead, or have the extractor emit an explicit `hour` column.
- **`set col to [other_col]`** — this stores the literal string `[other_col]`, not the column value. The correct form for column-to-column copy is `set col as other_col`.
- **Extending a lookup without updating downstream aggregate.** If you add a field to a `correlate`, every later `aggregate` on that dset must include `match <field>`, otherwise the field is dropped.
- **`services {}` referencing pre-rename column names.** After renaming `Usage` → `quantity` or lowercasing columns, the `services` block's `consumption_col`, `unit_label_col`, `category_col` etc. must point at the new names.
- **Forcing an enriched column blank with a late `create column`** after a `correlate` already populated it.
