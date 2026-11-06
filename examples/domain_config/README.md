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
retries, uses a `ThrottledServiceProxy`. Fixed pacing is the default and uses
`client.throttled_service`. Opt-in dynamic pacing uses a capture-owned proxy
with no fixed pause; the capture scheduler controls when each call starts.
It does not change the client's proxy or other examples' timing.

| Option | Default | Behavior |
| --- | --- | --- |
| `--call-delay` | `0.5` | Fixed pause, or initial spacing before dynamic limits are known; minimum 0.3. |
| `--dynamic-pacing` | Off | Target 95% of the tightest reported query rate, allowing spacing below 0.3 seconds. |
| `--query-limit-per-minute` | Unset | Personal read budget for this capture; a positive integer. Can lower, but never raise, the dynamic domain target. Applies in fixed mode too. |
| `--rate-limit-retries` | `3` | Additional attempts for a query-limit SOAP fault; 0 disables retries, maximum 10. |
| `--counter-check-interval` | `30` | Read attempts between usage checks; minimum 1. A check also runs at capture start. |

In fixed mode, the default pause is **0.5 seconds, not 0.8 seconds**, plus API
response time. An already-slower custom proxy adds its extra delay. These
settings govern capture reads, not the client's initial connection setup.

### Opt-in dynamic pacing

Use this mode when you know what other API processes are running and want to
make near-full use of the available limits:

```bash
python -m examples.domain_config.domain_config_capture --account_alias your_account_alias --dynamic-pacing
```

To reserve capacity for other processes, give this run a smaller personal budget:

```bash
python -m examples.domain_config.domain_config_capture --account_alias your_account_alias --dynamic-pacing --query-limit-per-minute 120
```

This caps the capture at 120 read attempts per minute, including usage checks
and retries. It does not reserve capacity on the server or coordinate other
processes. A stricter domain window still wins. Omit `--dynamic-pacing` to use
fixed pauses instead.

Dynamic pacing reads **all reported QUERY windows**, including zero-use ones,
and computes the most restrictive sustained rate using 95% of each limit. The
five-percent margin allows some timing uncertainty; it is not an allocation for
unknown traffic. Limits are not hardcoded to 180/minute. For example, a domain
reporting 600/minute can target 570/minute (about 0.105 seconds between calls),
unless an hourly/daily window or personal budget requires a slower rate.

Response time and local processing count toward the spacing between calls.
There are no catch-up bursts or parallel requests. If query limits are missing
or unusable, capture does not accelerate: it retains its current spacing or
the initial `--call-delay`, whichever is slower. Once limits are known,
`--call-delay` is not a floor in dynamic mode; use the personal budget to cap
the rate instead.

Dynamic pacing can shorten or remove the old 0.3-second pause. Other users'
traffic is invisible to this capture, so rate-limit faults or account lockout
remain possible despite pacing and backoff. Coordinate with other API users
before enabling it.

### Usage display and recovery

Counts returned by Five9 describe **the requesting user's usage**, while limits
are enforced across the domain. Other processes using this account may also
contribute to its counters. The display is not a domain-wide usage total or a
guarantee of remaining capacity.

Usage checks show only counters with nonzero usage, grouped by time window from
longest to shortest (for example, day, hour, then minute). Within each window,
the largest limits appear first. Aligned columns show the operation, calls used,
allowed limit, and percentage used; `HIGH` marks usage of 80% or more in fixed
mode and 98% or more in dynamic mode. Each check
produces one summary instead of a separate log line for every counter.

The CLI separates capture phases with blank lines and uses readable progress
labels. Routine messages omit timestamps and `INFO` prefixes; warnings and
errors keep their severity labels so they stand out.

Fixed mode raises its pause to at least 1 second when a QUERY counter reaches
80%, or after a query-limit fault, and keeps that slower pause for the instance.
Dynamic mode slows to at least twice its calculated target spacing when a QUERY
counter reaches 98%. An actual query-limit fault doubles its current spacing
(to at least 1 second). After the retry wait and 60 seconds without another
query-limit fault, healthy usage checks reduce that slowdown by 20% per check,
never exceeding the current domain target or personal budget. High counters
for other operation categories do not slow the read-only capture.

Both modes wait at least the reported query-limit window (never less than 60
seconds) before retrying a faulted read. Each retry doubles that wait and adds
0-5 seconds of random delay so simultaneous jobs are less likely to retry
together. Other SOAP faults are not retried.

Run only one capture per domain at a time and schedule it away from other
API-heavy jobs. Limits are shared with other integrations, so pacing does not
guarantee success. For busy domains, use a longer fixed pause such as
`--call-delay 1`, or a lower personal query budget in dynamic mode.
Do not repeatedly restart a failing capture without allowing usage to
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
