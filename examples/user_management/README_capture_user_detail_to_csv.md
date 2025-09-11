# capture_user_detail_to_csv.py

Comprehensive user export utility for Five9 domains. Supports:

- Targeted or full-domain user capture
- Large ("big") domain chunked retrieval to avoid timeouts
- Alphabetic OR zero‑padded numeric prefix enumeration (e.g. 000..999)
- Skipping early numeric ranges with `--numeric_prefix_start`
- Incremental append writing (safe partial progress)
- Configurable general user attributes (generalInfo fields)
- Explicit permission selection (namespaced as `role_permission` columns)
- Auto‑discovery of agent permissions (single batch mode only when no permissions provided)
- Optional media type enablement columns
- External JSON configuration file

## Output
A CSV file whose first row is a header. Columns include:

- General info fields you requested (e.g. `userName, firstName, lastName, EMail, active`)
- Zero or more media type columns: `media_enabled_<Type>` when `--include_media_types` or config flag used
- Permission columns namespaced with the role key: `agent_ReceiveTransfer`, `agent_SendMessages`, etc.

Permission values are the raw boolean (or string/number) returned by the API; blanks mean:
- User lacks that role
- Role has no such permission
- Permission was not in the selected list (for chunked mode) and auto-discovery was not active

## When To Use Big Domain Mode
`getUsersInfo()` may timeout for very large domains. Enabling `--big_domain` switches to incremental chunk retrieval and **writes each chunk immediately** so a mid-run failure still leaves prior data captured.

Two chunking strategies:
1. Default alphanumeric prefix iteration over: `A-Z a-z 0-9` (customizable in code if needed)
2. Numeric prefix enumeration using zero‑padded ranges (`--enumerate_numeric_prefixes`) – ideal for employeeID-style usernames like `102330@company.com`.

## JSON Configuration
Provide a JSON file (default: `user_capture_config.sample.json`) to avoid editing the script.

Example (`user_capture_config.sample.json`):
```
{
  "generalInfoFields": ["userName", "firstName", "lastName", "EMail", "active"],
  "permissions": {
    "agent": ["ReceiveTransfer", "SendMessages"]
  },
  "includeMediaTypes": false
}
```
Keys:
- `generalInfoFields`: list of user.generalInfo field names
- `permissions`: mapping roleKey -> list of permission types
- `includeMediaTypes`: boolean

CLI flag `--include_media_types` overrides the JSON flag if supplied.

## Command Line Arguments
(From `common_parser_arguments` plus script-specific additions)

| Argument | Default | Purpose |
|----------|---------|---------|
| `--username` | (env / credentials) | Five9 username (optional if alias used) |
| `--password` |  | Five9 password (optional if alias used) |
| `--account_alias` |  | Credential alias found in `private/credentials.py` |
| `--hostalias` | `us` | API host alias (us, ca, eu, frk, in) |
| `--filename` | `private/users_YYYY-MM-DD.csv` | Output CSV path |
| `--config` | `user_capture_config.sample.json` | JSON config path |
| `--include_media_types` | off | Include media type enablement flags |
| `--big_domain` | off | Enable chunked retrieval/write |
| `--enumerate_numeric_prefixes` | off | Use numeric enumeration instead of character set |
| `--numeric_prefix_width` | 3 | Width of zero‑pad for numeric enumeration (3 => 000..999) |
| `--numeric_prefix_start` | 0 | Starting numeric prefix (e.g. 100 skips 000–099) |

## Basic Usage
Export all users (single batch):
```
python capture_user_detail_to_csv.py --account_alias myAlias
```
Specify custom output file:
```
python capture_user_detail_to_csv.py --account_alias myAlias --filename exports/users_full.csv
```
Include media type enabled flags:
```
python capture_user_detail_to_csv.py --account_alias myAlias --include_media_types
```
Load fields/permissions from a custom config:
```
python capture_user_detail_to_csv.py --account_alias myAlias --config my_capture.json
```

