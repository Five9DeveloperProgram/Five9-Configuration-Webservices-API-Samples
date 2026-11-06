import datetime
import json
import logging
import math
import os
import random
import re
import shutil
import time

from git import Repo
from git.exc import InvalidGitRepositoryError
import zeep
import zeep.helpers
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from five9 import five9_session
from .campaign_profile_comprehension import demystify_filter
from . import ivr_diagram

API_SLEEP_INTERVAL = 0.3
DYNAMIC_TARGET_UTILIZATION = 0.95
LOGGER = logging.getLogger(__name__)
QUERY_LIMIT_FAULT = re.compile(
    r"(\d+)\s+seconds?\s+limit\s+\(\d+\)\s+for\s+query\s+operation\s+is\s+reached",
    re.IGNORECASE,
)

REPO_PATH = "domain_snapshots"
INCOMPLETE_MARKER = "CAPTURE_INCOMPLETE.txt"

METHOD_DEFAULT_ARGS = {
    "getAgentGroups": ".*",
}

DETAIL_LABELS = {
    "campaigns_outbound": "Outbound campaigns",
    "campaigns_inbound": "Inbound campaigns",
    "campaign_profile_filters": "Campaign profile filters",
    "skills_info": "Skills",
    "ivrs": "IVR scripts",
}

# Order of aquisition matters for purpose of syncing
METHODS = [
    "getAvailableLocales",
    "getDialingRules",
    "getSkills",
    "getPrompts",
    "getDispositions",
    "getWebConnectors",
    "getCallVariableGroups",
    "getCallVariables",
    "getContactFields",
    "getAgentGroups",
    "getCampaignProfiles",
    "getCampaigns",
    "getIVRScripts",
    "getSpeedDialNumbers",
    "getUserProfiles",
]

METHOD_DEPENDENCIES = {
    "getCampaignProfiles": ["getCampaigns"],
}


class DomainCaptureError(RuntimeError):
    """The capture did not finish and must not be used as a complete snapshot."""


