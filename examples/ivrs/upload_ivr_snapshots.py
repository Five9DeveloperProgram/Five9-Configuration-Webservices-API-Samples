"""Upload IVR JSON snapshots to a destination domain.

Preview local snapshots without connecting to Five9:
    python examples/ivrs/upload_ivr_snapshots.py --source-dir private/ivr_exports

Create renamed copies after confirming the destination domain:
    python examples/ivrs/upload_ivr_snapshots.py --source-dir private/ivr_exports \
        --target-suffix " - Copy" --apply

Each JSON file must contain a name matching its filename and an xmlDefinition.
Only references to other selected IVRs are renamed. Other domain dependencies
must already exist and be reviewed separately before applying the upload.
"""

import json
import logging
from pathlib import Path
import xml.etree.ElementTree as ET

from five9.utils.common import common_parser_arguments, create_five9_client


def load_migration_set(source_dir, file_pattern="*.json"):
    """Return validated snapshot dictionaries keyed by their source names."""
    source_dir = Path(source_dir)
    migration_set = {}
    source_paths = sorted(source_dir.glob(file_pattern))
    if not source_paths:
        raise ValueError(f"No snapshots matching {file_pattern!r} in {source_dir}")

    for source_path in source_paths:
        source_name = source_path.stem
        with source_path.open(encoding="utf-8") as snapshot_file:
            snapshot = json.load(snapshot_file)

        if not isinstance(snapshot, dict):
            raise ValueError(f"Snapshot must be a JSON object: {source_path}")
        if snapshot.get("name") != source_name:
            raise ValueError(
                f"Snapshot name {snapshot.get('name')!r} does not match {source_name!r}"
            )
        if not snapshot.get("xmlDefinition"):
            raise ValueError(f"Snapshot has no xmlDefinition: {source_path}")
        ET.fromstring(snapshot["xmlDefinition"])
        if source_name in migration_set:
            raise ValueError(f"Duplicate snapshot name: {source_name!r}")
        migration_set[source_name] = snapshot

    return migration_set


def prepare_script(snapshot, name_map, destination_domain_id):
    """Prepare one script for the destination domain and renamed IVR set."""
    root = ET.fromstring(snapshot["xmlDefinition"])
    domain_id = root.find("domainId")
    if domain_id is None:
        raise ValueError(f"IVR {snapshot['name']!r} has no domainId element")
    domain_id.text = str(destination_domain_id)

    parents = {child: parent for parent in root.iter() for child in parent}
    rewritten_references = []
    for element in root.iter("name"):
        parent = parents.get(element)
        referenced_name = (element.text or "").strip()
        if (
            parent is not None
            and parent.tag == "ivrScript"
            and referenced_name in name_map
        ):
            element.text = name_map[referenced_name]
            rewritten_references.append((referenced_name, element.text))

    target_name = name_map[snapshot["name"]]
    return {
        "description": snapshot.get("description"),
        "name": target_name,
        "xmlDefinition": ET.tostring(root, encoding="unicode", xml_declaration=True),
    }, rewritten_references


def target_names(migration_set, target_suffix=""):
    """Preserve source names unless an optional destination suffix is supplied."""
    return {name: f"{name}{target_suffix}" for name in migration_set}


def dependency_order(migration_set):
    """Return source names with referenced child IVRs before their parents."""
    name_map = target_names(migration_set)
    dependencies = {}
    for source_name, snapshot in migration_set.items():
        _, references = prepare_script(snapshot, name_map, destination_domain_id=0)
        dependencies[source_name] = {old_name for old_name, _ in references}

    ordered = []
    visiting = set()
    visited = set()

    def visit(source_name):
        if source_name in visiting:
            raise ValueError(f"Circular IVR dependency involving {source_name!r}")
        if source_name in visited:
            return
        visiting.add(source_name)
        for dependency in sorted(dependencies[source_name]):
            visit(dependency)
        visiting.remove(source_name)
        visited.add(source_name)
        ordered.append(source_name)

    for source_name in migration_set:
        visit(source_name)
    return ordered


