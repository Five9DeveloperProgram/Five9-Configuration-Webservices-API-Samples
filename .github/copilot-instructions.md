# Five9 Configuration Webservices API Samples - Copilot Instructions

> This file is kept in sync with [`../AGENTS.md`](../AGENTS.md), the repo's
> canonical, tool-agnostic AI-agent guidance doc (also used by Claude and other
> assistants). When instructions change, update `AGENTS.md` first, then mirror
> the change here — Copilot reads this file directly and does not follow the
> pointer.

## Who this is for
This repo is used by Five9 Developer Program members who can adapt Python
scripts but may not be professional software engineers. Prefer clear,
step-by-step explanations and copy-pasteable examples over jargon or new
frameworks. Explain unfamiliar concepts (such as SOAP and WSDL), virtual
environments, git, and testing briefly when they come up.

## Project Overview
This repository provides a Python wrapper for Five9's Configuration Webservices API, offering individually functional scripts demonstrating API method usage. It simplifies interaction with Five9 domains for configuration management, user administration, IVR management, and reporting.

This is unsupported sample code, not a production-grade integration. See
"Safety guardrails for AI agents" below.

## Architecture & Core Components

### Main Module: `five9/`
- **`five9_session.py`**: Core module containing `Five9Client` class (extends `zeep.Client`)
  - Manages SOAP client authentication and session handling
  - Supports both admin (`wsadmin/v13/AdminWebService`) and statistics (`wssupervisor/SupervisorWebService`) session types
  - Features throttling via `ThrottledServiceProxy` (default 0.3s delay between calls)
  - Tracks API rate limits via `call_counters` and domain config via `vccConfig`
  - Uses `HistoryPlugin` for SOAP envelope inspection
  - Key properties: `latest_envelopes`, `latest_envelope_sent`, `latest_envelope_received`, `current_api_useage_formatted`, `latest_request_headers`
  - Raises `Five9ClientCreationError` on connection/auth failures

### Utilities: `five9/utils/`
- **`common.py`**: Common CLI argument parsing and client creation helpers
  - `common_parser_arguments()`: Standard argparse setup for examples
  - `create_five9_client()`: Client factory from parsed args
- **`domain_capture.py`**: `Five9DomainConfig` class for capturing/syncing domain configurations
  - Methods for bulk retrieval and Git-based versioning of domain objects
  - Supports campaign profiles, agent groups, IVR scripts, dispositions, etc.
  - Can optionally generate IVR diagrams during capture
- **`general.py`**: Utility functions like `get_random_password()` and `datatype_conversion()`
- **`ivr_utils.py`**: IVR-specific utilities
  - `decompress_function_body()`: Decompresses base64/zlib/gzip encoded IVR functions
  - `extract_jsfunctions_from_ivr()`: Parses IVR XML to extract JavaScript functions
  - `ivr_variable_usage()`: Analyzes script variable usage across IVRs
- **`ivr_diagram.py`**: Generates SVG diagrams and Markdown/text documentation
  from IVR XML; use `python3 -m five9.utils.ivr_diagram input.five9ivr output.svg`
- **`test_users.py`**: Helpers for finding test users by username pattern
- **`campaign_profile_comprehension.py`**: Campaign profile filtering/analysis utilities

### Examples: `examples/`
Categorized working scripts demonstrating API usage:
- **`user_management/`**: Bulk user create/update, skill management, SSO enforcement, migration prep
- **`records_management/`**: List operations (add/delete records, async operations, CRM updates)
- **`prompt_management/`**: Multilingual prompt handling
- **`ivrs/`**: IVR script management and diagram generation
- **`reporting/`**: Report generation and retrieval
- **`statistics_webservices/`**: Real-time statistics queries
- **`domain_config/`**: Domain-wide configuration capture and sync, including
  IVR diagrams by default (`--skip-ivr-documentation` opts out)

