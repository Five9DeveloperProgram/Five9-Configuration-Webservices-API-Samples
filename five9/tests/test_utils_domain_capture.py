import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from git import Repo

from five9.utils import domain_capture


def _fake_client(domain_name):
    client = mock.Mock()
    client.service.getVCCConfiguration.return_value = SimpleNamespace(
        domainName=domain_name
    )
    return client


class TestSnapshotRepoPersistence(unittest.TestCase):
    """The snapshot git repo must survive repeated captures of the same domain."""

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def _capture(self, domain="Test Domain", files=None):
        cfg = domain_capture.Five9DomainConfig(
            client=_fake_client(domain), methods=[]
        )
        for name, text in (files or {}).items():
            with open(os.path.join(cfg.domain_path, name), "w") as f:
                f.write(text)
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


if __name__ == "__main__":
    unittest.main()
