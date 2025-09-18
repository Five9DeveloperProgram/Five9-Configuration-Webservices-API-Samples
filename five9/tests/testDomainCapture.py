# unittests for the domain_capture module

import unittest
import os
from five9.utils.domain_capture import Five9DomainConfig
from five9.five9_session import Five9Client

from private.credentials import ACCOUNTS


# run with coverage
# coverage run -m unittest discover -s tests -p "test*.py" -v
# coverage html

# instructions for how to run coverage for just this test
# coverage run -m unittest tests.testDomainCapture


INTEGRATION = os.getenv("F9_INTEGRATION", "0") == "1"
TEST_ENV_USERNAME = os.getenv("F9_TEST_USERNAME")
TEST_ENV_PASSWORD = os.getenv("F9_TEST_PASSWORD")

@unittest.skipUnless(INTEGRATION, "Integration tests require F9_INTEGRATION=1")
class TestDomainCapture(unittest.TestCase):
    username = None
    password = None
    account = None
    skip_reason = None

    @classmethod
    def setUpClass(cls):
        if "default_test_account" in ACCOUNTS:
            creds = ACCOUNTS.get("default_test_account", {})
            cls.username = creds.get("username")
            cls.password = creds.get("password")
            cls.account = "default_test_account"
        elif TEST_ENV_USERNAME and TEST_ENV_PASSWORD:
            cls.username = TEST_ENV_USERNAME
            cls.password = TEST_ENV_PASSWORD
            cls.account = None
        else:
            cls.skip_reason = "No integration test credentials found (add default_test_account or set F9_TEST_USERNAME/F9_TEST_PASSWORD)."

    def input(self, prompt):
        if prompt == "Enter Username: ":
            return self.username
        if prompt == "Enter Password: ":
            return self.password

    # initialize test variables from credentials.ACCOUNTS
    def setUp(self):
        if self.skip_reason:
            self.skipTest(self.skip_reason)
        # initialize client using account alias if available else direct creds
        if self.account:
            self.client = Five9Client(account=self.account)
        else:
            self.client = Five9Client(five9username=self.username, five9password=self.password)

    def initialize_domain_configuration(self, get_objects=False):
        # if no self.domain_configuration object exists, create one
        if not hasattr(self, "domain_configuration"):
            self.domain_configuration = Five9DomainConfig(
                client=self.client,
                # methods=["getCampaignProfiles"]
            )
            get_objects = True

        if get_objects:
            self.domain_configuration.get_domain_objects()

    def test_domain_config_capture(self):
        self.domain_configuration = Five9DomainConfig(
            client=self.client,
            # methods=["getCampaignProfiles"]
        )

        # self.assertEqual(self.domain_configuration.client, self.client)

        # assert that a folder was created matching the domain name in the
        # domain_config/domain_snapshots folder
        self.assertTrue(os.path.exists(self.domain_configuration.domain_path))

        # assert that there is a git repo in the domain_config/domain_snapshots folder
        self.assertTrue(
            os.path.exists(os.path.join(self.domain_configuration.domain_path, ".git"))
        )

    def test_domain_config_capture_campaign_profiles(self):
        # assert that a a demystified campaign profile was created for each
        # campaign in the domain with type "OUTBOUND" that also has a campaignProfile
        # with one or more crmCriteria
        self.initialize_domain_configuration()

        for campaign in self.domain_configuration.domain_objects["getCampaigns"]:
            if (
                campaign["type"] == "OUTBOUND"
                and campaign["mode"] == "ADVANCED"
                and campaign["profileName"]
                and self.domain_configuration.domain_objects[
                    "getCampaignProfiles_campaign_profile_filters"
                ][campaign["profileName"]]["grouping"]["type"]
                == "Custom"
                and len(
                    self.domain_configuration.domain_objects[
                        "getCampaignProfiles_campaign_profile_filters"
                    ][campaign["profileName"]]["crmCriteria"]
                )
                > 0
            ):
                # build path variable for the demystified campaign profile
                # and assert that it exists
                demystified_campaign_profile_path = os.path.join(
                    "domain_snapshots",
                    f"{self.domain_configuration.domain_path}",
                    "campaign_profile_filters_demystified",
                    campaign["profileName"] + ".sql",
                )
                print(demystified_campaign_profile_path)
                self.assertTrue(os.path.exists(demystified_campaign_profile_path))
