import base64
import unittest
from unittest.mock import patch
import requests
import zeep
from five9 import five9_session


class MockService:
    def __init__(self, call_counters=None, vcc_config=None, operations=None):
        self._call_counters = call_counters or []
        self._vcc_config = vcc_config or {"domainName": "TestDomain", "domainId": "12345"}
        self._operations = operations or {"getUsers": None, "getSkills": None}

    def getCallCountersState(self):
        return self._call_counters

    def getVCCConfiguration(self):
        return self._vcc_config

    def closeSession(self):
        return True


class Five9SessionUnitTests(unittest.TestCase):
    def _base_call_counters(self):
        return [
            {"timeout": 60, "callCounterStates": [
                {"operationType": "GetUsers", "value": 10, "limit": 100},
                {"operationType": "GetSkills", "value": 5, "limit": 50},
            ]},
            {"timeout": 1, "callCounterStates": [
                {"operationType": "GetUsers", "value": 1, "limit": 10},
            ]},
        ]

    def _mock_context(self):
        mock_service = MockService(call_counters=self._base_call_counters())
        init_patch = patch('zeep.Client.__init__', return_value=None)
        service_patch = patch.object(zeep.Client, 'service', new=property(lambda self: mock_service))
        return mock_service, init_patch, service_patch

    @patch('time.sleep', return_value=None)
    def test_throttled_service_proxy_calls_sleep(self, mock_sleep):
        class Dummy:
            def ping(self, x): return x + 1
        proxy = five9_session.ThrottledServiceProxy(Dummy(), delay_seconds=0.05)
        self.assertEqual(proxy.ping(4), 5)
        mock_sleep.assert_called_once_with(0.05)

    @patch('time.sleep', return_value=None)
    def test_client_init_with_username_prompts_for_password(self, _):
        mock_service, p_init, p_service = self._mock_context()
        with p_init, p_service, patch('five9.five9_session.getpass', return_value='pw123'):
            client = five9_session.Five9Client(five9username='user1', five9password=None)
            self.assertEqual(client.transport_session.auth.username, 'user1')
            self.assertEqual(client.transport_session.auth.password, 'pw123')
            self.assertIs(client.service, mock_service)

    @patch('time.sleep', return_value=None)
    def test_client_init_with_interactive_account_lookup(self, _):
        mock_service, p_init, p_service = self._mock_context()
        five9_session.ACCOUNTS['default_account'] = {'username': 'apiUserUsername'}
        with p_init, p_service, patch('builtins.input', return_value='userX'), patch('five9.five9_session.getpass', return_value='pwX'):
            client = five9_session.Five9Client(account='default_account')
            self.assertEqual(client.transport_session.auth.username, 'userX')
            self.assertEqual(client.transport_session.auth.password, 'pwX')
            self.assertIs(client.service, mock_service)

    @patch('time.sleep', return_value=None)
    def test_client_init_with_hostname_alias(self, _):
        mock_service, p_init, p_service = self._mock_context()
        with p_init, p_service:
            client = five9_session.Five9Client(five9username='u', five9password='p', api_hostname_alias='us')
            self.assertIn('api.five9.com', client.api_definition)
            self.assertIs(client.service, mock_service)

    @patch('time.sleep', return_value=None)
    def test_error_wrapped_as_creation_error(self, _):
        def fake_raise(self, wsdl, transport=None, plugins=None):
            raise requests.exceptions.ConnectionError('boom')
        with patch('zeep.Client.__init__', new=fake_raise):
            with self.assertRaises(five9_session.Five9ClientCreationError):
                five9_session.Five9Client(five9username='u', five9password='p')

    @patch('time.sleep', return_value=None)
    def test_latest_envelopes_and_history_reset(self, _):
        mock_service, p_init, p_service = self._mock_context()
        from lxml import etree
        with p_init, p_service:
            client = five9_session.Five9Client(five9username='u', five9password='p')
            sent_env = etree.Element('EnvelopeSent')
            recv_env = etree.Element('EnvelopeRecv')
            class DummyHistory: ...
            h = DummyHistory()
            h.last_sent = {'envelope': sent_env, 'http_headers': {'X-Test': '1'}}
            h.last_received = {'envelope': recv_env}
            client.history = h
            self.assertIn('EnvelopeSent', client.latest_envelopes)
            self.assertIn('EnvelopeRecv', client.latest_envelopes)
            client.history = 'broken'
            v = client.latest_envelopes
            self.assertIn('History object not found', v)
            self.assertEqual(client.latest_envelope_sent, '')
            self.assertEqual(client.latest_envelope_received, '')

    @patch('time.sleep', return_value=None)
    def test_latest_request_headers_and_auth_format(self, _):
        mock_service, p_init, p_service = self._mock_context()
        with p_init, p_service:
            client = five9_session.Five9Client(five9username='alpha', five9password='beta')
            class DummyHistory: ...
            h = DummyHistory()
            h.last_sent = {'http_headers': {'User-Agent': 'UnitTest'}}
            client.history = h
            hdrs = client.latest_request_headers
            auth_str = base64.b64encode(b'alpha:beta').decode()
            self.assertIn(f'Authorization: {auth_str}', hdrs)
            self.assertIn('User-Agent: UnitTest', hdrs)
            client.history.last_sent = None
            self.assertEqual(client.latest_request_headers, 'No request found in history')

    @patch('time.sleep', return_value=None)
    def test_current_api_usage_formatted(self, _):
        mock_service, p_init, p_service = self._mock_context()
        with p_init, p_service:
            client = five9_session.Five9Client(five9username='u', five9password='p')
            formatted = client.current_api_useage_formatted
            self.assertIn('GetUsers:', formatted)
            self.assertIn('GetSkills:', formatted)

    @patch('time.sleep', return_value=None)
    def test_print_available_service_methods(self, _):
        mock_service, p_init, p_service = self._mock_context()
        with p_init, p_service, patch('sys.stdout.write') as mock_write:
            client = five9_session.Five9Client(five9username='u', five9password='p')
            client.print_available_service_methods()
            out = ''.join(c[0][0] for c in mock_write.call_args_list)
            self.assertIn('getUsers', out)
            self.assertIn('getSkills', out)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
