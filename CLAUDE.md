# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An unofficial Python client for the German broker **Trade Republic**, plus an `examples/` workspace of scripts that use the client to export an account's timeline, documents, and portfolio and convert them to CSV (targeted at importing into "Portfolio Performance").

The installable package lives in `src/trapi/`. The `examples/` and `LS/` directories are standalone scripts/data, not part of the package.

## Tooling (non-negotiable)

This repo follows the same methodology as the sibling `qufin` project. Use these tools and no substitutes:

| Tool | Purpose | Never use instead |
|---|---|---|
| `uv` | Package management | `pip`, `poetry`, `conda` |
| `ruff` | Linting and formatting | `flake8`, `black`, `isort` |
| `pytest` + `pytest-xdist` | Testing | `unittest` |
| `pyright` | Type checking | `mypy` |

All dependencies are declared in `pyproject.toml` (hatchling build backend); the lockfile is `uv.lock`. Runtime deps are in `[project.dependencies]`; tooling is in the `[dependency-groups] dev` group; `getpass4` (used only by `examples/`) is in the optional `examples` group and is not installed by default.

## Commands

```bash
uv sync --all-groups                 # install runtime + dev + examples deps, create .venv
uv add <package>                     # add a runtime dependency
uv add --group dev <package>         # add a dev dependency

uv run ruff format .                 # format
uv run ruff check --fix .            # lint and auto-fix     (or: make fmt)
uv run pyright                       # strict type-check, scoped to src/   (make typecheck)
uv run pytest                        # run tests across all cores (-n auto)  (make test)
uv run pytest tests/test_smoke.py::test_all_isins_loads_bundled_data   # one test
```

`testpaths = ["tests"]` and `-n auto` are baked into `addopts`, and `asyncio_mode = "auto"` is set, so a bare `pytest` parallelizes and runs `async def` tests without per-test decorators.

> **Baseline is not clean yet.** Tooling was introduced on top of legacy code: `ruff check` and strict `pyright` still report findings in `src/trapi/api.py` (untyped signatures, `== None` comparisons, hungarian-notation naming). These are the cleanup backlog for subsequent refactoring steps — not a regression. `pyright` is scoped to `src/` only; `examples/` and `LS/` have relaxed `ruff` per-file ignores.

Running the example scripts (run from the **repo root**, not from inside `examples/`):

```bash
python3 ./examples/portfolioExporter.py                 # -> myPortfolio.json
python3 ./examples/timelineExporter.py                  # -> myTimeline.json
python3 ./examples/isinDownloader.py -p -c              # crawl portfolio stocks -> stock_details/, allStocks.json
python3 ./examples/timelineCsvConverter.py              # -> myTransactions.csv
```

`startMe.sh` chains the full doc+details export pipeline (`timelineExporterWithDocsAndDetails.py` then `timelineCSVconvWithDetails.py`). It is a bash script; on this Windows machine run it via the Bash tool or invoke the Python steps directly.

### Important caveats before running anything live
- The examples were originally **tested only on Linux, Python 3.8, and `LOCALE = "de"`**; the package itself now targets Python >=3.11. `timelineCSVconvWithDetails.py` hard-exits unless locale is `de`.
- Trade Republic allows **only one registered device at a time** — logging in here logs you out of the phone app. First run after pairing often errors; re-running usually succeeds.

## Architecture

### `src/trapi/api.py` — the client (everything of substance lives here)

Two classes:
- **`TRApi`** — the async, WebSocket-based client. All API methods are `async` and take a `callback` (default `print`).
- **`TrBlockingApi(TRApi)`** — synchronous wrapper. Each method calls the async parent via `get_one()`, which runs the event loop until exactly one response arrives (`start(receive_one=True)`) with a timeout. Use this for simple scripts; use `TRApi` directly for streaming/multiple subscriptions.

