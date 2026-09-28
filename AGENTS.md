# Five9 Configuration Webservices API Samples — AI Agent Guide

> **Canonical guidance doc.** This is the tool-agnostic source of truth for AI coding
> assistants working in this repo. `.github/copilot-instructions.md` is kept in sync
> with this file for GitHub Copilot (which only reads its own file directly).
> `CLAUDE.md` at the repo root imports this file for Claude Code. When instructions
> change, update **this file first**, then propagate.

## Who this is for

This repo is used by **Five9 Developer Program members** — partner and customer
developers who can read, adapt, and run Python scripts but are often **not
professional software engineers**. Many are contact-center administrators or
solutions engineers who picked up scripting to automate Five9 configuration tasks.

When assisting in this repo, an AI agent should:
- Prefer clear, step-by-step explanations over terse engineering jargon.
- Briefly explain unfamiliar concepts when they come up rather than assuming
  prior knowledge — e.g. a SOAP API is an older web-service style that exchanges
  XML messages described by a WSDL (Web Services Description Language) file,
  which is essentially a machine-readable contract listing the available methods,
  their parameters, and data types. Five9's Configuration Webservices API is a
  SOAP/WSDL API. This repo wraps it with the `zeep` Python library so most users
  never need to touch raw XML directly.
- Favor working, copy-pasteable examples that follow the existing patterns in
  `examples/` over introducing new frameworks or abstractions.
- Assume the user may be unfamiliar with virtual environments, git, or unit
  testing — explain the "why" briefly when instructing them to run a command.

## Project Overview

This repository provides a Python wrapper for Five9's Configuration Webservices
API, offering individually functional scripts that demonstrate API method usage.
It simplifies interaction with Five9 domains for configuration management, user
administration, IVR management, and reporting.

**Disclaimer:** This is sample code, **not officially supported by Five9**. For
production deployments, users should be directed to Five9 Professional Services
or their Technical Account Manager (TAM) — see "Safety guardrails" below.

## Architecture & Core Components

### Main Module: `five9/`
- **`five9_session.py`** — Core module containing the `Five9Client` class (extends
  `zeep.Client`)
  - Manages SOAP client authentication and session handling
  - Supports both admin (`wsadmin/v13/AdminWebService`) and statistics
    (`wssupervisor/SupervisorWebService`) session types
  - Wraps calls in `ThrottledServiceProxy` (default 0.3s delay between calls) —
    exposed as `client.throttled_service`
  - Tracks API rate limits via `call_counters` and domain config via `vccConfig`
  - Uses `HistoryPlugin` for SOAP envelope inspection
  - Key properties: `latest_envelopes`, `latest_envelope_sent`,
    `latest_envelope_received`, `current_api_useage_formatted`,
    `latest_request_headers`
  - Raises `Five9ClientCreationError` on connection/auth failures

### Utilities: `five9/utils/`
- **`common.py`** — Common CLI argument parsing and client creation helpers
  - `common_parser_arguments()`: Standard argparse setup for examples
  - `create_five9_client()`: Client factory from parsed args
- **`domain_capture.py`** — `Five9DomainConfig` class for capturing/syncing domain
  configurations
  - Methods for bulk retrieval and Git-based versioning of domain objects
    (campaign profiles, agent groups, IVR scripts, dispositions, skills, etc.)
  - Snapshots write to `domain_snapshots/<DOMAIN_NAME>/` and can optionally
    generate IVR diagrams during capture (see `ivr_diagram.py` below)
- **`general.py`** — Utility functions like `get_random_password()` and
  `datatype_conversion()`
- **`ivr_utils.py`** — IVR-specific utilities
  - `decompress_function_body()`: Decompresses base64/zlib/gzip encoded IVR
    functions
  - `extract_jsfunctions_from_ivr()`: Parses IVR XML to extract JavaScript
    functions
  - `ivr_variable_usage()`: Analyzes script variable usage across IVRs
- **`ivr_diagram.py`** — Converts an IVR script's `xmlDefinition` into a styled
  SVG call-flow diagram plus Markdown/text documentation
  - Entry points: `capture_domain_ivrs(client, base_dir="private", name_pattern=".*")`,
    `document_ivrs(ivrs, output_dir, name_pattern=".*")`,
    `write_ivr_documentation(xml_definition, output_prefix, name=None)`,
    `ivr_to_svg()`, `ivr_to_text()`
  - Runnable as a CLI: `python3 -m five9.utils.ivr_diagram input.five9ivr output.svg`
  - SVGs are sized to be pasted into Lucidchart or similar diagramming tools
