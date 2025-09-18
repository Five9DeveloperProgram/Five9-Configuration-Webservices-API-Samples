# unit test for the five9_session library
from io import StringIO
import unittest
from unittest.mock import patch
import os

INTEGRATION = os.getenv("F9_INTEGRATION", "0") == "1"

TEST_ENV_USERNAME = os.getenv("F9_TEST_USERNAME")
TEST_ENV_PASSWORD = os.getenv("F9_TEST_PASSWORD")

from five9 import five9_session
from private.credentials import ACCOUNTS

# run with coverage
# coverage run -m unittest discover -s tests -p "test*.py" -v
# coverage html


@unittest.skipUnless(INTEGRATION, "Integration tests require F9_INTEGRATION=1")
class TestFive9Session(unittest.TestCase):
    username = None
    password = None
    account = None
    skip_reason = None

    @classmethod
    def setUpClass(cls):
        # Determine credentials preference: ACCOUNTS alias, then env vars
        if "default_test_account" in ACCOUNTS:
            creds = ACCOUNTS.get("default_test_account", {})
            cls.username = creds.get("username")
            cls.password = creds.get("password")
            cls.account = "default_test_account"
        elif TEST_ENV_USERNAME and TEST_ENV_PASSWORD:
            cls.username = TEST_ENV_USERNAME
            cls.password = TEST_ENV_PASSWORD
            cls.account = None  # direct creds
        else:
            cls.skip_reason = "No integration test credentials found (add default_test_account or set F9_TEST_USERNAME/F9_TEST_PASSWORD)."

    def setUp(self):
        if self.skip_reason:
            self.skipTest(self.skip_reason)

    def test_session_create_with_default_credential(self):
        test_client = five9_session.Five9Client(account=self.account) if self.account else five9_session.Five9Client(five9username=self.username, five9password=self.password)
        self.assertIsNotNone(test_client)

    def test_session_create_with_username_and_password(self):
        test_client = five9_session.Five9Client(five9username=self.username, five9password=self.password)
        self.assertIsNotNone(test_client)
        test_client.service.closeSession()

    def test_session_create_with_invalid_credentials(self):
        with self.assertRaises(five9_session.Five9ClientCreationError):
            test_client = five9_session.Five9Client(
                five9username="badusername", five9password="badpassword"
            )
            test_client.service.closeSession()

    def test_session_create_with_invalid_api_hostname(self):
        with self.assertRaises(five9_session.Five9ClientCreationError):
            test_client = five9_session.Five9Client(
                account=self.account, api_hostname="api.f9.co"
            )
            test_client.service.closeSession()

    def test_session_create_with_invalid_api_version(self):
        test_client = five9_session.Five9Client(account=self.account, api_version="v99")
        # API BUG FOUND - the API returns a valid client object even if the API version is invalid
        self.assertIsNotNone(test_client)
        self.assertGreater(len(test_client.call_counters), 0)
        test_client.service.closeSession()

    def test_client_envelopes(self):
        test_client = five9_session.Five9Client(account=self.account)
        self.assertIsNot(test_client.latest_envelopes, "")
        self.assertIsNot(test_client.latest_envelope_sent, "")
        self.assertIsNot(test_client.latest_envelope_received, "")
        self.assertIsNot(test_client.latest_request_headers, "")

        self.assertTrue(
            test_client.latest_envelopes.startswith(
                '<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">'
            )
        )
        self.assertTrue(
            test_client.latest_envelope_sent.startswith(
                '<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">'
            )
        )

        self.assertTrue(
            test_client.latest_envelope_received.startswith(
                '<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">'
            )
        )

        test_client.history = "accidentally modified"
        latest_envelopes = test_client.latest_envelopes
        latest_envelope_sent = test_client.latest_envelope_sent
        latest_envelope_received = test_client.latest_envelope_received

        # Assert that the latest envelope is a string
        self.assertIsInstance(latest_envelopes, str)
        self.assertIsInstance(latest_envelope_sent, str)
        self.assertIsInstance(latest_envelope_received, str)

        # Assert that the latest envelope is not empty
        self.assertNotEqual(latest_envelopes, "")
        self.assertEqual(latest_envelope_sent, "")
        self.assertEqual(latest_envelope_received, "")

        # Assert that the latest envelope does not start with a specific string
        self.assertFalse(
            latest_envelopes.startswith(
                '<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">'
            )
        )

    @patch("sys.stdout", new_callable=StringIO)
    def test_client_show_available_service_methods(self, mock_stdout):
        test_client = five9_session.Five9Client(account=self.account)
        test_client.print_available_service_methods()

        # test that the client.available_methods prints a list of available methods
        self.assertIsNot(mock_stdout.getvalue(), "")
        test_client.service.closeSession()
