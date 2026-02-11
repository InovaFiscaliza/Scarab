# Scarab AI Coding Agent Instructions

## Project Overview
Scarab is an **Enterprise Service Bus (ESB)** that runs as a Windows service, monitoring folders and performing file operations while consolidating metadata tables. It processes XLSX, CSV, and JSON files, merging metadata with support for multi-table relationships (PK/FK), filename extraction, and multiple output formats.

## Architecture & Data Flow

### Module Structure
- **[scarab.py](src/scarab.py)**: Main loop with signal handlers (SIGTERM, SIGBREAK, SIGINT) for graceful shutdown
- **[config_handler.py](src/config_handler.py)**: JSON config parser with defaults from [default_config.json](src/default_config.json)
- **[metadata_handler.py](src/metadata_handler.py)**: Core metadata consolidation engine (1886 lines)
- **[file_handler.py](src/file_handler.py)**: File operations (move, trash, MD5 checking)
- **[log_handler.py](src/log_handler.py)**: Logging setup with `coloredlogs` for terminal and file output

### Critical Data Flow
1. Files appear in `POST` folders → moved to `TEMP` (MD5 checked for duplicates)
2. Files sorted by regex into: metadata files, data files, or trash
3. Metadata files: processed → consolidated via PK/FK → saved to `STORE` + multiple `GET` folders
4. Data files: published to `GET` folders (optionally referenced in metadata)
5. Cleanup: old files in `TEMP` → `TRASH` based on `clean period in hours`

### Multi-Table Architecture
- **Single vs Multi-Table**: JSON root objects, XLSX sheets, or CSV with different column sets define tables
- **PK/FK Relationships**: Config defines associations (e.g., `FactData.FK1` → `DimData1.PK1`)
  - `"relative value": true`: Keys are file-scoped (reset per file)
  - `"relative value": false`: Absolute keys across all files
  - `"int type": true`: Sequential integer PKs; `false`: strings/UUIDs
- **Key Merge Logic**: Rows with duplicate key columns are merged using `_custom_agg()` (see [metadata_handler.py#L195](src/metadata_handler.py#L195))
  - Concatenates unique values with `, ` separator
  - PK merges tracked in `pk_unmerge_map` for FK fixup

## Configuration Patterns


### Config File Structure (JSON)
- **Mandatory root keys**: `log`, `folders`, `files`, `metadata` (enforced by `_ensure_mandatory_structure()`)
- **Folder keys**: `post` (list), `temp`, `trash`, `store`, `get` (dict mapping regex keys to folder lists)
- **File regex patterns**:
  - `metadata file regex`: Dict with keys (e.g., `"*"`, `"json"`) → regex patterns
  - `data file regex`: Maps to `folders.get` keys for routing files
- **Table names**: Map JSON keys to human-readable names (e.g., `{"project": "PROJETO"}`)
- **CSV separator**: New config key `csv separator` (under `files`) sets the delimiter for CSV parsing. Default is `;`, but can be set to `,` or other values for tests or integration.
- **Special keys**:
  - `"_"`: Default table for single-table data or unmapped JSON keys
  - `"*"`: Refers to all tables in multi-table files
  - `"<name>"`: Placeholder replaced by config `name` value

### Example Config Snippet
```json
{
  "metadata": {
    "key": {"project": ["issue", "context"]},
    "association": {
      "FactData": {
        "PK": {"name": "UID", "int type": false, "relative value": false},
        "FK": {"DimData1": "FK_Dim1"}
      }
    }
  }
}
```

## Development Workflows

### Running Tests
- **Location**: [tests/](tests/) folder with `.bat` scripts (Windows-specific)
- **Command**: `uv run ..\src\scarab.py .\sandbox\config.json` (from `tests/` directory)
- **Setup**: Run `0clean_test.bat` to reset sandbox, then `1test_simple_XLSX.bat`, etc.
- **Stop**: `Ctrl+C` for graceful shutdown (may take up to `check period in seconds`)

### Environment Setup
1. Install [UV](https://docs.astral.sh/uv/) package manager
2. Run `uv sync` in project root (installs deps from [pyproject.toml](pyproject.toml))
3. Execute: `uv run src\scarab.py <config_path>.json`

### Dependencies (from pyproject.toml)
- `pandas>=2.2.3`, `openpyxl>=3.1.5`: XLSX/CSV handling
- `pyqvd>=2.3.0`: QlikView QVD output
- `base58>=2.1.1`: Unique ID generation
- `coloredlogs>=15.0.1`: Terminal formatting

## Project-Specific Conventions

### Unique Column Naming
Metadata handler creates internal columns with unique IDs to avoid conflicts:
- `index-<uuid>`: Concatenated key columns for row deduplication
- `file-<uuid>`: Tracks data file references
- `post_order-<uuid>`: Preserves input order when no `sort by` defined

### Null Handling
- **Null strings**: See `default_config.json` → `null string values` (includes `"NA"`, `"<NA>"`, `""`, `"pd.NA"`, etc.)
- **Merge behavior**: Null values are **ignored** during updates (existing data retained)
- **Data removal**: Requires stopping service + manual edit of reference file

### File Naming & Extraction
- **Filename data format**: Regex with named groups extracts metadata (e.g., `"(?P<date>\\d{4}\\.\\d{2}\\.\\d{2})"`)
- **Post-processing rules**: Apply `replace`, `add prefix`, `add suffix` to extracted data
- **Timestamp format**: `%Y%m%d_%H%M%S` for trash file renaming

## Common Pitfalls

1. **Config Validation**: Missing mandatory keys (`log`, `folders`, `files`, `metadata`) cause startup failure
2. **Regex Keys**: `folders.get` keys must match `files.data file regex` keys exactly
3. **PK/FK Consistency**: Mixing relative/absolute or int/string types across tables breaks associations
4. **Character Scope**: Default regex `[^A-Za-z0-9çÇãÃ...]` strips special chars from column names
5. **Overwrite Flags**: Three separate flags control behavior in `store`, `get`, and `trash` folders
6. **Multi-Table CSV**: CSV files are single-table; use `table names` config to route to correct table

## Integration Points

### Windows Task Scheduler
- XML examples in [src/Scheduler/](src/Scheduler/)
- Service runs on startup, auto-restarts on failure
- Supports OneDrive sync for SharePoint integration

### Power Automate
- PA scripts in [src/PA/](src/PA/) extract metadata from SharePoint uploads
- Places files in Scarab-monitored folders for processing

## Output Formats
Supported via file extension in `catalog names` config:
- **XLSX**: Multi-table with sheets (primary format for recovery)
- **CSV**: Single-table (creates `<base>_<table>.csv` per table)
- **JSON**: Array/dict format
- **QVD**: QlikView binary (via `pyqvd`)
- **Parquet**: Columnar format
