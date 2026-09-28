# Five9 Object Dependencies and Safe Deletion

Use this guide before deleting or renaming a Five9 domain object. Five9 may
reject a deletion while an object is in use, but a rejected request should be
treated as a final safety net, not as the dependency discovery process.

This repository is sample code and does not provide a complete Five9 dependency
engine. Relationships vary by object type and API version, and some references
are embedded as names in IVR XML, filters, or connector settings. Confirm the
current behavior in the Five9 Configuration Webservices API documentation and,
for production workflows, with Five9 Professional Services or your Technical
Account Manager (TAM).

## How to read the relationships

This guide writes relationships as:

```text
referencing object -> referenced object
```

For example, `campaign -> campaign profile` means the campaign stores the
profile name. Before deleting the profile, find every campaign that points to
it and reassign or remove that reference. It does **not** mean that deleting the
campaign also deletes the profile.

Dependencies should be handled from the outside in:

1. Find objects that reference the deletion target.
2. Decide whether to reassign, detach, disable, or delete each referencing
   object.
3. Apply and verify those changes.
4. Delete the now-unreferenced target.

Never assume that deleting a referenced object will cascade safely.

## Dependency matrix

The fields and files below reflect objects captured by
`five9.utils.domain_capture.Five9DomainConfig`. File names are relative to a
single, freshly captured `domain_snapshots/<DOMAIN_NAME>/` directory.

| Object to delete or rename | Objects that can reference it | Where to check | Coverage |
| --- | --- | --- | --- |
| Campaign profile | Inbound and outbound campaigns | `campaigns_inbound/*.json` and `campaigns_outbound/*.json`: `profileName` | Captured directly |
| Campaign | Lists, skills, dispositions, and external scripts/connectors | Query campaign associations; search `getWebConnectors.json`, `ivrs/*.json`, and operational scripts for the campaign name | Reverse references are not completely captured |
| IVR script | Inbound campaigns | `campaigns_inbound/*.json`: `defaultIvrSchedule.ivrSchedule.scriptName` and any additional schedule entries | Captured directly |
| IVR script | Parent IVR scripts | `ivrs/*.json`: `xmlDefinition` foreign-script nodes containing `data/ivrScript/name`; generated IVR Markdown also lists foreign scripts | Captured directly |
| Prompt/audio file | IVR scripts | `ivrs/*.json`: `xmlDefinition` `filePrompt` nodes and prompt names; generated diagrams show `[File: <name>]` | Captured directly |
| Prompt/audio file | Skills or other media settings | Inspect `skills_info/*.json`, the live object detail, and the Admin UI | Possible relationship; not fully represented by current snapshots |
| Skill | Users | `skills_info/*.json`: each skill's `users` entries | Captured directly |
| Skill | IVR scripts | `ivrs/*.json`: `skillTransfer` nodes, including `listOfSkillsEx` and `vmSkillBox` | Captured directly |
| Skill | Campaigns | Inspect campaign details and the Admin UI/API association used by `addSkillsToCampaign` and `removeSkillsFromCampaign` | Association exists; current snapshot does not provide a complete reverse lookup |
| Disposition | Campaign wrap-up settings | `campaigns_inbound/*.json` and `campaigns_outbound/*.json`: `callWrapup.dispostionName` (the API field is spelled this way) | Captured directly |
| Disposition | Campaign profile disposition sets | Query `getCampaignProfileDispositions` for each profile | Requires an extra query |
| Disposition | Call variables and web connectors | `getCallVariableGroups.json`: `dispositions`; `getWebConnectors.json`: `triggerDispositions` | Captured directly |
| List | Campaigns | Query `getListsForCampaign` for each campaign | Requires an extra query |
| List | Web connectors and scripts | Search `getWebConnectors.json` and `ivrs/*.json` for list-name constants, URLs, or parameters | String reference; manual review required |
| Contact field / CRM field | Campaign profile filters and ordering | `campaign_profile_filters/*.json`: `leftValue` and `orderByFields` | Captured directly |
| Contact field / CRM field | IVR scripts and web connectors | Search `ivrs/*.json` CRM lookup/update nodes and `getWebConnectors.json` variables | Captured as names/strings; manual review required |
| Call variable or call-variable group | IVR scripts and web connectors | Search `ivrs/*.json`, `getWebConnectors.json`, `getCallVariables.json`, and `getCallVariableGroups.json` | Captured as names/strings; manual review required |
| User | Skills and agent groups | `skills_info/*.json`: `users`; `getAgentGroups.json`: `agents` | Captured directly |
| User | Object ownership, roles, and other assignments | Query `getUserInfo`; check IVR ownership and the Admin UI | Current domain capture does not snapshot individual user details or all ownership links |
| User profile | Users | Query `getUsersInfo`/`getUserInfo` and inspect `generalInfo.userProfileName` | Requires an extra query |
| Agent group | Users/agents | `getAgentGroups.json`: `agents`; confirm current membership live | Captured directly |
| Web connector | Call variables, contact fields, dispositions, and list/campaign names stored in its settings | `getWebConnectors.json`: `variables`, `triggerDispositions`, constants, and URLs | Captured, but many references are plain strings |