class Five9DomainConfig:
    """Capture domain objects with paced reads and bounded query-limit retries.

    Fixed pacing includes the client's proxy pause in ``call_delay``. Opt-in
    dynamic pacing uses a capture-owned proxy and derives request spacing from
    the reported query limits, including response and local processing time.
    ``query_limit_per_minute`` caps this capture's reads in either mode.
    """

    def __init__(
        self,
        client=None,
        username=None,
        password=None,
        account=None,
        api_hostname_alias=None,
        sync_target_domain=None,
        methods=METHODS,
        generate_ivr_diagrams=False,
        call_delay=0.5,
        rate_limit_retries=3,
        counter_check_interval=30,
        dynamic_pacing=False,
        query_limit_per_minute=None,
    ):
        if not math.isfinite(call_delay) or call_delay < API_SLEEP_INTERVAL:
            raise ValueError("call_delay must be finite and at least 0.3 seconds")
        if not isinstance(rate_limit_retries, int) or not 0 <= rate_limit_retries <= 10:
            raise ValueError("rate_limit_retries must be an integer between 0 and 10")
        if not isinstance(counter_check_interval, int) or counter_check_interval < 1:
            raise ValueError("counter_check_interval must be a positive integer")
        if query_limit_per_minute is not None and (
            isinstance(query_limit_per_minute, bool)
            or not isinstance(query_limit_per_minute, int)
            or query_limit_per_minute < 1
        ):
            raise ValueError("query_limit_per_minute must be a positive integer")
        self.call_delay = call_delay
        self.dynamic_pacing = dynamic_pacing
        self._initial_call_delay = call_delay
        self._personal_interval = (
            60.0 / query_limit_per_minute if query_limit_per_minute else 0.0
        )
        self._query_interval = None
        self._last_request_started = None
        self._backoff_interval = 0.0
        self._recover_after = 0.0
        self._last_reported_interval = call_delay
        self.rate_limit_retries = rate_limit_retries
        self.counter_check_interval = counter_check_interval
        self._calls_since_counter_check = 0
        self._last_api_method = None
        self.client = client
        self.sync_target_domain = sync_target_domain
        self.methods = methods
        self.generate_ivr_diagrams = generate_ivr_diagrams

        self.domain_objects = {}

        self.domain_path = None

        self.vccConfig = None
        self.repo = None

        LOGGER.debug("API host alias: %s", api_hostname_alias)

        if client is None:
            LOGGER.info("\nConnecting to Five9...\n")
            self.client = five9_session.Five9Client(
                five9username=username,
                five9password=password,
                account=account,
                api_hostname_alias=api_hostname_alias,
            )
        else:
            self.client = client

        if self.client is not None:
            LOGGER.info(
                "Capture pacing: %s.\n",
                (
                    "dynamic, targeting 95% of reported query limits"
                    if self.dynamic_pacing
                    else f"fixed, {call_delay:g}-second pause"
                ),
            )
            if query_limit_per_minute is not None:
                LOGGER.info(
                    "Personal budget: at most %d reads/minute.\n",
                    query_limit_per_minute,
                )
            self._capture_service = (
                five9_session.ThrottledServiceProxy(
                    self.client.service, delay_seconds=0
                )
                if self.dynamic_pacing
                else self.client.throttled_service
            )
            # check for methods that have dependencies, add dependencies to methods list
            for method in methods:
                if method in METHOD_DEPENDENCIES:
                    for dependency in METHOD_DEPENDENCIES[method]:
                        if dependency not in methods:
                            methods.append(dependency)

            self.getVCCConfiguration()

    def sync_to_target_domain(self, sync_objects=[]):
        """Method to run the domain object sync methods that are implemented.  If no sync_objects are provided, will run all sync methods"""

        self.sync_methods = {
            "campaignProfiles": self.sync_campaignProfiles,
        }

        if self.sync_target_domain is not None:
            if len(sync_objects) == 0:
                sync_objects = self.sync_methods.keys()
            for sync_object in sync_objects:
                sync_method = self.sync_methods[sync_object]
                print(f"SYNC - {sync_object}")
                sync_method()

    def _call_service(self, method, *args, **kwargs):
        if self._calls_since_counter_check >= self.counter_check_interval:
            self._check_call_counters()
        return self._request(method, *args, **kwargs)

    def _request(self, method, *args, **kwargs):
        self._last_api_method = method
        for attempt in range(self.rate_limit_retries + 1):
            self._wait_before_request()
            self._calls_since_counter_check += 1
            try:
                return getattr(self._capture_service, method)(*args, **kwargs)
            except zeep.exceptions.Fault as error:
                match = QUERY_LIMIT_FAULT.search(str(error))
                if match is None or attempt == self.rate_limit_retries:
                    raise
                wait_seconds = max(60, int(match.group(1))) * 2**attempt
                wait_seconds += random.uniform(0, 5)
                self.call_delay = max(
                    self.call_delay * (2 if self.dynamic_pacing else 1), 1.0
                )
                self._backoff_interval = self.call_delay
                self._recover_after = time.monotonic() + wait_seconds + 60
                LOGGER.warning(
                    "Five9's read limit was reached (%s).\n"
                    "Waiting %.1f seconds, then trying again (%d of %d).\n",
                    method,
                    wait_seconds,
                    attempt + 1,
                    self.rate_limit_retries,
                )
                time.sleep(wait_seconds)

    def _wait_before_request(self):
        proxy_pause = 0.0 if self.dynamic_pacing else API_SLEEP_INTERVAL
        extra_pause = 0.0 if self.dynamic_pacing else self.call_delay - proxy_pause
        interval = max(
            self._personal_interval, self.call_delay if self.dynamic_pacing else 0
        )
        if self._last_request_started is None:
            extra_pause = max(extra_pause, interval - proxy_pause)
        else:
            elapsed = time.monotonic() - self._last_request_started
            extra_pause = max(extra_pause, interval - elapsed)
        time.sleep(max(0.0, extra_pause))
        self._last_request_started = time.monotonic()

    def _update_dynamic_pacing(self, counters):
        if not self.dynamic_pacing:
            return
        intervals = []
        high_query_usage = False
        for window in counters or []:
            for state in window.get("callCounterStates") or []:
                if str(state["operationType"]).upper() != "QUERY":
                    continue
                if window["timeout"] <= 0 or state["limit"] <= 0:
                    continue
                intervals.append(
                    window["timeout"] / (DYNAMIC_TARGET_UTILIZATION * state["limit"])
                )
                high_query_usage |= state["value"] >= 0.98 * state["limit"]
        if not intervals:
            self.call_delay = max(
                self.call_delay, self._initial_call_delay, self._personal_interval
            )
            return
        self._query_interval = max(self._personal_interval, *intervals)
        if high_query_usage:
            self._backoff_interval = max(
                self._backoff_interval, self._query_interval * 2
            )
        elif time.monotonic() >= self._recover_after:
            self._backoff_interval *= 0.8
        self.call_delay = max(self._query_interval, self._backoff_interval)
        if abs(self.call_delay - self._last_reported_interval) >= max(
            0.01, self._last_reported_interval * 0.1
        ):
            LOGGER.info(
                "Capture pacing: up to %.1f reads/minute (%.3f-second target spacing).\n",
                60 / self.call_delay,
                self.call_delay,
            )
            self._last_reported_interval = self.call_delay

    def _check_call_counters(self):
        counters = zeep.helpers.serialize_object(
            self._request("getCallCountersState"), dict
        )
        self._calls_since_counter_check = 0
        self._update_dynamic_pacing(counters)
        sections = []
        high_usage = False
        for window in sorted(
            counters or [], key=lambda item: item["timeout"], reverse=True
        ):
            active_states = sorted(
                (
                    state
                    for state in window.get("callCounterStates") or []
                    if state["value"] != 0
                ),
                key=lambda state: (-state["limit"], str(state["operationType"])),
            )
            if not active_states:
                continue
            seconds = window["timeout"]
            window_label = f"{seconds:,} seconds"
            for duration, unit in (
                (86400, "day"),
                (3600, "hour"),
                (60, "minute"),
                (1, "second"),
            ):
                if seconds >= duration and seconds % duration == 0:
                    count = seconds // duration
                    window_label = f"{count:,} {unit}{'s' if count != 1 else ''}"
                    break
            name_width = max(
                14, *(len(str(state["operationType"])) for state in active_states)
            )
            rows = [
                f"  {window_label} window",
                f"    {'Operation':<{name_width}} {'Used':>10} / {'Limit':<10} {'Usage':>6}",
            ]
            for state in active_states:
                limit = state["limit"]
                value = state["value"]
                percentage = f"{value / limit:.1%}" if limit > 0 else "n/a"
                threshold = 0.98 if self.dynamic_pacing else 0.8
                is_high = limit > 0 and value >= threshold * limit
                high_usage = high_usage or (
                    is_high and str(state["operationType"]).upper() == "QUERY"
                )
                operation = str(state["operationType"]).replace("_", " ").capitalize()
                rows.append(
                    f"    {operation:<{name_width}} {value:>10,} / {limit:<10,} "
                    f"{percentage:>6}{'  HIGH' if is_high else ''}"
                )
            sections.append("\n".join(rows))
        if sections:
            LOGGER.info(
                "\nYour API usage / Domain limit\n"
                "Other users' activity is not included in these counts.\n\n%s\n",
                "\n\n".join(sections),
            )
        if high_usage:
            if not self.dynamic_pacing:
                self.call_delay = max(self.call_delay, 1.0)
            LOGGER.warning(
                "High query usage. Capture %s: %.3f seconds per request.\n",
                "target spacing" if self.dynamic_pacing else "pause",
                self.call_delay,
            )

    def getVCCConfiguration(self):
        """Method to get the VCC Configuration for the domain and create the domain snapshot folder"""

        self.vccConfig = self._call_service("getVCCConfiguration")

        # One stable folder per domain so the git history accumulates across
        # captures and `git diff` / `git log` show what changed between runs.
        # (Use the current working directory, not the package location.)
        self.domain_path = os.path.join(
            os.getcwd(),
            REPO_PATH,
            f"{self.vccConfig.domainName}",
        )

        if os.path.exists(self.domain_path):
            LOGGER.debug("Refreshing snapshot working files in %s", self.domain_path)
            # Remove old files so objects deleted in the domain show up as
            # deletions in git. The .git folder (history) is never touched.
            for name in os.listdir(self.domain_path):
                if name in (".git", ".gitignore"):
                    continue
                path = os.path.join(self.domain_path, name)
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
        else:
            os.makedirs(self.domain_path, exist_ok=True)

        try:
            self.repo = Repo(self.domain_path)
            LOGGER.debug("Using snapshot history in %s", self.domain_path)
        except InvalidGitRepositoryError:
            self.repo = Repo.init(self.domain_path)
            # set the "longpaths=true" option for the repo (required for Windows
            # to support long names of objects and the filenames created)
            self.repo.git.config("core.longpaths", "true")
            self.repo.git.add(A=True)
            self.repo.index.commit("Initial Commit")
            LOGGER.debug("Created snapshot history in %s", self.domain_path)

        self._mark_capture_incomplete()

    def _mark_capture_incomplete(self):
        with open(os.path.join(self.domain_path, INCOMPLETE_MARKER), "w") as marker:
            marker.write(
                "Capture is in progress or failed. Do not use these working files "
                "as a complete snapshot. Previous committed snapshots remain in "
                "Git history. Rerun the capture after resolving the failure.\n"
            )

    def write_object_to_target_path(
        self,
        target_path,
        domain_object,
        sort_keys=True,
        indent=4,
        toJson=True,
        filetype="txt",
    ):
        output_string = ""

        def fix_datetimes(obj):
            if isinstance(obj, dict):
                return {k: fix_datetimes(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [fix_datetimes(i) for i in obj]
            elif isinstance(obj, datetime.datetime):
                return obj.isoformat()
            elif isinstance(obj, datetime.date):
                return obj.isoformat()
            else:
                return obj

        if toJson == True:
            filetype = "json"
            clean_object = fix_datetimes(domain_object)
            output_string = json.dumps(
                clean_object, sort_keys=sort_keys, indent=indent
            )
        else:
            output_string = domain_object

        with open(f"{target_path}.{filetype}", "w") as outputFile:
            outputFile.write(output_string)

        return True

    def get_config_object_detail(
        self, parent_method_name, subfolder_name, method_response=None, vcc_method=None
    ):
        subfolder_path = os.path.join(self.domain_path, subfolder_name)

        os.makedirs(os.path.dirname(subfolder_path), exist_ok=True)
        self.domain_objects[f"{parent_method_name}_{subfolder_name}"] = {}

        with logging_redirect_tqdm(), tqdm(
            method_response or [],
            desc=DETAIL_LABELS.get(subfolder_name, subfolder_name.replace("_", " ")),
            unit="item",
            mininterval=1,
            dynamic_ncols=True,
        ) as objects:
            for domain_object in objects:
                object_name = domain_object.name
                if vcc_method is not None:
                    domain_object = self._call_service(vcc_method, object_name)
                self.domain_objects[f"{parent_method_name}_{subfolder_name}"][
                    object_name
                ] = zeep.helpers.serialize_object(domain_object, dict)
                target_path = os.path.join(subfolder_path, object_name)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                captured_object = self.domain_objects[
                    f"{parent_method_name}_{subfolder_name}"
                ][object_name]
                self.write_object_to_target_path(target_path, captured_object)

                if self.generate_ivr_diagrams and subfolder_name == "ivrs":
                    self.write_ivr_documentation(
                        target_path, object_name, captured_object
                    )

    def write_ivr_documentation(self, target_path, ivr_name, captured_ivr):
        """Emit an SVG call-flow and a Markdown prompt summary alongside the
        captured IVR JSON. Enabled by ``generate_ivr_diagrams=True``.

        Failures for a single IVR are logged and skipped so one malformed
        script never aborts a full domain capture.
        """
        xml_definition = captured_ivr.get("xmlDefinition")
        if not xml_definition:
            return
        try:
            ivr_diagram.write_ivr_documentation(
                xml_definition,
                target_path,
                name=ivr_name,
            )
            LOGGER.debug("Generated diagram and documentation for %s", ivr_name)
        except Exception as e:
            LOGGER.warning("Skipped diagram for %s: %s", ivr_name, e)

    def get_domain_objects(self, methods=None):
        if methods is None:
            methods = self.methods
        if self.client is not None:
            try:
                LOGGER.info(
                    "\nDomain configuration capture\n"
                    "  Domain: %s\n"
                    "  Save folder: %s\n\n"
                    "Working files will be refreshed; earlier saved snapshots remain in history.\n",
                    self.vccConfig.domainName,
                    self.domain_path,
                )
                self._check_call_counters()
                self.getVCCConfiguration()
                self.domain_objects = {}

                for method in self.client.service._operations.keys():
                    if method in methods:
                        label = re.sub(
                            r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])",
                            " ",
                            method[3:] if method.startswith("get") else method,
                        )
                        LOGGER.info("\nCapturing %s\n", label)
                        target_path_for_method = os.path.join(self.domain_path, method)
                        # create directory for the target path
                        os.makedirs(
                            os.path.dirname(target_path_for_method), exist_ok=True
                        )

                        try:
                            if method in METHOD_DEFAULT_ARGS.keys():
                                method_response = self._call_service(
                                    method, METHOD_DEFAULT_ARGS[method]
                                )
                            else:
                                method_response = self._call_service(method)

                            if method == "getIVRScripts":
                                self.get_config_object_detail(
                                    method, "ivrs", method_response
                                )

                            elif method == "getCampaigns":
                                self.domain_objects[
                                    method
                                ] = zeep.helpers.serialize_object(method_response, dict)
                                self.write_object_to_target_path(
                                    target_path_for_method, self.domain_objects[method]
                                )
                                method_response = self._call_service(
                                    method, campaignType="OUTBOUND"
                                )
                                self.get_config_object_detail(
                                    method,
                                    "campaigns_outbound",
                                    method_response,
                                    "getOutboundCampaign",
                                )
                                method_response = self._call_service(
                                    method, campaignType="INBOUND"
                                )
                                self.get_config_object_detail(
                                    method,
                                    "campaigns_inbound",
                                    method_response,
                                    "getInboundCampaign",
                                )

                            elif method == "getCampaignProfiles":
                                self.domain_objects[
                                    method
                                ] = zeep.helpers.serialize_object(method_response, dict)
                                self.write_object_to_target_path(
                                    target_path_for_method, self.domain_objects[method]
                                )
                                self.get_config_object_detail(
                                    method,
                                    "campaign_profile_filters",
                                    method_response,
                                    "getCampaignProfileFilter",
                                )
                                # self.get_config_object_detail(method, 'campaign_profile_dispositions', method_response, 'getCampaignProfileDispositions')
                                self.demystify_campaign_profile_filters()

                            elif method == "getSkills":
                                self.domain_objects[
                                    method
                                ] = zeep.helpers.serialize_object(method_response, dict)
                                self.write_object_to_target_path(
                                    target_path_for_method, self.domain_objects[method]
                                )
                                self.get_config_object_detail(
                                    method,
                                    "skills_info",
                                    method_response,
                                    "getSkillsInfo",
                                )

                            else:
                                self.domain_objects[
                                    method
                                ] = zeep.helpers.serialize_object(method_response, dict)
                                self.write_object_to_target_path(
                                    target_path_for_method, self.domain_objects[method]
                                )

                        except zeep.exceptions.Fault as error:
                            raise DomainCaptureError(
                                f"Failed to retrieve {method}"
                            ) from error

                os.remove(os.path.join(self.domain_path, INCOMPLETE_MARKER))
                LOGGER.info("\nSaving snapshot...\n")
                self.repo.git.add(A=True)
                self.repo.index.commit(
                    f"Domain Object Sync {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )

            except Exception as error:
                if self.domain_path and os.path.isdir(self.domain_path):
                    self._mark_capture_incomplete()
                raise DomainCaptureError(
                    f"Capture incomplete.\n"
                    f"  Snapshot folder: {self.domain_path}\n"
                    f"  Last API method: {self._last_api_method}\n\n"
                    "No new snapshot was saved. Earlier saved snapshots remain in history.\n"
                    "The working files may be partial; do not use them as a complete backup."
                ) from error
        else:
            raise DomainCaptureError("No active client available for capture")

    def sync_contactFields(self):
        pass

    def sync_campaignProfiles(self):
        for profile in self.domain_objects["getCampaignProfiles"]:
            description = profile["description"] or ""
            if description.find("--sync") > -1:
                try:
                    self.sync_target_domain.client.service.createCampaignProfile(
                        profile
                    )
                    print(f'\t\t\tSYNC (create): {profile["name"]}')
                except:
                    self.sync_target_domain.client.service.modifyCampaignProfile(
                        profile
                    )
                    print(f'\t\t\tSYNC (update): {profile["name"]}')

                    # Remove filters/grouping from the target domain before adding in conditions and grouping from this domain
                    self.sync_target_domain.client.service.modifyCampaignProfileCrmCriteria(
                        profileName=profile["name"],
                        grouping={"expression": None, "type": "All"},
                        removeCriteria=self.sync_target_domain.domain_objects[
                            "getCampaignProfiles_campaign_profile_filters"
                        ][profile["name"]]["crmCriteria"],
                    )
                    if (
                        len(
                            self.sync_target_domain.domain_objects[
                                "getCampaignProfiles_campaign_profile_filters"
                            ][profile["name"]]["orderByFields"]
                        )
                        > 0
                    ):
                        remove_fields = self.sync_target_domain.domain_objects[
                            "getCampaignProfiles_campaign_profile_filters"
                        ][profile["name"]]["orderByFields"]

                        self.sync_target_domain.client.service.modifyCampaignProfileFilterOrder(
                            campaignProfile=profile["name"],
                            removeOrderByField=[
                                field["fieldName"] for field in remove_fields
                            ],
                        )

                self.sync_target_domain.client.service.modifyCampaignProfileCrmCriteria(
                    profileName=profile["name"],
                    grouping=self.domain_objects[
                        "getCampaignProfiles_campaign_profile_filters"
                    ][profile["name"]]["grouping"],
                    addCriteria=self.domain_objects[
                        "getCampaignProfiles_campaign_profile_filters"
                    ][profile["name"]]["crmCriteria"],
                )
                if (
                    len(
                        self.domain_objects[
                            "getCampaignProfiles_campaign_profile_filters"
                        ][profile["name"]]["orderByFields"]
                    )
                    > 0
                ):
                    self.sync_target_domain.client.service.modifyCampaignProfileFilterOrder(
                        campaignProfile=profile["name"],
                        addOrderByField=self.domain_objects[
                            "getCampaignProfiles_campaign_profile_filters"
                        ][profile["name"]]["orderByFields"],
                    )

    def sync_ivrScripts(self):
        pass
        # for profile in self.domain_objects['getCampaignProfiles']:

    def demystify_campaign_profile_filters(self, reload_domain=False, verbose=False):
        if reload_domain == True:
            self.get_domain_objects(methods=["getCampaignProfiles"])
        profile_filters = self.domain_objects[
            "getCampaignProfiles_campaign_profile_filters"
        ]

        subfolder_path = os.path.join(
            self.domain_path, "campaign_profile_filters_demystified"
        )

        os.makedirs(subfolder_path, exist_ok=True)
        LOGGER.info("Writing readable campaign profile filters")
        for pf in profile_filters.keys():
            profile_filter = profile_filters[pf]
            if verbose == True:
                print(f"\n\n********** Demystifying {pf}")
            if (profile_filter["grouping"]["type"] == "Custom") and len(
                profile_filter["crmCriteria"]
            ) > 0:
                target_filename = os.path.join(subfolder_path, pf)
                demystified = demystify_filter(profile_filter, verbose=verbose)
                self.write_object_to_target_path(
                    target_path=target_filename, domain_object=demystified, toJson=False, filetype="sql"
                )