## Big Domain (Alphabetic) Example
```
python capture_user_detail_to_csv.py --account_alias enterpriseA --big_domain --filename private/users_big.csv \
  --config user_capture_config.sample.json
```
Writes incrementally (overwrites file at first chunk, then appends).

## Big Domain Numeric Enumeration
For ID-based usernames (e.g. `123456@domain.com`):
```
python capture_user_detail_to_csv.py --account_alias enterpriseA \
  --big_domain --enumerate_numeric_prefixes --numeric_prefix_width 3 \
  --filename private/users_numeric.csv
```
Patterns requested: `000*`, `001*`, ..., `999*`.

Skip early ranges (start at 100):
```
python capture_user_detail_to_csv.py --account_alias enterpriseA \
  --big_domain --enumerate_numeric_prefixes --numeric_prefix_width 3 \
  --numeric_prefix_start 100 --filename private/users_numeric_100_plus.csv
```

## Combining JSON Config + Numeric Enumeration + Media Types
```
python capture_user_detail_to_csv.py --account_alias enterpriseA \
  --big_domain --enumerate_numeric_prefixes --numeric_prefix_start 200 \
  --include_media_types --config team_capture.json \
  --filename private/users_team_200_plus.csv
```

## Permission Columns & Namespacing
Each permission column is `role_permissionType` (e.g. `agent_ReceiveTransfer`). Empty cell reasons:
- Permission not in the supplied list (chunk mode never auto-discovers)
- Role absent for user
- Permission type not granted / emitted by API

### Auto-Discovery Caveat
Auto-discovery of permissions (when you omit `permissions` in config and run single batch) only collects **agent** role permissions and only when not in big domain mode.

## Resuming / Partial Data Strategy
If a chunked run fails:
1. The CSV already contains completed prefixes.
2. Re-run with the same arguments; it will overwrite file from the first chunk.
3. To implement *true* resume (skip existing prefixes), you can add logic to parse existing `userName` values and compute which prefixes remain — not currently implemented.

## Performance & Rate Limiting
- A 300ms sleep is applied between chunk calls to reduce rate limit risk; adjust if needed.
- Numeric enumeration can yield many empty responses quickly (fast but still sleeps). You can reduce delay for empty chunks if necessary.

## Troubleshooting
| Symptom | Possible Cause | Fix |
|---------|----------------|-----|
| CSV permission columns blank | Role missing or permission not in chosen list | Add permission to config `permissions` map |
| File only has first chunk | Script error mid-run | Inspect logs; rerun (data prior to failure retained) |
| No media columns | Flag/config not set | Use `--include_media_types` or set `includeMediaTypes: true` in JSON |
| Auto-discovery didn’t run | Big domain mode active | Provide explicit `permissions` in config |
| Unexpected timeout still | Chunks still too large | Increase granularity (e.g. move to numeric enumeration) |

## Sample Output (Truncated)
```
userName,firstName,lastName,EMail,active,agent_ReceiveTransfer
102330@fedex.com,Darlene,Zicha,102330@fedex.com,False,True
...
```

## Extending
Ideas:
- Add `--resume_from_pattern` to skip processed prefixes
- Write a sidecar JSON with summary stats
- Support multiple role blocks in config (e.g. supervisor, admin)
- Parallelize safe prefix subsets (be mindful of API limits)

## Safety Notes
- Chunk mode writes header only once; deletion of the file mid-run can cause a missing header for subsequent appended rows.
- Ensure credential storage in `private/credentials.py` is secured (not committed).

## Quick Start Recipe
```
cp examples/user_management/user_capture_config.sample.json my_capture.json
# Edit my_capture.json as needed
python capture_user_detail_to_csv.py --account_alias myAlias --config my_capture.json --big_domain --enumerate_numeric_prefixes --numeric_prefix_start 100
```

---
Maintained as part of the Five9 Configuration Webservices API Samples.