### Testing: `five9/tests/`
- Fast, offline utility tests are named `test_utils_*.py`
- `testSessions.py` and `testDomainCapture.py` are live integration tests
- Coverage tracking via `htmlcov/`
- Run offline tests with `make unit`; do not run integration tests against a
  live account without explicit user confirmation

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
  - Structure: `ACCOUNTS = {'default_account': {'username': '...', 'password': '...'}}`
  - Bootstrapped on install via `setup.py`, preserved on reinstall
  - Reset with a timestamped backup: `F9_RESET_PRIVATE=1 pip install -e .`
- **Auth Methods** (in priority order):
  1. Explicit `--username`/`--password` args
  2. Account alias via `--account_alias` (looks up in `ACCOUNTS`)
  3. Environment vars: `F9_TEST_USERNAME` / `F9_TEST_PASSWORD` (integration tests only)
  4. Interactive prompt (fallback, with a hidden password via `getpass`)
- **Multi-Region Support**: Use `--hostalias` or `api_hostname_alias`:
  - `us`: api.five9.com (default)
  - `ca`: api.five9.ca
  - `eu`: api.five9.eu
  - `frk`: api.eu.five9.com
  - `in`: api.in.five9.com

### Creating New Examples
When adding new example scripts:
1. Import `common_parser_arguments` and `create_five9_client` from `five9.utils.common`
2. Use standard CLI args (username, password, account_alias, hostalias)
3. Add script-specific args after common ones
4. Include docstring explaining purpose and usage
5. Handle exceptions gracefully with informative error messages
6. Use `tqdm` for progress bars in bulk operations
7. Place in appropriate `examples/` subdirectory

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
- **API Calls**: Use `client.service.methodName(args)` for isolated, one-off
  calls only. For bulk or high-repeat calls, use
  `client.throttled_service.methodName(args)` instead.
- **Throttled Calls**: `Five9Client` creates `client.throttled_service`
  automatically. It delegates to the same SOAP service, pausing 300ms before
  each method call; no separate proxy setup is needed.
- **Rate Limiting**: Check `client.current_api_useage_formatted` for current usage
- **SOAP Inspection**: Use `client.latest_envelopes` to debug request/response
- **Error Handling**: Catch `Five9ClientCreationError` for connection/auth issues

### API Rate Limits & Best Practices
- **Required for repeated calls**: Use `client.throttled_service` whenever
  iterating over objects or repeatedly calling API methods, whether reading,
  creating, updating, deleting, or polling. This applies to loops, nested
  loops, bulk scripts, and repeated calls from helpers; do not use
  `client.service` just because the method is read-only or asynchronous.
  For example:
  ```python
  for name in names:
      user = client.throttled_service.getUserInfo(name)
  ```
  See `examples/domain_config/push_campaigns.py` for an existing bulk-call
  pattern.
- Default throttle: 300ms before each proxied call (`ThrottledServiceProxy`).
  It reduces the chance of hitting Five9's per-domain API rate limits, but
  does not guarantee that a long-running or concurrent workload stays within
  the limit; monitor usage and slow down further if needed.
- Monitor usage: `client.service.getCallCountersState()` for a one-off check;
  use `client.throttled_service.getCallCountersState()` if checking repeatedly
- Bulk operations: Use async methods when available (`asyncAddRecordsToList`,
  `asyncUpdateCrmRecords`, `asyncDeleteRecordsFromList`,
  `asyncUpdateCampaignDispositions`); invoke them through
  `client.throttled_service` when issuing repeated requests.
- Batch processing: Use `tqdm` for progress tracking and user feedback

### Testing Approach
Typical users need not run deep tests for one-off examples. When changing core
code or utilities, run `make unit` (fast, offline tests). `make coverage` runs
coverage for those tests. `make test` includes live integration tests and must
not be run without explicit user confirmation for the target domain.
Alternatively, after activating the virtual environment, run
`python -m unittest discover -s five9/tests -p 'test_utils_*.py' -v`.
Keep unit tests independent of live API access.

### Domain Snapshots
- `Five9DomainConfig` class captures domain state to Git repository
- Default path: `domain_snapshots/<DOMAIN_NAME>/`
- Methods captured: Skills, Campaigns, IVRs, Users, Agent Groups, etc.
- Use for: Version control, disaster recovery, migration planning, auditing
- `examples/domain_config/domain_config_capture.py` generates IVR
  diagrams/docs by default (`--skip-ivr-documentation` to opt out)
