# IVR Variable Usage

This script extracts variable usage from Five9 IVR scripts and outputs the data to a CSV file.

## Usage

```sh
python ivr_variable_usage.py --username <Five9 username> [--password <Five9 password>] [--hostalias <host alias>] [--outputfile <output file>] [--verbose]
```

### Arguments

- `--username`: (Required) Five9 username.
- `--password`: (Optional) Five9 password. If not provided, you will be prompted to enter it.
- `--hostalias`: (Optional) Five9 host alias. Default is `us`. Options are `us`, `ca`, `eu`, `frk`, `in`.
- `--outputfile`: (Optional) Output CSV file name. Default is `private/ivr_variable_usage.csv`.
- `--verbose`: (Optional) Enable verbose output.

### Example

```sh
python ivr_variable_usage.py --username myusername --password mypassword --hostalias us --outputfile output.csv --verbose
```

## Output

The script generates a CSV file with the following columns:

- `Variable Name`: Name of the IVR variable.
- `IVR Script Name`: Name of the IVR script where the variable is used.

## Logging

The script logs the time taken to pull IVR scripts and the total runtime. If the `--verbose` flag is set, it also logs the extracted variable usage in JSON format.

# IVR Diagram & Documentation Generator

This script renders each Five9 IVR script into a styled SVG call-flow diagram and a Markdown prompt summary. It decodes TTS prompts, maps each module type to a distinct shape/color, lays out the flow, and documents every exit.

The diagram includes:

The generated SVG can be passed verbatim to Lucidchart via the Lucid connector's `lucid_convert_svg_to_diagram` tool. The script itself does not talk to Lucid — it only produces the artifacts.

Rendering is provided by the reusable `five9.utils.ivr_diagram` module (`ivr_to_svg()` / `ivr_to_text()`), which operates on an IVR's `xmlDefinition` string. The Markdown summary is focused on script variables, JavaScript functions, and foreign scripts in use. Domain capture can emit the same artifacts automatically — see `Five9DomainConfig(generate_ivr_diagrams=True)` in `examples/domain_config`.

High-level utility entry points:

- `capture_domain_ivrs(client, base_dir="private", name_pattern=".*")`
- `document_ivrs(ivrs, output_dir, name_pattern=".*")`
- `write_ivr_documentation(xml_definition, output_prefix, name=None)`

## Usage

```sh
python ivr_generate_diagrams.py --account_alias <alias> [--base-dir <dir>] [--name-pattern <regex>]
```

### Arguments

- `--account_alias`: (Optional) Alias for a stored credential object in `private/credentials.py`.
- `--username` / `--password`: (Optional) Provide credentials directly instead of an alias.
- `--hostalias`: (Optional) Five9 host alias. Default is `us`. Options are `us`, `ca`, `eu`, `frk`, `in`.
- `--base-dir`: (Optional) Base directory for output. A subfolder named for the Five9 domain is created inside it. Default is `private` (git-ignored).
- `--name-pattern`: (Optional) Regex to filter IVR script names. Default is all scripts.

### Example

```sh
python ivr_generate_diagrams.py --account_alias default_account --name-pattern "^Main"
```

## Output

Files are written to `<base-dir>/<Five9 domain name>/ivr-documentation/<timestamp>/`. For each matching IVR script:

- `<name>.svg`: styled call-flow diagram, ready for Lucid import.
- `<name>.md`: per-module decoded prompts, branch transitions, and a Script Variables inventory (diff-friendly documentation).

The timestamped folder uses the current run time, so repeated exports do not overwrite previous diagrams.

## Domain Capture Integration

`examples/domain_config/domain_config_capture.py` now generates IVR SVG/Markdown documentation during domain capture by default.

To skip that behavior on a capture run:

```sh
python examples/domain_config/domain_config_capture.py --account_alias default_account --skip-ivr-documentation
```

## Credit

The SVG layout and rendering engine was originally written as a standalone `five9_to_lucid.py` utility by a Five9 colleague and adapted into this library.

# Skill Transfer Module Usage

This script extracts skill transfer modules from a Five9 XML response and outputs the data to a CSV file.


## Usage

```sh
python skill_transfer_module_usage.py --username <Five9 username> [--password <Five9 password>] [--hostalias <host alias>] [--output <output file>] [--verbose]
```

### Arguments

- `--username`: (Required) Five9 username.
- `--password`: (Optional) Five9 password. If not provided, you will be prompted to enter it.
- `--hostalias`: (Optional) Five9 host alias. Default is `us`. Options are `us`, `ca`, `eu`, `frk`, `in`.
- `--output`: (Optional) Output CSV file name. Default is `private/ivr_skill_transfer_modules.csv`.
- `--verbose`: (Optional) Enable verbose output.

### Example

```sh
python skill_transfer_module_usage.py --username myusername --password mypassword --hostalias us --output output.csv --verbose
```

## Output

The script generates a CSV file with the following columns:

- `IVR Script`: Name of the IVR script.
- `Skill Transfer Module Name`: Name of the skill transfer module.
- `Skill Target`: Name of the skill target.
- `Target Type`: Type of the skill target (skill or variable).
- `Skill Target Order`: Order of the skill target.

## Logging

The script logs the time taken to pull IVR scripts and the total runtime. If the `--verbose` flag is set, it also logs the extracted skill transfer modules in JSON format.
