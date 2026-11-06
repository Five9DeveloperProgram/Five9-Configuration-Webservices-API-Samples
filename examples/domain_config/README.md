# Domain config snapshot capture example

Before deleting or renaming a domain object, use the repository's
[object dependency and safe deletion guide](../../OBJECT_DEPENDENCIES.md).
It describes which snapshot files and additional live API checks can reveal
references to the target object.

The domain capture example can be run from the command line. Use an account
alias stored in `private/credentials.py`, or supply `--username` and enter the
password at the hidden prompt. Avoid passing passwords on the command line,
where they may be retained in shell history.

## Rate limits and capture settings

From the repository root, activate the environment and run the example:

```bash
source venvs/five9/bin/activate
python -m examples.domain_config.domain_config_capture --account_alias your_account_alias --call-delay 0.5
```

This connects to the domain associated with the alias. Confirm that it is the
intended domain before running it. Capture reads domain configuration and writes
local files; it does not update the domain.

Every capture read, including per-object detail calls, counter checks, and
retries, uses `client.throttled_service`.

| Option | Default | Behavior |
| --- | --- | --- |
| `--call-delay` | `0.5` | Total pause per read attempt, including the standard proxy's 0.3 seconds; minimum 0.3. |
| `--rate-limit-retries` | `3` | Additional attempts for a query-limit SOAP fault; 0 disables retries, maximum 10. |
| `--counter-check-interval` | `30` | Read attempts between usage checks; minimum 1. A check also runs at capture start. |

The default pause is **0.5 seconds, not 0.8 seconds**, plus API response time.
An already-slower custom proxy adds its extra delay; capture never shortens it.
These settings govern capture reads, not the client's initial connection setup.

Usage checks show only counters with nonzero usage, grouped by time window from
longest to shortest (for example, day, hour, then minute). Within each window,
the largest limits appear first. Aligned columns show the operation, calls used,
allowed limit, and percentage used; `HIGH` marks usage of 80% or more. Each check
produces one summary instead of a separate log line for every counter.

The CLI separates capture phases with blank lines and uses readable progress
labels. Routine messages omit timestamps and `INFO` prefixes; warnings and
errors keep their severity labels so they stand out.

At 80% of any reported limit, or after
a query-limit fault, capture raises its pause to at least 1 second for the
remainder of that instance's lifetime. For the reported query-limit fault,
capture waits at least the specified window (never less than 60 seconds) before
retrying the same read. Each retry doubles that wait and adds 0-5 seconds of
random delay so simultaneous jobs are less likely to retry together. Other SOAP
faults are not retried.

Run only one capture per domain at a time and schedule it away from other
API-heavy jobs. Limits are shared with other integrations, so pacing does not
guarantee success. For busy domains, start with `--call-delay 1` or increase it
further. Do not repeatedly restart a failing capture without allowing usage to
subside. IVR diagrams are generated locally from captured XML; skipping them
does not save API calls.

## Incomplete captures

A failed read stops capture instead of skipping objects and committing a partial
snapshot. The CLI exits with status 1. During capture, and after failure, the
snapshot folder contains `CAPTURE_INCOMPLETE.txt`; it is removed on success.
Serialization failures also prevent a snapshot commit. Optional IVR diagram
generation retains its existing behavior: a failed diagram is reported and
skipped without failing the configuration capture.

**The working files may be partial:** capture still clears the previous working
files before retrieving the new configuration. Previous committed snapshots
remain in the snapshot folder's Git history, but the working directory must not
be used as a complete backup while the marker exists. Do not manually commit
partial files. Resolve the failure, allow API usage to subside, and rerun the
capture; a successful run rebuilds the files and creates a new snapshot commit.

## Captured details

Detail capture uses `tqdm` progress bars for campaigns, campaign profile filters,
skills, and IVRs, showing completed counts and estimated time remaining instead
of printing every object name. Rate-limit warnings and errors remain visible.

Certain methods such as getCampaigns, getSkills, and getCampaignProfiles respond with a configuration object that requires an additional call to a corresponding detail method to obtain more information about the target objects.  In these cases, the script is configured to iterate through the objects in the response and store the additional detail in a subfolder.  For the getCampaigns method, the method needed to obtain the campaign details depends on the campaign type (inbound or outbound).  In this case, it will store the campaign details in a campaigns_inbound and campaigns_outbound folder accordingly.  

The getIVRScripts method returns all IVRs in a single object, so this script iterates through all of the IVRs returned and stores them in individual files in the ivrs folder.  
