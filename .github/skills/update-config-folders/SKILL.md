---
name: update-config-folders
description: "Use when asked to update folders in one config to match another config. Trigger phrases: update config folders, sync folders between configs, copy folders from reference, sandbox to production config migration, update folders considering."
---

# Update Config Folders

## Goal
Update folder definitions in a target config file to match the folder structure defined in a reference config file, enabling quick migration from test/sandbox configurations to production configurations or vice versa.

## Required inputs
1. **Target config** (first mentioned): The config file to be edited.
2. **Reference config** (mentioned after "considering"): The config file providing the folder structure to copy.

If paths are not explicit, infer them from user request and context.

## Folder sections to sync
Copy these sections from reference config to target config:
1. `folders.post` (list of input folders)
2. `folders.temp` (temporary staging folder)
3. `folders.trash` (trash/archive folder)
4. `folders.store` (metadata storage folder)
5. `folders.get` (output folders dict with routing keys)

All other config sections remain unchanged.

## Update procedure
1. Read the target config file (to be edited).
2. Read the reference config file (source of folder structure).
3. Extract `folders` object from reference config.
4. Replace the `folders` object in target config with the reference version.
5. Preserve all other config sections unchanged.
6. Write the updated target config back to disk.

## Validation checklist
After editing:
1. Parse the updated target config as JSON.
2. Confirm that:
   1. All folder sections from reference are now in target.
   2. All non-folder sections in target remain unchanged.
   3. No keys are missing in the updated `folders` object.
3. Optionally run Scarab once in test mode against the updated config (if feasible).

## Output format to user
Return:
1. What changed and why
2. Target config file updated
3. Folder sections synced summary (old vs new folder structure)
4. Validation results
5. Any warnings if folder paths do not exist on disk