- **`campaign_profile_comprehension.py`** — Campaign profile filtering/analysis
  utilities (e.g. `demystify_filter`)
- **`test_users.py`** — Helpers for discovering test users by username pattern
  (`find_test_users`, `active_users`, `export_usernames_to_csv`)

### Examples: `examples/`
Categorized working scripts demonstrating API usage:
- **`user_management/`** — Bulk user create/update, skill management, SSO
  enforcement, migration prep
- **`records_management/`** — List operations (add/delete records, async
  operations, CRM updates)
- **`prompt_management/`** — Multilingual prompt handling
- **`ivrs/`** — IVR script management, JS function export, variable usage
  analysis, diagram generation (`ivr_generate_diagrams.py`)
- **`reporting/`** — Report generation and retrieval
- **`statistics_webservices/`** — Real-time statistics queries
- **`domain_config/`** — Domain-wide configuration capture and sync
  (`domain_config_capture.py`), campaign-profile filter tooling, contact field
  cleanup, bulk stop-time updates

Several subfolders have their own `README.md` with extra detail
(`examples/domain_config/README.md`, `examples/ivrs/README.md`,
`examples/reporting/README.md`, `examples/statistics_webservices/README.md`).

### Testing: `five9/tests/`
- Unit tests in `test_*.py` files; fast utility tests are named `test_utils_*.py`
  and avoid live API calls
- Integration tests (`testSessions.py`, `testDomainCapture.py`) hit the live API
  and require credentials
- Coverage tracking via `htmlcov/`
- See "Testing Approach" below for the full set of commands (there's a
  `Makefile` with convenience targets in addition to raw `unittest`/`coverage`
  invocations)

## Development Guidelines

### Code Style & Standards
- **Python Version**: Compatible with Python 3.8+
- **Formatting**: Uses `black` formatter (configured in `tox.ini`)
- **Type Checking**: Limited type hints currently in use
- **Documentation**: Docstrings should follow Google/NumPy style
- **Dependencies**: Managed via `requirements.txt` and `setup.py`
  - Core: `zeep` (SOAP client), `requests`, `lxml`, `tqdm` (progress bars),
    `GitPython` (domain snapshot versioning)
  - Dev: `black`, `coverage`

### Authentication & Credentials
- **Credential Storage**: `private/credentials.py` (git-ignored)
  - Structure:
    ```python
    ACCOUNTS = {
        'default_account': {
            'username': 'apiUserName',
            'password': 'superSecretPassword'
        },
        # Optional test account used by integration tests if present
        # 'default_test_account': {
        #     'username': 'apiTestUser',
        #     'password': 'apiTestPass'
        # }
    }
    ```
  - Bootstrapped on install via `setup.py`; existing file is preserved on
    reinstall
  - Reset (with timestamped backup of the old file) via:
    `F9_RESET_PRIVATE=1 pip install -e .`
- **Auth Methods** (in priority order):
  1. Explicit `--username`/`--password` args
  2. Account alias via `--account_alias` (looks up in `ACCOUNTS`)
  3. Environment vars: `F9_TEST_USERNAME` / `F9_TEST_PASSWORD` (integration
     tests only)
  4. Interactive prompt (fallback — the script will prompt for username and,
     via `getpass`, a hidden password)
- **Multi-Region Support**: Use `--hostalias` or `api_hostname_alias`:
  - `us`: api.five9.com (default)
  - `ca`: api.five9.ca
  - `eu`: api.five9.eu
  - `frk`: api.eu.five9.com
  - `in`: api.in.five9.com

### Creating New Examples
When adding new example scripts:
1. Import `common_parser_arguments` and `create_five9_client` from
   `five9.utils.common`
2. Use standard CLI args (username, password, account_alias, hostalias)
3. Add script-specific args after common ones
4. Include a docstring explaining purpose and usage
5. Handle exceptions gracefully with informative error messages
6. Use `tqdm` for progress bars in bulk operations
7. Place in the appropriate `examples/` subdirectory

Example template:
```python
from five9.utils.common import common_parser_arguments, create_five9_client

if __name__ == "__main__":
    args = common_parser_arguments(additional_args=[
        {"name": "--custom-arg", "type": str, "help": "Description"}
    ])

    client = create_five9_client(args)
    # Implementation here
```

