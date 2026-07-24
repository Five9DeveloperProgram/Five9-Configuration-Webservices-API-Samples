import datetime
import json
import os
import shutil
import time

from git import Repo
import zeep

from five9 import five9_session
from .campaign_profile_comprehension import demystify_filter
from . import ivr_diagram

API_SLEEP_INTERVAL = 0.3

REPO_PATH = "domain_snapshots"

METHOD_DEFAULT_ARGS = {
    "getAgentGroups": ".*",
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


class Five9DomainConfig:
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
    ):
        self.client = client
        self.sync_target_domain = sync_target_domain
        self.methods = methods
        self.generate_ivr_diagrams = generate_ivr_diagrams

        self.domain_objects = {}

        self.domain_path = None

        self.vccConfig = None
        self.repo = None

        print("api_hostname_alias", api_hostname_alias)

        if client is None:
            print(
                f"\nNo client provided, creating a new client for {username}{account}"
            )
            self.client = five9_session.Five9Client(
                five9username=username, five9password=password, account=account, api_hostname_alias=api_hostname_alias
            )
        else:
            self.client = client

        if self.client is not None:
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

    def getVCCConfiguration(self):
        """Method to get the VCC Configuration for the domain and create the domain snapshot folder"""

        self.vccConfig = self.client.service.getVCCConfiguration()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Use current working directory instead of hardcoded path
        current_working_directory = os.getcwd()

        self.domain_path = os.path.join(
            current_working_directory,  # Change from os.path.dirname(__file__)
            "domain_snapshots",
            f"{self.vccConfig.domainName}",
            "ivr-documentation",
            timestamp,
        )

        # delete the contents of the domain snapshot folder if it exists, except for the .git folder
        if os.path.exists(self.domain_path):
            print(
                f"\nDeleting existing snapshot data for {self.vccConfig.domainName}:\n{self.domain_path}\n"
            )

            # for each file in the root directory, delete it unless the parent directory is .git
            for name in os.listdir(self.domain_path):
                if name != ".gitignore" and name != ".git":
                    # if the file is a directory, delete the directory
                    if os.path.isdir(os.path.join(self.domain_path, name)):
                        shutil.rmtree(os.path.join(self.domain_path, name))
                    else:
                        # remove the file
                        os.remove(os.path.join(self.domain_path, name))

        else:
            os.makedirs(self.domain_path, exist_ok=True)

        try:
            self.repo = Repo(self.domain_path)
            print(f"Found existing repo at {self.domain_path}")
        except Exception as e:
            print(f"Error: {e}")
            self.repo = Repo.init(self.domain_path)
            # set the "longpaths=true" option for the repo (required for Windows
            # to support long names of objects and the filenames created)
            self.repo.git.config("core.longpaths", "true")
            self.repo.git.add(A=True)
            self.repo.index.commit("Initial Commit")
            print(f"Created new repo at {self.domain_path}")

        print(f"\nDomain snapshot initialized for:\n{self.vccConfig.domainName}\n")


        # TODO - Add logic to check if repo exists and if so, pull latest, else create new repo

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
            try:
                clean_object = fix_datetimes(domain_object)  # <= Only modifies datetime fields
                output_string = json.dumps(
                    clean_object,
                    sort_keys=sort_keys,
                    indent=indent
                )
            except TypeError as e:
                print(f"Error: {e}")
                print(f"Domain Object: {domain_object}")
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
        print(f"\n\t{parent_method_name} - {subfolder_name}")
        self.domain_objects[f"{parent_method_name}_{subfolder_name}"] = {}

        for domain_object in method_response:
            object_name = domain_object.name
            print(f"\t\t{object_name}")
            if vcc_method is not None:
                sub_method = getattr(self.client.service, vcc_method)
                domain_object = sub_method(object_name)
                time.sleep(0.2)
                # print(domain_object)
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
                self.write_ivr_documentation(target_path, object_name, captured_object)

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
            print(f"\t\t\tdiagram + docs: {ivr_name}")
        except Exception as e:
            print(f"\t\t\tskipped diagram for {ivr_name}: {e}")

    def get_domain_objects(self, methods=None):
        if methods is None:
            methods = self.methods
        if self.client is not None:
            try:
                self.getVCCConfiguration()

                print("Processing Domain Object Methods")
                for method in self.client.service._operations.keys():
                    if method in methods:
                        print(f"\t{method}")
                        vcc_method = getattr(self.client.service, method)
                        target_path_for_method = os.path.join(self.domain_path, method)
                        # create directory for the target path
                        os.makedirs(
                            os.path.dirname(target_path_for_method), exist_ok=True
                        )

                        try:
                            if method in METHOD_DEFAULT_ARGS.keys():
                                method_response = vcc_method(
                                    METHOD_DEFAULT_ARGS[method]
                                )
                            else:
                                method_response = vcc_method()

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
                                method_response = vcc_method(campaignType="OUTBOUND")
                                self.get_config_object_detail(
                                    method,
                                    "campaigns_outbound",
                                    method_response,
                                    "getOutboundCampaign",
                                )
                                method_response = vcc_method(campaignType="INBOUND")
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

                        except zeep.exceptions.Fault as e:
                            print("Error: ")
                            print(e)

                # add changes to the git repo and commit
                # print the repo status and path
                print(f"Git Status: {self.repo.git.status()}")
                self.repo.git.add(A=True)
                self.repo.index.commit(
                    f"Domain Object Sync {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )

            except zeep.exceptions.Fault as e:
                print(e)
        else:
            print("No active client object available to connect with Five9 VCC")

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
        print(
            f"\n\n********** Demystifying campaign profile filters to\n{subfolder_path}"
        )
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