Authentication is **ECDSA device pairing**, not a password session:
1. `register_new_device()` generates a NIST256p signing key, POSTs to `/api/v1/auth/account/reset/device`, prompts for the SMS token via `input()`, and writes the private key as a PEM file named **`key`** in the current working directory.
2. `login()` reads that `key` file and authenticates. If no key / 401, it transparently calls `register_new_device()` and retries.
3. `do_request()` signs every REST call with `X-Zeta-Timestamp` + `X-Zeta-Signature` headers (HMAC-style ECDSA over `"{timestamp}.{payload}"`).

The `key` file is gitignored and is resolved relative to the **current working directory** — scripts must be run from a consistent cwd or pairing will repeat.

WebSocket subscription model (`sub()` + `start()`):
- `sub()` lazily opens `wss://api.traderepublic.com`, handshakes with `connect 21 {locale}`, then sends `sub <id> <payload>`. Each subscription `key` (e.g. `"ticker US..."`) is assigned an incrementing integer id stored in `self.dict`, and its callback in `self.callbacks[id]`.
- `start()` is the receive loop. It parses each frame as `<id> <state> <data>`:
  - `D` — a **delta** update; reconstructed against the previous payload by `decode_updates()` using `=n`/`-n`/`+text` instructions (keep n chars / skip n chars / insert text). This is TR's diff protocol; see the worked example in the `decode_updates` docstring.
  - `A` ack (ignored), `C` continue, `E` raises `TRapiExcServerErrorState` (commonly a server-side expired object), anything else raises `TRapiExcServerUnknownState`.
- Each public method (`cash`, `portfolio`, `timeline`, `instrument`, `stock_details`, `neon_news`, `simple_create_order`, …) maps 1:1 to a TR WebSocket message `type`. Docstrings note which require login. Old method names are kept as `@deprecated` aliases.

`TRApi.all_isins()` is a classmethod reading the bundled `src/trapi/isins.txt` (included in the wheel by hatchling).

### `examples/` — the export/convert pipeline

Config is split in two files the scripts import:
- **`environment.py`** (copy from `environment_template.py`) — `NUMBER`, `PIN`, `LOCALE`, `CURRENCY`. Gitignored.
- **`envConsts.py`** — output directory and filename constants (`S_OUTPUT_DIR`, `S_DOC_DOWNLOADS`, etc.).

Data flow: `timelineExporter` (paginates the timeline via `res["cursors"]["after"]`) → `myTimeline.json`; `portfolioExporter` → `myPortfolio.json`; `isinDownloader` crawls per-ISIN stock details into `stock_details/` and combines into `allStocks.json`; `timelineCsvConverter` joins these to emit `myTransactions.csv`.

The hard part is **mapping a timeline event's display title to an ISIN** — TR timeline events do not include the ISIN. `getIsinFromStockName()` resolves names against three sources in order: crawled `allStocks.json` names, the manual override map `companyNameIsins.json`, and the Lang & Schwarz universe (`LS/isins.json`). Unresolved names print `WARNING: Company not found` and must be added by hand to `companyNameIsins.json`, then the converter re-run. The conversion branches heavily on German vs. English body text (e.g. `"Kauf"`/`"Buy order"`, `"Gutschrift Dividende"`/`"Dividend per"`).

`timelineExporterWithDocsAndDetails.py` is the heavyweight variant: it also fetches each event's `timeline_detail`, downloads linked PDF documents (sorting them into dated subfolders under `S_DOC_DOWNLOADS`), and has retry/backoff with re-login on server errors. `timelineCSVconvWithDetails.py` is its in-memory CSV counterpart (DE-only).

### `LS/` — Lang & Schwarz reference data

The L&S trading universe ("Stammdaten") published as PDF, converted (externally, via Tabula) to `stammdaten.json`, then reduced by `convert-stammdaten.py` to `isins.json` — an array of `[WKN, ISIN, name, symbol]` used by the CSV converter for name→ISIN fallback lookup.