### Working with Five9Client
- **Initialization**: `Five9Client(five9username=..., five9password=..., account=..., api_hostname_alias=...)`
- **API Calls**: Access via `client.service.methodName(args)`
- **Throttled Calls**: Use `client.throttled_service` for automatic rate
  limiting instead of calling `client.service` directly in loops
- **Rate Limiting**: Check `client.current_api_useage_formatted` for current
  usage; raw counters via `client.service.getCallCountersState()`
- **SOAP Inspection**: Use `client.latest_envelopes` (or
  `latest_envelope_sent` / `latest_envelope_received`) to debug request/response
  XML
- **Error Handling**: Catch `Five9ClientCreationError` for connection/auth
  issues

### API Rate Limits & Best Practices
- Default throttle: 300ms between calls (`ThrottledServiceProxy`) — this exists
  because Five9 enforces per-domain API rate limits; removing or shortening the
  delay risks the domain getting throttled or the account getting locked out
- Monitor usage: `client.service.getCallCountersState()`
- Bulk operations: Use async methods when available (`asyncAddRecordsToList`,
  `asyncUpdateCrmRecords`, `asyncDeleteRecordsFromList`,
  `asyncUpdateCampaignDispositions`)
- Batch processing: Use `tqdm` for progress tracking and user feedback

### Testing Approach
Most typical users can skip deep testing — it's mainly relevant when modifying
`five9/` core code or utilities rather than writing one-off example scripts.

**Makefile targets** (recommended — handle venv/install for you):
```bash
make unit                    # fast utility tests (no live API)
make coverage                # coverage for fast tests
make test                    # full suite incl. integration (sets F9_INTEGRATION=1)
FAIL_UNDER=80 make coverage  # enforce minimum coverage
```

**Direct commands** (after activating the virtual environment):
```bash
python -m unittest discover -s five9/tests -p 'test_utils_*.py' -v   # fast, offline
F9_INTEGRATION=1 python -m unittest discover -s five9/tests -p 'test*.py' -v  # full, incl. integration
coverage run -m unittest discover -s five9/tests -p 'test_utils_*.py'
coverage html && open htmlcov/index.html
./five9/unittest_coverage.sh --report --fail-under=75   # Mac/Linux helper script
                                                          # (.ps1 variant for Windows)
```

- **Test Categories**: Utility unit tests (fast, offline) are `test_utils_*.py`;
  integration tests (live API, need credentials) are `testSessions.py`,
  `testDomainCapture.py`
- **Environment Variables**: `F9_INTEGRATION=1` includes integration tests;
  `F9_TEST_USERNAME`/`F9_TEST_PASSWORD` supply integration creds;
  `OPEN_HTML=0` disables auto-opening the coverage report; `FAIL_UNDER` sets
  the coverage threshold for the Make target
- **Test Isolation**: Each test should be independent and unit tests should
  not require live API access

### Domain Snapshots
- `Five9DomainConfig` class captures domain state to a Git repository
- Default path: `domain_snapshots/<DOMAIN_NAME>/`
- Objects captured: Skills, Campaigns, IVRs, Users, Agent Groups, Campaign
  Profiles, Dispositions, and more (see `METHODS` list in `domain_capture.py`)
- Use for: version control, disaster recovery, migration planning, auditing
- `examples/domain_config/domain_config_capture.py` also generates IVR
  diagrams/docs during capture by default (`--skip-ivr-documentation` to
  opt out)
- Before deleting or renaming a domain object, follow
  `OBJECT_DEPENDENCIES.md`. It documents reverse-reference checks, snapshot
  coverage gaps, and the required dependency report.

## Common Tasks

### Adding a New API Method Wrapper
1. Check if the method exists: `client.print_available_service_methods()`
2. Inspect the method signature: `print(client.wsdl.dump())`
3. Create an example in the appropriate `examples/` subdirectory
4. Add a unit test in `five9/tests/`
5. Document parameters and return values

### Debugging SOAP Requests
```python
# After any API call:
print(client.latest_envelope_sent)      # Request XML
print(client.latest_envelope_received)  # Response XML
print(client.latest_envelopes)          # Both
```

### Handling Complex Data Types
- Use `client.get_type()` to construct complex types
- Example: `disposition = client.get_type('ns0:disposition')(...)`
- Zeep auto-converts Python dicts to SOAP types where possible

