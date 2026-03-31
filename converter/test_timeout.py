"""
RuleConverter 超时处理测试
测试场景：
1. HEAD 请求超时
2. GET 请求超时
3. Git 命令超时
4. 正常请求（不超时）
"""

import unittest
import unittest.mock
import socket
import urllib.error
import subprocess
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from RuleConverter import run_git_command, process_task, get_proxy_url


class TestTimeoutConfig(unittest.TestCase):
    """测试超时配置读取"""

    def test_get_proxy_url_enabled(self):
        config = {
            "settings": {"proxy": {"enabled": True, "host": "127.0.0.1", "port": 6667}}
        }
        self.assertEqual(get_proxy_url(config), "http://127.0.0.1:6667")

    def test_get_proxy_url_disabled(self):
        config = {
            "settings": {"proxy": {"enabled": False, "host": "127.0.0.1", "port": 6667}}
        }
        self.assertIsNone(get_proxy_url(config))

    def test_get_proxy_url_missing(self):
        config = {"settings": {}}
        self.assertIsNone(get_proxy_url(config))


class TestNetworkTimeout(unittest.TestCase):
    """测试网络超时处理"""

    def setUp(self):
        self.config = {
            "settings": {
                "user_agent": "TestAgent",
                "proxy": {"enabled": False},
                "timeout": {"head_request": 1, "get_request": 1, "git_command": 1},
            },
            "state": {},
        }
        self.repo_dir = os.path.dirname(__file__)

    @unittest.mock.patch("urllib.request.OpenerDirector.open")
    def test_head_request_timeout(self, mock_open):
        mock_open.side_effect = socket.timeout("HEAD request timed out")
        result = process_task(
            "http://example.com/test.list",
            self.repo_dir,
            "test",
            "TestTask",
            self.config,
        )
        self.assertFalse(result)

    @unittest.mock.patch("urllib.request.OpenerDirector.open")
    def test_get_request_timeout(self, mock_open):
        mock_open.side_effect = [
            unittest.mock.MagicMock(
                getheader=lambda x: "new-etag" if x == "ETag" else None
            ),
            socket.timeout("GET request timed out"),
        ]
        result = process_task(
            "http://example.com/test.list",
            self.repo_dir,
            "test",
            "TestTask",
            self.config,
        )
        self.assertFalse(result)

    @unittest.mock.patch("urllib.request.OpenerDirector.open")
    def test_url_error_network_failure(self, mock_open):
        mock_open.side_effect = urllib.error.URLError("Connection refused")
        result = process_task(
            "http://example.com/test.list",
            self.repo_dir,
            "test",
            "TestTask",
            self.config,
        )
        self.assertFalse(result)


class TestGitTimeout(unittest.TestCase):
    """测试 Git 命令超时处理"""

    def setUp(self):
        self.repo_dir = os.path.dirname(__file__)

    @unittest.mock.patch("subprocess.run")
    def test_git_command_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git status", timeout=1)
        success, msg = run_git_command(self.repo_dir, ["status"], timeout=1)
        self.assertFalse(success)
        self.assertIn("超时", msg)


class TestNormalOperation(unittest.TestCase):
    """测试正常操作（不超时）"""

    def setUp(self):
        self.config = {
            "settings": {
                "user_agent": "TestAgent",
                "proxy": {"enabled": False},
                "timeout": {"head_request": 10, "get_request": 30, "git_command": 60},
            },
            "state": {"TestTask": "old-etag"},
        }
        self.repo_dir = os.path.dirname(__file__)

    @unittest.mock.patch("urllib.request.OpenerDirector.open")
    def test_skip_when_up_to_date(self, mock_open):
        mock_response = unittest.mock.MagicMock()
        mock_response.getheader.side_effect = (
            lambda x: "old-etag" if x == "ETag" else None
        )
        mock_open.return_value.__enter__ = unittest.mock.MagicMock(
            return_value=mock_response
        )
        mock_open.return_value.__exit__ = unittest.mock.MagicMock(return_value=False)

        with unittest.mock.patch("os.path.exists", return_value=True):
            result = process_task(
                "http://example.com/test.list",
                self.repo_dir,
                "test",
                "TestTask",
                self.config,
            )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