def confirm_destination(client, confirmed_domain=None):
    """Require the exact detected domain name before allowing writes."""
    print(f"Connected destination domain: {client.domain_name}")
    if confirmed_domain is None:
        confirmed_domain = input(
            "Type the exact destination domain name to create or update these IVRs: "
        )
    if confirmed_domain != client.domain_name:
        raise ValueError(
            f"Destination is {client.domain_name!r}, not confirmed domain "
            f"{confirmed_domain!r}"
        )
    return confirmed_domain


def apply_migration(
    client, migration_set, confirmed_domain, resume=False, target_suffix=""
):
    """Create and populate the destination scripts after safety checks."""
    if confirmed_domain != client.domain_name:
        raise ValueError(
            f"Destination is {client.domain_name!r}, not confirmed domain "
            f"{confirmed_domain!r}"
        )

    ordered_names = dependency_order(migration_set)
    name_map = target_names(migration_set, target_suffix)
    existing_scripts = client.throttled_service.getIVRScripts(namePattern=".*") or []
    existing_names = {script.name for script in existing_scripts}
    collisions = sorted(set(name_map.values()) & existing_names)
    if collisions and not resume:
        raise ValueError(
            "Refusing to overwrite existing destination IVRs: " + ", ".join(collisions)
        )
    if resume:
        logging.info("Resume mode: reusing %d existing target IVRs", len(collisions))

    prepared_scripts = {}
    for source_name, snapshot in migration_set.items():
        prepared_script, _ = prepare_script(snapshot, name_map, client.domain_id)
        prepared_scripts[source_name] = prepared_script

    logging.info(
        "Creating %d IVRs in domain %s", len(prepared_scripts), client.domain_name
    )
    for script in prepared_scripts.values():
        if script["name"] not in existing_names:
            client.throttled_service.createIVRScript(name=script["name"])

    for source_name in ordered_names:
        script = prepared_scripts[source_name]
        client.throttled_service.modifyIVRScript(scriptDef=script)
        logging.info("Saved IVR: %s", script["name"])


def print_plan(migration_set, source_dir, target_suffix=""):
    name_map = target_names(migration_set, target_suffix)
    print(f"Source directory: {source_dir}")
    print(f"Scripts selected: {len(migration_set)}")
    for source_name in dependency_order(migration_set):
        _, references = prepare_script(
            migration_set[source_name], name_map, destination_domain_id="DESTINATION"
        )
        print(f"  {source_name} -> {name_map[source_name]}")
        for old_reference, new_reference in references:
            print(f"    reference: {old_reference} -> {new_reference}")


if __name__ == "__main__":
    args = common_parser_arguments(
        additional_args=[
            {
                "name": "--source-dir",
                "type": Path,
                "required": True,
                "help": "Directory containing the IVR JSON snapshots to upload",
            },
            {
                "name": "--file-pattern",
                "default": "*.json",
                "help": "Snapshot filename glob within the source directory (default: *.json)",
            },
            {
                "name": "--target-suffix",
                "default": "",
                "help": "Optional suffix for destination IVR names; default preserves names",
            },
            {
                "name": "--apply",
                "action": "store_true",
                "help": "Create and save the planned IVRs in the destination domain",
            },
            {
                "name": "--confirm-domain",
                "default": None,
                "help": "Exact destination domain name; prompted for if omitted with --apply",
            },
            {
                "name": "--resume",
                "action": "store_true",
                "help": "Overwrite existing target IVR definitions after a partial run",
            },
        ]
    )
    try:
        scripts = load_migration_set(args.source_dir, args.file_pattern)
        print_plan(scripts, args.source_dir, args.target_suffix)
    except (ValueError, OSError, ET.ParseError) as error:
        logging.error("Cannot prepare IVR upload: %s", error)
        raise SystemExit(1)

    if args.apply:
        if args.resume:
            print("Resume mode will overwrite any existing target IVR definitions.")
        destination_client = create_five9_client(args)
        confirmed_domain = confirm_destination(destination_client, args.confirm_domain)
        apply_migration(
            destination_client,
            scripts,
            confirmed_domain,
            resume=args.resume,
            target_suffix=args.target_suffix,
        )
    else:
        print("Dry run only; no Five9 API connection or changes were made.")