### Working with IVR Scripts
- Get IVRs: `client.service.getIVRScripts(scriptNamePattern='.*')`
- Parse functions: `ivr_utils.extract_jsfunctions_from_ivr(ivr.xmlDefinition)`
- Analyze variables: `ivr_utils.ivr_variable_usage(ivrs, verbose=True)`
- Generate a diagram: `ivr_diagram.ivr_to_svg(ivr.xmlDefinition)` or run
  `examples/ivrs/ivr_generate_diagrams.py`
- Decompress function bodies from base64/zlib/gzip encoding

### Bulk User Operations
- Template pattern: Get a template user with `getUserInfo()`, copy roles/skills
- Use `tqdm` for progress: `with tqdm(total=len(users), desc="...", mininterval=1) as pbar:`
- Error handling: Catch per-user exceptions, continue processing others
- See `examples/user_management/bulk_user_create.py` for reference
- **This is a bulk write operation** — see "Safety guardrails" below before
  running it against a real domain

## Important Conventions

### Error Handling
- Wrap client creation in try/except for `Five9ClientCreationError`
- Handle SOAP faults: `except zeep.exceptions.Fault as e:`
- Network errors: `except requests.exceptions.RequestException as e:`
- Per-item errors in bulk operations: log and continue

### Logging
- Configure via the `logging_level` kwarg to `Five9Client` (default: `INFO`)
- Use the `logging` module, not `print()`, for operational messages
- Format: `"%(asctime)s - %(levelname)s - %(message)s"`

### File Organization
- Keep examples self-contained and runnable
- Extract reusable logic to `five9/utils/`
- Private data (credentials, CSVs) goes in `private/` (git-ignored)
- Domain snapshots in `domain_snapshots/` (selectively committed)

### Naming Conventions
- Scripts: Descriptive snake_case (e.g., `bulk_user_create.py`)
- Functions: snake_case with clear verb prefixes (`get_`, `create_`, `update_`,
  `delete_`)
- Classes: PascalCase (e.g., `Five9Client`, `Five9DomainConfig`)
- Constants: UPPER_SNAKE_CASE (e.g., `ACCOUNTS`, `HOST_ALIAS`)

## Project-Specific Gotchas

1. **API Version**: Default is v13, but v4 is still supported (limited
   features) — a couple of code comments/docstrings elsewhere in the repo
   still say "v12" in prose; treat the `api_version="v13"` default in
   `Five9Client.__init__` as authoritative.
2. **Session Types**: Don't mix admin and statistics methods on the same
   client.
3. **Throttling**: Respect the 300ms default delay; adjust via
   `ThrottledServiceProxy` only if you understand the rate-limit implications
   (see Safety guardrails).
4. **Credentials**: NEVER commit `private/credentials.py` — it's git-ignored
   for security. Note that `.gitignore` also currently excludes the whole
   `.github/` folder, so don't assume something is version-controlled just
   because it's tracked locally — check with `git ls-files` if it matters.
5. **Virtual Environment**: Always activate `venvs/five9` before running
   scripts.
6. **Zeep Caching**: The first run may be slow while the WSDL is fetched/cached.
7. **Domain Name**: Available as `client.domain_name` after initialization
   (admin sessions only; not populated for `sessiontype="statistics"`).

## Quick Reference

### Interactive Shell
```bash
python -m five9.five9_session                      # Use default account
python -m five9.five9_session -go                  # Pre-fetch users, campaigns, skills
python -m five9.five9_session --account my_account # Use specific account
```

### Running Examples
```bash
python examples/domain_current_ratelimits.py --account_alias default_account
python examples/user_management/bulk_user_create.py --username user@domain --password pass
```

### Testing
```bash
python -m unittest discover -s five9/tests         # Run all tests
python five9/tests/test_five9_session_unit.py      # Run specific test
./five9/unittest_coverage.sh                       # Generate coverage report
make unit                                          # Fast tests via Makefile
```

### Installation/Setup
```bash
git pull                                           # Update repository
pip install -e .                                   # Reinstall (preserves credentials)
F9_RESET_PRIVATE=1 pip install -e .               # Force credential template reset
```

## Safety guardrails for AI agents

These rules apply regardless of which AI tool is being used (Claude, Copilot,
or otherwise). This repo talks to **real Five9 contact-center domains** —
mistakes can affect live agents, campaigns, and customer data.

