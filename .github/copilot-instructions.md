# Scarab AI Coding Agent Instructions

## Project Overview

Scarab is an asynchronous file-oriented ingestion service. A Python daemon monitors configured
local or SharePoint input repositories, validates JSON descriptors, calculates deterministic UUIDv5
identifiers, calls PostgreSQL JSONB functions, and dispatches associated media to configured
storage repositories.

The active implementation is under `src/`; database definitions are under `db/`; container
artifacts are under `containers/`. Project architecture and module contracts are documented in
[docs/rewrite/PLAN.md](../docs/rewrite/PLAN.md) and
[docs/rewrite/CONTRACTS.md](../docs/rewrite/CONTRACTS.md).

## Active Modules

- [src/main.py](../src/main.py): daemon lifecycle, logging, signals, and scan loop
- [src/config_loader.py](../src/config_loader.py): immutable Pydantic configuration models
- [src/database.py](../src/database.py): psycopg3 connection pool and stored-function calls
- [src/storage_manager.py](../src/storage_manager.py): local and SharePoint I/O, filename safety,
  trash maintenance
- [src/pipeline.py](../src/pipeline.py): validation, UUIDv5 generation, ingestion, media dispatch
- [db/init.sql](../db/init.sql): PostgreSQL extensions, tables, indexes, and grants documentation
- [db/procedures.sql](../db/procedures.sql): JSONB operation function

## Development Workflow

1. Install dependencies with `uv sync --extra dev`.
2. Run the test suite with `uv run pytest`.
3. Run lint with `uv run ruff check src tests`.
4. Run the daemon locally with `uv run python -m src.main config`.
5. Run the containers with `podman compose -f containers/podman-compose.yml up --build` when Podman
   is available.

## Conventions

- Python identifiers, comments, and docstrings are written in English.
- User-facing Markdown documentation is written in Brazilian Portuguese.
- Use absolute imports from `src.*`.
- Keep public Python signatures fully typed and preserve the contracts in
  `docs/rewrite/CONTRACTS.md`.
- Use parameterized SQL exclusively. Never interpolate payloads, filenames, or secrets into SQL.
- Treat filenames read from JSON as untrusted. Route all storage operations through
  `StorageManager` validation.
- Keep database and SharePoint secrets in environment variables referenced by configuration; never
  hardcode or log secret values.
- Do not add dependencies for Python standard-library modules such as `uuid`.
- Do not edit unrelated files or reformat completed modules without a concrete reason.