The table is intentionally conservative. A relationship marked "captured
directly" means this repository has observed the named field in captured API
objects; it does not guarantee that the table lists every place Five9 can store
that reference.

## Known dependency chains

Common chains can span more than one object:

```text
inbound campaign -> IVR -> child IVR
                        -> prompt
                        -> skill -> user
                        -> contact field

campaign -> campaign profile -> disposition
                             -> contact field

campaign -> list
web connector -> disposition / call variable / contact field / list name
```

Follow the full chain before changing a shared object. A prompt or skill that
looks unused by campaigns can still be reached through an IVR.

## Snapshot and search workflow

1. Confirm the account alias, API hostname/region, and `client.domain_name`.
   There is no reliable API-only test that distinguishes a sandbox from a
   production domain.
2. Capture the current domain configuration before making changes. Use
   `examples/domain_config/domain_config_capture.py`; enable its IVR
   documentation so child scripts, prompts, and skill transfers are easier to
   review.
3. Work only from the newest snapshot for the target domain. Older snapshots
   are useful for recovery, but they can produce stale matches.
4. Search for the exact object name in JSON, IVR XML, and generated IVR
   Markdown. For example:

   ```bash
   rg -n --fixed-strings 'Exact Object Name' 'domain_snapshots/<DOMAIN_NAME>'
   ```

5. Classify each match as a structured reference, a string reference, or an
   incidental mention such as a description. Do not automatically rewrite
   every text match.
6. Run the object-specific live checks from the matrix. In particular, query
   campaign lists, campaign profile dispositions, users/user profiles, and
   ownership because the normal snapshot is incomplete in those areas.
7. Produce a dependency report before proposing a mutation. Record the target,
   its type, each referencer, the field or API that proved the relationship,
   and the planned replacement or detach action.

`METHOD_DEPENDENCIES` in `five9/utils/domain_capture.py` only controls which
methods are fetched together. It is **not** a reverse-dependency map and must
not be used to decide that an object is safe to delete.

## Safe deletion checklist

- Prefer a sandbox/trial domain and a single test object first.
- Back up the target object's JSON/XML and every object that will be modified.
- Stop affected campaigns when the operation or Five9 UI requires it. The
  repository's contact-field removal example stops campaigns before deleting
  fields and then verifies that they restart.
- Reassign or detach references before deleting the target. Preserve the
  original values in the dependency report so the change can be reversed.
- Use a dry run that reports intended API calls without making them whenever a
  script supports it.
- Get explicit operator confirmation of the domain and exact changes before
  any create, modify, or delete API call. This is required even when an AI
  agent found no dependencies.
- Use `client.throttled_service` for loops or bulk checks so dependency
  discovery does not bypass the repository's API rate limiting.
- Delete one object at a time. Treat an "in use" SOAP fault as evidence of a
  missed dependency; do not retry repeatedly or attempt to bypass the check.
- Re-query the deleted object and all changed referencers. Restart any
  previously running campaigns, verify their state, and capture a new snapshot.

## Minimum report for an AI agent

Before asking for permission to delete an object, an AI agent should report:

```text
Domain: <confirmed domain and region>
Target: <object type and exact name>
Snapshot: <path and capture time>
Structured references: <objects and fields>
String references: <objects and values requiring human review>
Live checks performed: <API methods, or "not performed">
Planned detach/reassignment actions: <ordered list>
Backup/recovery path: <snapshot or export>
Validation plan: <queries and operational checks>
```

Finding no matches is not approval to delete. The operator must still confirm
the domain and authorize the write operation, and the agent must state which
live checks were not performed.

## Important limitations

- Five9 can add or change fields and validation rules independently of this
  sample repository.
- Snapshot files are point-in-time data and may be stale immediately after
  capture if another administrator changes the domain.
- Some relationships are exposed only through per-object API calls or the
  Admin UI; a broad text search cannot prove that an object is unused.
- Names embedded in XML, URLs, JavaScript, filter expressions, or constants do
  not have enforced foreign-key semantics and require human review.
- Do not assume that Five9 blocks every unsafe deletion, that a deletion
  cascades, or that restoring one JSON object restores all related state.