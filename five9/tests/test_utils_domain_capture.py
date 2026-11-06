import io
import logging
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from git import Repo
from zeep import xsd
from zeep.exceptions import Fault

from five9.utils import domain_capture
from examples.domain_config import domain_config_capture


def _fake_client(domain_name):
    client = mock.Mock()
    client.service.getVCCConfiguration.return_value = SimpleNamespace(
        domainName=domain_name
    )
    client.throttled_service = domain_capture.five9_session.ThrottledServiceProxy(
        client.service
    )
    client.service.getCallCountersState.return_value = []
    return client


class TestSnapshotRepoPersistence(unittest.TestCase):
    """The snapshot git repo must survive repeated captures of the same domain."""

    def setUp(self):
        self.sleep = mock.patch.object(domain_capture.time, "sleep").start()
        self.addCleanup(mock.patch.stopall)
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def _use_fake_clock(self, cfg):
        clock = SimpleNamespace(now=0.0)
        self.sleep.side_effect = lambda seconds: setattr(
            clock, "now", clock.now + seconds
        )
        patcher = mock.patch.object(
            domain_capture.time, "monotonic", side_effect=lambda: clock.now
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        cfg._last_request_started = None
        return clock

    def _capture(self, domain="Test Domain", files=None):
        cfg = domain_capture.Five9DomainConfig(client=_fake_client(domain), methods=[])
        for name, text in (files or {}).items():
            with open(os.path.join(cfg.domain_path, name), "w") as f:
                f.write(text)
        os.remove(os.path.join(cfg.domain_path, domain_capture.INCOMPLETE_MARKER))
        cfg.repo.git.add(A=True)
        cfg.repo.index.commit("capture")
        return cfg

    def test_path_is_stable_between_runs(self):
        first = self._capture()
        second = self._capture()
        self.assertEqual(first.domain_path, second.domain_path)

    def test_history_accumulates_and_git_dir_is_kept(self):
        self._capture(files={"a.json": "1"})
        cfg = self._capture(files={"a.json": "2"})
        # Initial Commit + 2 captures
        self.assertEqual(len(list(Repo(cfg.domain_path).iter_commits())), 3)

    def test_stale_files_removed_and_show_as_deletions(self):
        self._capture(files={"old.json": "x"})
        cfg = self._capture(files={"new.json": "y"})
        self.assertFalse(os.path.exists(os.path.join(cfg.domain_path, "old.json")))
        changed = Repo(cfg.domain_path).git.diff("HEAD~1", "HEAD", name_status=True)
        self.assertIn("D\told.json", changed)

    def test_capture_calls_use_proxy_and_configured_delay(self):
        client = _fake_client("Test Domain")
        client.service._operations = {"getAgentGroups": None, "getSkills": None}
        client.service.getAgentGroups.return_value = []
        skill_type = xsd.ComplexType(xsd.Sequence([xsd.Element("name", xsd.String())]))
        client.service.getSkills.return_value = [skill_type(name="Support")]
        client.service.getSkillsInfo.return_value = {"name": "Support"}
        cfg = domain_capture.Five9DomainConfig(
            client=client, methods=["getAgentGroups", "getSkills"], call_delay=1.0
        )
        self.sleep.reset_mock()

        cfg.get_domain_objects()

        client.service.getAgentGroups.assert_called_once_with(".*")
        client.service.getSkillsInfo.assert_called_once_with("Support")
        self.assertEqual(
            self.sleep.call_args_list, [mock.call(0.7), mock.call(0.3)] * 5
        )
        self.assertFalse(
            os.path.exists(
                os.path.join(cfg.domain_path, domain_capture.INCOMPLETE_MARKER)
            )
        )

    def test_invalid_delay_rejected_before_client_creation(self):
        for delay in (0.2, -1, float("nan"), float("inf")):
            with self.subTest(delay=delay), mock.patch.object(
                domain_capture.five9_session, "Five9Client"
            ) as create_client:
                with self.assertRaises(ValueError):
                    domain_capture.Five9DomainConfig(call_delay=delay)
                create_client.assert_not_called()

    def test_query_limit_retries_same_read_with_increasing_wait(self):
        client = _fake_client("Test Domain")
        cfg = domain_capture.Five9DomainConfig(client=client, methods=[])
        fault = Fault("60 seconds limit (180) for query operation is reached.")
        client.service.getSkillsInfo.side_effect = [fault, fault, {"name": "Support"}]
        self.sleep.reset_mock()
        with mock.patch.object(domain_capture.random, "uniform", return_value=2):
            result = cfg._call_service("getSkillsInfo", "Support")
        self.assertEqual(result, {"name": "Support"})
        self.assertEqual(
            client.service.getSkillsInfo.call_args_list, [mock.call("Support")] * 3
        )
        self.sleep.assert_any_call(62)
        self.sleep.assert_any_call(122)
        self.assertEqual(cfg.call_delay, 1.0)

    def test_query_limit_retry_count_is_bounded(self):
        client = _fake_client("Test Domain")
        cfg = domain_capture.Five9DomainConfig(
            client=client, methods=[], rate_limit_retries=2
        )
        client.service.getSkills.side_effect = Fault(
            "120 seconds limit (360) for query operation is reached."
        )
        self.sleep.reset_mock()
        with mock.patch.object(domain_capture.random, "uniform", return_value=0):
            with self.assertRaises(Fault):
                cfg._call_service("getSkills")
        self.assertEqual(client.service.getSkills.call_count, 3)
        self.sleep.assert_any_call(120)
        self.sleep.assert_any_call(240)

    def test_other_faults_are_not_retried(self):
        client = _fake_client("Test Domain")
        cfg = domain_capture.Five9DomainConfig(client=client, methods=[])
        client.service.getSkills.side_effect = Fault("Permission denied")
        with self.assertRaises(Fault):
            cfg._call_service("getSkills")
        client.service.getSkills.assert_called_once_with()

    def test_periodic_counter_check_uses_proxy_and_slows_capture(self):
        client = _fake_client("Test Domain")
        cfg = domain_capture.Five9DomainConfig(
            client=client, methods=[], counter_check_interval=2
        )
        client.service.getCallCountersState.return_value = [
            {
                "timeout": 60,
                "callCounterStates": [
                    {"operationType": "QUERY", "value": 144, "limit": 180}
                ],
            }
        ]
        cfg._call_service("getSkills")
        self.sleep.reset_mock()
        cfg._call_service("getSkills")
        client.service.getCallCountersState.assert_called_once_with()
        self.assertEqual(cfg.call_delay, 1.0)
        self.assertEqual(
            self.sleep.call_args_list,
            [mock.call(0.2), mock.call(0.3), mock.call(0.7), mock.call(0.3)],
        )

    def test_counter_readout_only_logs_nonzero_usage(self):
        client = _fake_client("Test Domain")
        cfg = domain_capture.Five9DomainConfig(client=client, methods=[])
        client.service.getCallCountersState.return_value = [
            {
                "timeout": 60,
                "callCounterStates": [
                    {"operationType": "QUERY", "value": 1, "limit": 180},
                    {"operationType": "UPDATE", "value": 0, "limit": 60},
                ],
            }
        ]
        with self.assertLogs(domain_capture.LOGGER, level="INFO") as logs:
            cfg._check_call_counters()
        self.assertEqual(len(logs.records), 1)
        summary = logs.records[0].getMessage()
        self.assertIn("Your API usage / Domain limit", summary)
        self.assertIn("1 minute window", summary)
        self.assertRegex(summary, r"Query\s+1 / 180\s+0\.6%")
        self.assertNotIn("Update", summary)
        client.service.getCallCountersState.return_value[0]["callCounterStates"][0][
            "value"
        ] = 0
        with mock.patch.object(domain_capture.LOGGER, "info") as log_info:
            cfg._check_call_counters()
        log_info.assert_not_called()
        self.assertEqual(cfg.call_delay, 0.5)

    def test_counter_summary_orders_windows_and_limits_and_warns_once(self):
        client = _fake_client("Test Domain")
        cfg = domain_capture.Five9DomainConfig(client=client, methods=[])
        client.service.getCallCountersState.return_value = [
            {
                "timeout": 60,
                "callCounterStates": [
                    {"operationType": "UPDATE", "value": 48, "limit": 60},
                    {"operationType": "QUERY", "value": 144, "limit": 180},
                ],
            },
            {
                "timeout": 86400,
                "callCounterStates": [
                    {"operationType": "QUERY", "value": 1200, "limit": 10000},
                ],
            },
            {
                "timeout": 3600,
                "callCounterStates": [
                    {"operationType": "QUERY", "value": 12, "limit": 1000},
                    {"operationType": "UNKNOWN", "value": 1, "limit": 0},
                ],
            },
        ]
        with self.assertLogs(domain_capture.LOGGER, level="INFO") as logs:
            cfg._check_call_counters()
        self.assertEqual(len(logs.records), 2)
        summary = logs.records[0].getMessage()
        self.assertLess(summary.index("1 day window"), summary.index("1 hour window"))
        self.assertLess(
            summary.index("1 hour window"), summary.index("1 minute window")
        )
        minute_section = summary.split("1 minute window")[1]
        self.assertLess(minute_section.index("Query"), minute_section.index("Update"))
        self.assertIn("1,200 / 10,000", summary)
        self.assertIn("n/a", summary)
        self.assertEqual(summary.count("HIGH"), 2)
        self.assertEqual(logs.records[1].levelname, "WARNING")
        self.assertEqual(cfg.call_delay, 1.0)

    def test_dynamic_pacing_uses_domain_limits_without_changing_client_proxy(self):
        client = _fake_client("Test Domain")
        original_proxy = client.throttled_service
        cfg = domain_capture.Five9DomainConfig(
            client=client, methods=[], dynamic_pacing=True
        )
        counters = [
            {
                "timeout": 60,
                "callCounterStates": [
                    {"operationType": "query", "value": 0, "limit": 600},
                    {"operationType": "UPDATE", "value": 60, "limit": 60},
                ],
            }
        ]
        cfg._update_dynamic_pacing(counters)
        self.assertAlmostEqual(cfg.call_delay, 60 / (0.95 * 600))
        self.assertIs(client.throttled_service, original_proxy)
        self.assertEqual(original_proxy._delay, 0.3)
        counters.append(
            {
                "timeout": 3600,
                "callCounterStates": [
                    {"operationType": "QUERY", "value": 0, "limit": 3600}
                ],
            }
        )
        cfg._update_dynamic_pacing(counters)
        self.assertAlmostEqual(cfg.call_delay, 3600 / (0.95 * 3600))

    def test_personal_budget_and_latency_are_included_in_request_spacing(self):
        cfg = domain_capture.Five9DomainConfig(
            client=_fake_client("Test Domain"),
            methods=[],
            dynamic_pacing=True,
            query_limit_per_minute=60,
        )
        cfg._update_dynamic_pacing(
            [
                {
                    "timeout": 60,
                    "callCounterStates": [
                        {"operationType": "QUERY", "value": 0, "limit": 600}
                    ],
                }
            ]
        )
        clock = SimpleNamespace(now=0.0)
        self.sleep.side_effect = lambda seconds: setattr(
            clock, "now", clock.now + seconds
        )
        cfg._last_request_started = None
        with mock.patch.object(
            domain_capture.time, "monotonic", side_effect=lambda: clock.now
        ):
            cfg.client.service.getSkills.side_effect = lambda: clock.now
            first = cfg._request("getSkills")
            clock.now += 0.4
            second = cfg._request("getSkills")
            self.assertAlmostEqual(second - first, 1.0)
            clock.now += 2.0
            third = cfg._request("getSkills")
            self.assertAlmostEqual(third - second, 2.0)

    def test_invalid_retry_and_monitor_settings_rejected(self):
        for kwargs in (
            {"rate_limit_retries": -1},
            {"rate_limit_retries": 11},
            {"counter_check_interval": 0},
            {"query_limit_per_minute": 0},
            {"query_limit_per_minute": -1},
            {"query_limit_per_minute": 1.5},
            {"query_limit_per_minute": True},
        ):
            with self.subTest(kwargs=kwargs), mock.patch.object(
                domain_capture.five9_session, "Five9Client"
            ) as create_client:
                with self.assertRaises(ValueError):
                    domain_capture.Five9DomainConfig(**kwargs)
                create_client.assert_not_called()

    def test_dynamic_reads_and_counter_checks_share_the_same_budget(self):
        client = _fake_client("Test Domain")
        cfg = domain_capture.Five9DomainConfig(
            client=client,
            methods=[],
            dynamic_pacing=True,
            query_limit_per_minute=1000,
            counter_check_interval=2,
        )
        counters = [
            {
                "timeout": 60,
                "callCounterStates": [
                    {"operationType": "QUERY", "value": 0, "limit": 600}
                ],
            }
        ]
        cfg._update_dynamic_pacing(counters)
        cfg._calls_since_counter_check = 0
        clock = self._use_fake_clock(cfg)
        starts = []
        client.service.getSkills.side_effect = lambda: starts.append(clock.now)
        client.service.getCallCountersState.side_effect = lambda: (
            starts.append(clock.now) or counters
        )
        for unused in range(3):
            cfg._call_service("getSkills")
        self.assertEqual(len(starts), 4)
        for previous, current in zip(starts, starts[1:]):
            self.assertAlmostEqual(current - previous, 60 / (0.95 * 600))
        self.assertLess(cfg.call_delay, 0.3)

    def test_dynamic_retry_backs_off_then_recovers_without_exceeding_budget(self):
        client = _fake_client("Test Domain")
        cfg = domain_capture.Five9DomainConfig(
            client=client, methods=[], dynamic_pacing=True, query_limit_per_minute=120
        )
        counters = [
            {
                "timeout": 60,
                "callCounterStates": [
                    {"operationType": "QUERY", "value": 0, "limit": 600}
                ],
            }
        ]
        cfg._update_dynamic_pacing(counters)
        clock = self._use_fake_clock(cfg)
        starts = []

        def attempt():
            starts.append(clock.now)
            if len(starts) == 1:
                raise Fault("60 seconds limit (600) for query operation is reached.")
            return []

        client.service.getSkills.side_effect = attempt
        with mock.patch.object(domain_capture.random, "uniform", return_value=0):
            cfg._request("getSkills")
        self.assertEqual(starts[1] - starts[0], 60)
        cfg._update_dynamic_pacing(counters)
        self.assertEqual(cfg.call_delay, 1.0)
        clock.now = cfg._recover_after
        cfg._update_dynamic_pacing(counters)
        self.assertEqual(cfg.call_delay, 0.8)
        for unused in range(10):
            cfg._update_dynamic_pacing(counters)
        self.assertEqual(cfg.call_delay, 0.5)

    def test_missing_query_limits_do_not_accelerate_capture(self):
        cfg = domain_capture.Five9DomainConfig(
            client=_fake_client("Test Domain"), methods=[], dynamic_pacing=True
        )
        cfg._update_dynamic_pacing([])
        self.assertEqual(cfg.call_delay, 0.5)
        cfg._update_dynamic_pacing(
            [
                {
                    "timeout": 3600,
                    "callCounterStates": [
                        {"operationType": "QUERY", "value": 0, "limit": 1000}
                    ],
                }
            ]
        )
        slower_delay = cfg.call_delay
        cfg._update_dynamic_pacing(
            [
                {
                    "timeout": 60,
                    "callCounterStates": [
                        {"operationType": "QUERY", "value": 0, "limit": 0}
                    ],
                }
            ]
        )
        self.assertEqual(cfg.call_delay, slower_delay)

    def test_query_pressure_not_write_pressure_slows_dynamic_capture(self):
        client = _fake_client("Test Domain")
        cfg = domain_capture.Five9DomainConfig(
            client=client, methods=[], dynamic_pacing=True
        )
        counters = [
            {
                "timeout": 60,
                "callCounterStates": [
                    {"operationType": "QUERY", "value": 570, "limit": 600},
                    {"operationType": "UPDATE", "value": 60, "limit": 60},
                ],
            }
        ]
        client.service.getCallCountersState.return_value = counters
        with mock.patch.object(domain_capture.LOGGER, "warning") as warning:
            cfg._check_call_counters()
        warning.assert_not_called()
        self.assertAlmostEqual(cfg.call_delay, 60 / (0.95 * 600))
        counters[0]["callCounterStates"][0]["value"] = 588
        with self.assertLogs(domain_capture.LOGGER, level="WARNING"):
            cfg._check_call_counters()
        self.assertAlmostEqual(cfg.call_delay, 2 * 60 / (0.95 * 600))

    def test_fixed_mode_keeps_proxy_pause_and_honors_personal_budget(self):
        cfg = domain_capture.Five9DomainConfig(
            client=_fake_client("Test Domain"), methods=[], query_limit_per_minute=30
        )
        self.assertFalse(cfg.dynamic_pacing)
        clock = self._use_fake_clock(cfg)
        cfg.client.service.getSkills.side_effect = lambda: clock.now
        first = cfg._request("getSkills")
        second = cfg._request("getSkills")
        self.assertAlmostEqual(second - first, 2.0)
        self.assertEqual(cfg.client.throttled_service._delay, 0.3)

    def test_failed_capture_leaves_marker_and_does_not_commit_or_continue(self):
        previous = self._capture(files={"previous.json": "{}"})
        previous_commit = previous.repo.head.commit.hexsha
        client = _fake_client("Test Domain")
        client.service._operations = {"getSkills": None, "getAgentGroups": None}
        client.service.getSkills.side_effect = Fault(
            "60 seconds limit (180) for query operation is reached."
        )
        cfg = domain_capture.Five9DomainConfig(
            client=client, methods=["getSkills", "getAgentGroups"], rate_limit_retries=0
        )
        with self.assertRaisesRegex(
            domain_capture.DomainCaptureError, "Capture incomplete"
        ):
            cfg.get_domain_objects()
        self.assertEqual(cfg.repo.head.commit.hexsha, previous_commit)
        self.assertEqual(cfg.repo.git.show("HEAD:previous.json"), "{}")
        self.assertTrue(
            os.path.exists(
                os.path.join(cfg.domain_path, domain_capture.INCOMPLETE_MARKER)
            )
        )
        client.service.getAgentGroups.assert_not_called()

    def test_detail_failure_also_prevents_commit(self):
        client = _fake_client("Test Domain")
        client.service._operations = {"getCampaigns": None}
        campaign_type = xsd.ComplexType(
            xsd.Sequence([xsd.Element("name", xsd.String())])
        )
        client.service.getCampaigns.return_value = [campaign_type(name="Outbound")]
        client.service.getOutboundCampaign.side_effect = Fault("Permission denied")
        cfg = domain_capture.Five9DomainConfig(client=client, methods=["getCampaigns"])
        previous_commit = cfg.repo.head.commit.hexsha
        with self.assertRaisesRegex(
            domain_capture.DomainCaptureError, "getOutboundCampaign"
        ):
            cfg.get_domain_objects()
        self.assertEqual(cfg.repo.head.commit.hexsha, previous_commit)
        client.service.getInboundCampaign.assert_not_called()

    def test_serialization_failure_prevents_commit(self):
        client = _fake_client("Test Domain")
        client.service._operations = {"getSkills": None}
        client.service.getSkills.return_value = [object()]
        cfg = domain_capture.Five9DomainConfig(client=client, methods=["getSkills"])
        previous_commit = cfg.repo.head.commit.hexsha
        with self.assertRaises(domain_capture.DomainCaptureError):
            cfg.get_domain_objects()
        self.assertEqual(cfg.repo.head.commit.hexsha, previous_commit)

    def test_cli_passes_settings_and_returns_nonzero_on_failure(self):
        arguments = [
            "domain_config_capture",
            "--account_alias",
            "offline",
            "--call-delay",
            "1",
            "--rate-limit-retries",
            "2",
            "--counter-check-interval",
            "10",
            "--dynamic-pacing",
            "--query-limit-per-minute",
            "120",
        ]
        with mock.patch("sys.argv", arguments), mock.patch.object(
            domain_capture, "Five9DomainConfig"
        ) as create_capture:
            create_capture.return_value.get_domain_objects.side_effect = (
                domain_capture.DomainCaptureError("Capture incomplete")
            )
            with self.assertLogs(level="ERROR"):
                self.assertEqual(domain_config_capture.main(), 1)
            self.assertEqual(create_capture.call_args.kwargs["call_delay"], 1.0)
            self.assertEqual(create_capture.call_args.kwargs["rate_limit_retries"], 2)
            self.assertEqual(
                create_capture.call_args.kwargs["counter_check_interval"], 10
            )
            self.assertTrue(create_capture.call_args.kwargs["dynamic_pacing"])
            self.assertEqual(
                create_capture.call_args.kwargs["query_limit_per_minute"], 120
            )

    def test_campaign_and_profile_reads_use_proxy(self):
        client = _fake_client("Test Domain")
        client.service._operations = {"getCampaigns": None, "getCampaignProfiles": None}
        named_type = xsd.ComplexType(xsd.Sequence([xsd.Element("name", xsd.String())]))
        client.service.getCampaigns.return_value = [named_type(name="Campaign")]
        client.service.getOutboundCampaign.return_value = {"name": "Campaign"}
        client.service.getInboundCampaign.return_value = {"name": "Campaign"}
        client.service.getCampaignProfiles.return_value = [named_type(name="Profile")]
        client.service.getCampaignProfileFilter.return_value = {
            "grouping": {"type": "Standard"},
            "crmCriteria": [],
        }
        client.throttled_service = mock.Mock(wraps=client.throttled_service)
        cfg = domain_capture.Five9DomainConfig(
            client=client, methods=["getCampaigns", "getCampaignProfiles"]
        )
        client.throttled_service.reset_mock()
        cfg.get_domain_objects()
        self.assertEqual(
            client.throttled_service.getCampaigns.call_args_list,
            [
                mock.call(),
                mock.call(campaignType="OUTBOUND"),
                mock.call(campaignType="INBOUND"),
            ],
        )
        client.throttled_service.getOutboundCampaign.assert_called_once_with("Campaign")
        client.throttled_service.getInboundCampaign.assert_called_once_with("Campaign")
        client.throttled_service.getCampaignProfileFilter.assert_called_once_with(
            "Profile"
        )
        client.throttled_service.getVCCConfiguration.assert_called_once_with()
        client.throttled_service.getCallCountersState.assert_called_once_with()

    def test_cli_success_returns_zero(self):
        with mock.patch("sys.argv", ["domain_config_capture"]), mock.patch.object(
            domain_capture, "Five9DomainConfig"
        ) as create_capture:
            self.assertEqual(domain_config_capture.main(), 0)
        create_capture.return_value.get_domain_objects.assert_called_once_with()
        self.assertFalse(create_capture.call_args.kwargs["dynamic_pacing"])
        self.assertIsNone(create_capture.call_args.kwargs["query_limit_per_minute"])

    def test_detail_progress_counts_objects_without_printing_names(self):
        cfg = domain_capture.Five9DomainConfig(
            client=_fake_client("Test Domain"), methods=[]
        )
        items = [
            SimpleNamespace(name="First campaign"),
            SimpleNamespace(name="Second campaign"),
        ]
        cfg.client.service.getOutboundCampaign.return_value = {"description": "Test"}
        output, progress_output = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", output), mock.patch(
            "sys.stderr", progress_output
        ):
            cfg.get_config_object_detail(
                "getCampaigns", "campaigns_outbound", items, "getOutboundCampaign"
            )
        self.assertIn("Outbound campaigns", progress_output.getvalue())
        self.assertIn("2/2", progress_output.getvalue())
        self.assertEqual(output.getvalue(), "")
        for item in items:
            self.assertNotIn(item.name, progress_output.getvalue())
            self.assertTrue(
                os.path.isfile(
                    os.path.join(
                        cfg.domain_path, "campaigns_outbound", item.name + ".json"
                    )
                )
            )

    def test_console_formatter_keeps_warnings_distinct_and_info_plain(self):
        formatter = domain_config_capture._CaptureConsoleFormatter()
        for level, expected in (
            (logging.INFO, "\nCapture phase\n"),
            (logging.WARNING, "WARNING: \nCapture phase\n"),
            (logging.ERROR, "ERROR: \nCapture phase\n"),
        ):
            with self.subTest(level=level):
                record = logging.LogRecord(
                    "capture", level, "", 0, "\nCapture %s\n", ("phase",), None
                )
                self.assertEqual(formatter.format(record), expected)

    def test_capture_phase_headings_are_readable_and_separated(self):
        client = _fake_client("Test Domain")
        client.service._operations = {"getAgentGroups": None, "getIVRScripts": None}
        client.service.getAgentGroups.return_value = []
        client.service.getIVRScripts.return_value = []
        cfg = domain_capture.Five9DomainConfig(
            client=client, methods=["getAgentGroups", "getIVRScripts"]
        )
        with self.assertLogs(domain_capture.LOGGER, level="INFO") as logs:
            cfg.get_domain_objects()
        messages = [record.getMessage() for record in logs.records]
        self.assertIn("\nCapturing Agent Groups\n", messages)
        self.assertIn("\nCapturing IVR Scripts\n", messages)
        self.assertIn("\nSaving snapshot...\n", messages)
        self.assertEqual(sum("Save folder:" in message for message in messages), 1)

    def test_detail_progress_closes_on_failure_and_preserves_warning(self):
        cfg = domain_capture.Five9DomainConfig(
            client=_fake_client("Test Domain"), methods=[], rate_limit_retries=0
        )

        def fail_detail(*args, **kwargs):
            domain_capture.LOGGER.warning("Test capture warning")
            raise Fault("Permission denied")

        cfg.client.service.getCampaignProfileFilter.side_effect = fail_detail
        progress_output = io.StringIO()
        with mock.patch("sys.stderr", progress_output):
            with self.assertRaises(Fault):
                cfg.get_config_object_detail(
                    "getCampaignProfiles",
                    "campaign_profile_filters",
                    [SimpleNamespace(name="Profile")],
                    "getCampaignProfileFilter",
                )
        self.assertIn("0/1", progress_output.getvalue())
        self.assertIn("Test capture warning", progress_output.getvalue())
        self.assertTrue(progress_output.getvalue().endswith("\n"))


if __name__ == "__main__":
    unittest.main()
