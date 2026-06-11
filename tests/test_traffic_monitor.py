import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "traffic_monitor.py"
)

GB = 1024 ** 3


class FakeBot:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append((chat_id, text, kwargs))


class FakeClient:
    server_id = "primary"


class FakeMultiServerAPI:
    def __init__(self, users):
        self.servers = [{"id": "enabled", "enabled": True}]
        self.users = users
        self.include_disabled_calls = []

    def iter_all_users(self, include_disabled=True):
        self.include_disabled_calls.append(include_disabled)
        for enabled, username, data in self.users:
            if include_disabled or enabled:
                yield FakeClient(), username, data


def install_stubs():
    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    api_client_stub = types.ModuleType("utils.api_client")
    api_client_stub.MultiServerAPI = lambda: FakeMultiServerAPI([])
    sys.modules["utils.api_client"] = api_client_stub

    command_stub = types.ModuleType("utils.command")
    command_stub.bot = FakeBot()
    sys.modules["utils.command"] = command_stub

    language_stub = types.ModuleType("utils.language")
    language_stub.get_user_language = lambda user_id: "en"
    sys.modules["utils.language"] = language_stub

    translations_stub = types.ModuleType("utils.translations")
    translations_stub.get_message_text = lambda language, key: {
        "traffic_quota_alert": "regular {username} {percent}",
        "reseller_client_traffic_alert": "reseller-gb {username} {percent}",
        "reseller_client_days_alert": "reseller-days {username} {percent} {days_used} {total_days} {days_remaining}",
    }[key]
    sys.modules["utils.translations"] = translations_stub


def load_traffic_monitor_module():
    install_stubs()
    module_name = "traffic_monitor_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TrafficMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.monitor = load_traffic_monitor_module()
        self.monitor.ALERTS_FILE = str(Path(self.tmp_dir.name) / "traffic_alerts.json")
        self.monitor.RESELLERS_FILE = str(Path(self.tmp_dir.name) / "resellers.json")
        self.bot = FakeBot()
        self.monitor.bot = self.bot

    def tearDown(self):
        self.tmp_dir.cleanup()

    def run_monitor(self, users):
        multi_api = FakeMultiServerAPI(users)
        self.monitor.MultiServerAPI = lambda: multi_api
        self.monitor.monitor_user_traffic()
        return multi_api

    def read_alerts(self):
        with open(self.monitor.ALERTS_FILE, "r") as f:
            return json.load(f)

    def write_alerts(self, alerts):
        with open(self.monitor.ALERTS_FILE, "w") as f:
            json.dump(alerts, f)

    def write_reseller_days(self, reseller_id, username, days):
        with open(self.monitor.RESELLERS_FILE, "w") as f:
            json.dump({str(reseller_id): {"configs": [{"username": username, "days": days}]}}, f)

    def test_regular_user_at_95_percent_gets_one_alert_and_marks_all_crossed_thresholds(self):
        self.run_monitor([
            (True, "s123", {"upload_bytes": 95 * GB, "download_bytes": 0, "max_download_bytes": 100 * GB}),
        ])

        self.assertEqual(len(self.bot.sent_messages), 1)
        self.assertEqual(self.bot.sent_messages[0][0], 123)
        self.assertIn("regular s123 95", self.bot.sent_messages[0][1])
        self.assertEqual(self.read_alerts()["s123"]["notified"], [80, 90])

    def test_reseller_client_at_95_percent_gb_gets_one_alert_and_marks_all_crossed_thresholds(self):
        self.run_monitor([
            (True, "r456", {"upload_bytes": 95 * GB, "download_bytes": 0, "max_download_bytes": 100 * GB}),
        ])

        self.assertEqual(len(self.bot.sent_messages), 1)
        self.assertEqual(self.bot.sent_messages[0][0], 456)
        self.assertIn("reseller-gb r456 95", self.bot.sent_messages[0][1])
        self.assertEqual(self.read_alerts()["r456"]["gb_notified"], [80, 90])

    def test_reseller_client_at_95_percent_days_gets_one_alert_and_marks_all_crossed_thresholds(self):
        self.write_reseller_days(456, "r456", 100)

        self.run_monitor([
            (True, "r456", {"expiration_days": 5, "max_download_bytes": 0}),
        ])

        self.assertEqual(len(self.bot.sent_messages), 1)
        self.assertEqual(self.bot.sent_messages[0][0], 456)
        self.assertIn("reseller-days r456 95", self.bot.sent_messages[0][1])
        self.assertEqual(self.read_alerts()["r456"]["days_notified"], [80, 90])

    def test_regular_user_already_notified_at_80_only_gets_90_alert(self):
        self.write_alerts({"s123": {"notified": [80], "max_download_bytes": 100 * GB}})

        self.run_monitor([
            (True, "s123", {"upload_bytes": 95 * GB, "download_bytes": 0, "max_download_bytes": 100 * GB}),
        ])

        self.assertEqual(len(self.bot.sent_messages), 1)
        self.assertIn("regular s123 95", self.bot.sent_messages[0][1])
        self.assertEqual(self.read_alerts()["s123"]["notified"], [80, 90])

    def test_disabled_servers_are_skipped_by_quota_monitoring(self):
        multi_api = self.run_monitor([
            (False, "s123", {"upload_bytes": 95 * GB, "download_bytes": 0, "max_download_bytes": 100 * GB}),
        ])

        self.assertEqual(multi_api.include_disabled_calls, [False])
        self.assertEqual(self.bot.sent_messages, [])


if __name__ == "__main__":
    unittest.main()
