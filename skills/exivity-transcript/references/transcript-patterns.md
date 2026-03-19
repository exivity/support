# Transcript transformation patterns

## Common task structure

### Clean and shape extracted data

1. `import` the extracted file.
2. `default dset` to the imported dataset.
3. Normalize headings or values.
4. Create missing business columns.
5. Compute derived values with `calculate` or `set`.
6. Filter or move subsets when required.
7. Export or finish.

### Enrichment + aggregation

1. Import the usage dataset.
2. Import or reference enrichment datasets.
3. Correlate metadata columns into the main dataset.
4. Repair missing values.
5. Aggregate on the correct business key.
6. Derive any post-aggregate measures such as averages using `EXIVITY_AGGR_COUNT`.

### Service generation

Use a `services { ... }` block after the dataset has the final usage, rate, instance, and categorization fields required for service definitions. Do not generate services too early while identifiers or rates are still unstable.

## Output choice

- Use `finish` when the goal is an RDF/report result.
- Use `export` when the goal is a reusable intermediate dataset.
- Use `finish source.alias` when multiple DSETs exist and only one should be emitted.

## Style guidance from Exivity materials

The public `exivity/templates` repository is described as a library of extractor (`.use`) and transformer (`.trs`) templates for integrating Exivity with many vendors. Use that as a style signal: build pragmatic, end-to-end Transcript tasks that follow actual integration flows instead of abstract ETL examples.

Useful prompt framing for this skill:

- “Write a Transcript task that consumes this extracted CSV and builds billable usage.”
- “Repair this transformer but preserve the business logic.”
- “Map and aggregate these columns into Exivity services.”