1. **Never handle secrets in chat or in tracked files.**
   - Never print, log, echo, or commit the contents of `private/credentials.py`,
     `--password` values, `F9_TEST_PASSWORD`, or any API response that embeds
     credentials or auth headers (e.g. `client.latest_request_headers` includes
     a Basic Auth header — treat its output as sensitive and don't paste it
     back into chat).
   - Never ask the user to paste a username/password into the chat/conversation.
     If credentials are needed, point them to `private/credentials.py`, the
     `--account_alias` flag, or the interactive `getpass` prompt — all of which
     keep secrets out of shell history and chat transcripts.
   - Don't write scripts that hardcode credentials as string literals; use the
     existing `common_parser_arguments`/`create_five9_client` auth chain instead.

2. **Treat every connected Five9 domain as potentially production.**
   - There is no reliable, automatic way to tell a sandbox/trial domain from a
     live production domain purely from the API. Don't assume `default_account`
     or any configured alias is "just a test domain."
   - Before running anything that **writes, modifies, or deletes** domain
     configuration — e.g. `bulk_user_create.py`, `bulk_user_update_from_csv.py`,
     `bulk_user_skill_update.py`, `bulk_user_SSO_pseudo_enforce.py`,
     `modifyVCCConfiguration`, `deleteUser`/`deleteSkill`/`deleteCampaign`/
     `deleteIVRScript`, any `domain_config/` script that mutates campaign
     profiles, or any bulk/async CRUD method — **stop and get explicit
     confirmation from the user** that they intend to run it against the
     domain they're currently pointed at, and that they understand the effect.
   - Before any object deletion or rename, follow `OBJECT_DEPENDENCIES.md`:
     capture current state, inspect reverse references, perform the listed live
     checks, and report unresolved coverage gaps. Do not interpret "no snapshot
     matches" as proof that an object is unused.
   - Present the domain, exact target, discovered dependencies, planned detach
     or reassignment actions, backup path, and validation plan before requesting
     the user's confirmation. An API "in use" fault is a safety signal, not a
     check to bypass.
   - Prefer suggesting a dry run (print what would change, or filter to a small
     test subset) before a full bulk run.
   - Recommend testing against a sandbox/trial domain rather than a production
     one whenever the user's intent allows it.

3. **Don't bypass the built-in rate limiting.** `ThrottledServiceProxy` (0.3s
   default delay) exists to keep bulk operations within Five9's per-domain API
   rate limits. Don't remove it, monkey-patch around it, or write raw
   `client.service` loops that skip `client.throttled_service` for
   high-volume operations, unless the user explicitly asks and understands the
   risk of tripping rate limits or having the account throttled/locked.

4. **Escalate production deployment requests.** If a user's request implies
   deploying this sample code (or a derivative of it) as part of a production
   workflow, integration, or customer-facing system, flag clearly that this
   repository is unsupported sample code and recommend they engage Five9
   Professional Services or their Technical Account Manager (TAM) for a
   production-grade implementation.

5. **When in doubt, ask before acting.** For any action with side effects
   outside the local filesystem/git (API calls that create/modify/delete
   domain objects, sending data to a live domain), prefer asking a clarifying
   question over guessing intent.

## When Collaborating on This Repo

- **Adding Features**: Prioritize examples over modifying core `Five9Client`
  unless necessary
- **Breaking Changes**: Avoid breaking existing examples; maintain backward
  compatibility
- **Documentation**: Update this file (`AGENTS.md`) first when adding major
  features or patterns, then propagate to `.github/copilot-instructions.md`
- **Testing**: Add unit tests for new utility functions; integration tests
  optional but encouraged
- **Credentials**: Never request or expect user credentials in code review
- **Dependencies**: Minimize new dependencies; justify additions in PR
  description

## API Documentation References
- Five9 Configuration Webservices API docs: available in the Five9 admin
  portal under Help
- WSDL location: `https://api.five9.com/wsadmin/v13/AdminWebService?wsdl&user=<username>`
- Zeep documentation: https://docs.python-zeep.org/

## Contact & Support
- **Disclaimer**: This is sample code, NOT officially supported by Five9
- For production use: engage Five9 Professional Services or the TAM team
- Issues/PRs: welcome for bug fixes and enhancements
- Original Author: Andrew Willey (andrewawilley)