- Before deleting or renaming a domain object, follow
  `OBJECT_DEPENDENCIES.md`. Capture current state, inspect reverse references,
  perform the listed live checks, and report unresolved coverage gaps. Do not
  interpret "no snapshot matches" as proof that an object is unused.
- Before requesting approval for a deletion, report the domain, exact target,
  discovered dependencies, planned detach or reassignment actions, backup
  path, and validation plan. An API "in use" fault is a safety signal, not a
  check to bypass.

## Common Tasks

### Adding a New API Method Wrapper
1. Check if method exists: `client.print_available_service_methods()`
2. Inspect method signature: `print(client.wsdl.dump())`
3. Create example in appropriate `examples/` subdirectory
4. Add unit test in `five9/tests/`
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
  - When comparing functions of the same name across scripts, offer a diff;
    explain what that means if the user is unfamiliar with it.
- Analyze variables: `ivr_utils.ivr_variable_usage(ivrs, verbose=True)`
- Generate diagrams: `ivr_diagram.ivr_to_svg(ivr.xmlDefinition)` or run
  `examples/ivrs/ivr_generate_diagrams.py`

### Bulk User Operations
- Template pattern: Get template user with `getUserInfo()`, copy roles/skills
- Use `tqdm` for progress: `with tqdm(total=len(users), desc="...", mininterval=1) as pbar:`
- Error handling: Catch per-user exceptions, continue processing others
- See `examples/user_management/bulk_user_create.py` for reference
- This is a bulk write operation; get confirmation before running it

## Important Conventions

### Error Handling
- Wrap client creation in try/except for `Five9ClientCreationError`
- Handle SOAP faults: `except zeep.exceptions.Fault as e:`
- Network errors: `except requests.exceptions.RequestException as e:`
- Per-item errors in bulk operations: Log and continue

### Logging
- Configure via `logging_level` kwarg to `Five9Client` (default: INFO)
- Use `logging` module, not `print()` for operational messages
- Format: `"%(asctime)s - %(levelname)s - %(message)s"`

### File Organization
- Keep examples self-contained and runnable
- Extract reusable logic to `five9/utils/`
- Private data (credentials, CSVs) goes in `private/` (git-ignored)
- Domain snapshots in `domain_snapshots/` (selectively committed)

### Naming Conventions
- Scripts: Descriptive snake_case (e.g., `bulk_user_create.py`)
- Functions: snake_case with clear verb prefixes (get_, create_, update_, delete_)
- Classes: PascalCase (e.g., `Five9Client`, `Five9DomainConfig`)
- Constants: UPPER_SNAKE_CASE (e.g., `ACCOUNTS`, `HOST_ALIAS`)

## Project-Specific Gotchas

1. **API Version**: Default is v13, but v4 still supported (limited features);
   treat `Five9Client.__init__` as authoritative over old comments saying v12
2. **Session Types**: Don't mix admin and statistics methods on same client
3. **Use the built-in proxy for every bulk/high-repeat API sequence.** Route
   each repeated SOAP call through `client.throttled_service`, including reads,
   writes, async submissions, and status polling, even when calls are spread
   across helpers. `client.service` is for isolated one-off calls, not loops.
   The proxy sleeps 0.3s before each call; don't remove it, monkey-patch
   around it, or shorten its delay to work around rate limits. If the user
   explicitly requests bypassing or shortening it, explain the risk of
   throttling or account lockout and get their informed confirmation first.
4. **Credentials**: NEVER commit `private/credentials.py` - it's git-ignored
   for security. Only `.github/copilot-instructions.md` is allowed through the
   `.github/` ignore rule; check tracking for other files in that folder.
