---
name: build-config
description: "Use when asked to build or regenerate a Scarab config from a sample JSON and a base config. Trigger phrases: build-config, generate config, update sandbox config, infer table mapping, json to config mapping."
---

# Build Config

## Goal
Generate or update a Scarab config file using:
1. A sample JSON input file (schema source)
2. A base config file (paths and operational defaults)

This skill is generic and not restricted to appAnalise.

## Required inputs
1. Target config path to edit (for example [tests/sandbox/config.json](tests/sandbox/config.json))
2. Sample JSON path (any representative file)
3. Optional base config path to preserve defaults

If paths are not explicit, infer them from user request and current workspace context.

## Mapping rules (general approach)
Use these rules to infer table and key definitions from the sample JSON:

1. Table discovery
1. JSON keys with object or list of objects values should be mapped as explicit tables.
2. JSON keys mapped to scalar values should be mapped to default table _.

2. Cross-table key candidates
1. Columns present across multiple tables are candidate association keys.
2. Columns with names suggesting PK/FK semantics (for example PK, FK, Id, Key, correlationKey, parentId, childId) are strong association candidates.
3. If a key is clearly parent-level and repeated in child tables, define parent PK and child FK association.

3. Table key selection (uniqueness)
1. For each table, select columns that are stable and together identify row uniqueness.
2. Prefer columns exclusive to that table for metadata.key and identification.
3. Avoid volatile measurement columns as primary uniqueness keys when more stable identifiers exist.

4. Required tables
1. Set metadata.required tables to core tables needed for valid processing.
2. Keep optional tables out of required list if they may be absent in valid files.

5. Default table _
1. Keep _ for scalar root metadata and/or unmapped fields.
2. Keep add filename and add file timestamp for _ unless user asks otherwise.

## Config update procedure
1. Read the current target config.
2. Read sample JSON and infer tables/keys/associations using rules above.
3. Update these config sections:
1. files.metadata file regex
2. files.data file regex and folders.get consistency
3. files.catalog names
4. files.table names
5. metadata.required tables
6. metadata.key
7. metadata.association
8. metadata.add filename
9. metadata.add file timestamp
10. metadata.filename data format (only if user wants filename extraction)
4. Remove stale table mappings from prior flows when they are not present in the new sample schema.

## Filename extraction confirmation (mandatory question)
Before adding metadata.filename data format, ask the user if filename extraction is desired.

If yes, provide and confirm an example in this format:
1. Filename pattern example: monitorABC_20260610_123456_group42.json
2. Group mapping:
1. name -> sourceName (table _)
2. date -> batchDate (table _)
3. time -> batchTime (table _)
4. group -> groupId (table project)
3. Regex example using named groups and table destination.

Only add filename parsing rules after user confirmation.

## Validation checklist
After editing:
1. Parse the target config as JSON.
2. Run Scarab once in test mode against the target config when feasible.
3. Confirm no config key mismatch or get/data regex key mismatch errors.

## Output format to user
Return:
1. What changed and why
2. Target file updated
3. Inferred tables, keys, and associations summary
4. Validation results
5. Pending decision on filename extraction if not confirmed