5. **Virtual Environment**: Always activate `venvs/five9` before running scripts
6. **Zeep Caching**: First run may be slow while WSDL is fetched/cached
7. **Domain Name**: Available as `client.domain_name` after initialization (admin sessions only)

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
make unit                                          # Fast offline tests
python -m unittest discover -s five9/tests -p 'test_utils_*.py' -v
./five9/unittest_coverage.sh --report --fail-under=75
```

### Installation/Setup
```bash
git pull --ff-only                                 # Update after approval and checks below
pip install -e .                                   # Reinstall (preserves credentials)
F9_RESET_PRIVATE=1 pip install -e .               # Force credential template reset
```

### Checking for toolkit updates
When a newer helper or example might help with a user's task, occasionally
offer to check for repository updates; don't interrupt every conversation or
suggest that an update adds new Five9 API functionality. If the user agrees,
run `git fetch origin` and compare the local checkout with `origin/main`
(for example, `git log HEAD..origin/main --oneline`). Explain relevant new
utilities or examples in plain language. This check does not change the
user's working files. For downloads without a Git checkout, point the user
to the repository's GitHub page rather than assuming Git commands will work.
Never run `git pull` or change the checkout without the user's approval;
check for local modifications first and explain any risk of conflicts.
Before updating, verify the current branch and its configured upstream (the
remote branch it tracks) match the intended update source; do not assume a
custom branch tracks `origin/main`. With approval, use `git pull --ff-only`
on that verified tracking branch. This only advances the branch when no merge
is needed. If it refuses, stop and explain the problem; do not automatically
merge, rebase, reset, stash, or discard local work to force an update.

## Safety guardrails for AI agents

This repository can connect to real Five9 contact-center domains. Treat every
connected domain as potentially production, including `default_account`.

1. **Keep secrets out of chat and tracked files.** Never print, log, echo, or
   commit `private/credentials.py`, passwords, or API responses containing
   credentials or auth headers (`client.latest_request_headers` contains a
   Basic Auth header). Never ask users to paste credentials into chat. Refer
   them to the ignored credentials file, `--account_alias`, or the interactive
   `getpass` prompt instead. Never hardcode credentials in examples.
2. **Confirm before live writes.** Before executing any example or API call
   that creates, changes, or deletes domain configuration, get explicit user
   confirmation for the actual domain and intended effect. This includes bulk
   user scripts, campaign-profile mutations, `modifyVCCConfiguration`,
   `delete*` methods, and async CRUD. Prefer a dry run or a small test subset
   and recommend a sandbox/trial domain where possible.
   Before deleting or renaming an object, follow `OBJECT_DEPENDENCIES.md`:
   capture the current state, inspect reverse references and live checks,
   report any coverage gaps, and present the domain, exact target,
   dependencies, reassignment/detach plan, backup path, and validation plan
   before requesting approval. Do not treat "no snapshot matches" as proof
   of safety or work around an API "in use" fault.
3. **Respect throttling.** Route every repeated SOAP call through
   `client.throttled_service` (including reads, writes, async submissions,
   and polling across helpers). Do not remove or shorten its 300ms delay to
   evade rate limits without explaining the risk and getting informed consent.
4. **Escalate production deployments.** This is unsupported sample code;
   recommend Five9 Professional Services or a Technical Account Manager for
   production-grade integrations.
5. **Ask when in doubt.** For API calls that send data to a live domain or
   have other side effects beyond local files/git, clarify before acting.

## When Collaborating on This Repo

- **Adding Features**: Prioritize examples over modifying core `Five9Client` unless necessary
- **Breaking Changes**: Avoid breaking existing examples; maintain backward compatibility
- **Documentation**: Update `AGENTS.md` first when adding major features or
  patterns, then mirror the changes here
- **Testing**: Add unit tests for new utility functions; integration tests optional but encouraged
- **Credentials**: Never request or expect user credentials in code review
- **Dependencies**: Minimize new dependencies; justify additions in PR description

## API Documentation References
- Five9 Configuration Webservices API docs: Available in Five9 admin portal under Help
- WSDL location: `https://api.five9.com/wsadmin/v13/AdminWebService?wsdl&user=<username>`
- Zeep documentation: https://docs.python-zeep.org/

## Contact & Support
- **Disclaimer**: This is sample code, NOT officially supported by Five9
- For production use: Engage Five9 Professional Services or TAM team
- Issues/PRs: Welcome for bug fixes and enhancements
- Original Author: Andrew Willey (andrewawilley)
