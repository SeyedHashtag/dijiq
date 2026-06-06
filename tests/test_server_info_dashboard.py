import importlib.util
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_API_PATH = ROOT / "core" / "cli_api.py"
SERVERINFO_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "serverinfo.py"
GB = 1024 ** 3


class OnlineResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, users):
        self.users = users

    def get_users(self):
        return self.users


def load_cli_api(payments=None, servers=None, clients=None, online_response=None, resellers=None):
    for name in list(sys.modules):
        if name == "utils" or name.startswith("utils."):
            sys.modules.pop(name, None)

    sys.modules["dotenv"] = types.SimpleNamespace(dotenv_values=lambda *args, **kwargs: {})
    sys.modules["psutil"] = types.SimpleNamespace(
        cpu_percent=lambda interval=1: 12.5,
        virtual_memory=lambda: types.SimpleNamespace(percent=40.0, used=512 * 1024 * 1024, total=1024 * 1024 * 1024),
        disk_usage=lambda _path: types.SimpleNamespace(percent=50.0, used=20 * GB, total=100 * GB),
    )

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    payment_records_stub = types.ModuleType("utils.payment_records")
    payment_records_stub.load_payments = lambda: payments or {}
    sys.modules["utils.payment_records"] = payment_records_stub

    referral_stub = types.ModuleType("utils.referral")
    referral_stub.load_referrals = lambda: {"stats": {"1": {"total_earnings": 5.0}}}
    sys.modules["utils.referral"] = referral_stub

    language_stub = types.ModuleType("utils.language")
    language_stub.load_user_languages = lambda: {"1": "en", "2": "fa", "3": "en"}
    sys.modules["utils.language"] = language_stub

    translations_stub = types.ModuleType("utils.translations")
    translations_stub.LANGUAGES = {"en": "English", "fa": "Persian"}
    sys.modules["utils.translations"] = translations_stub

    servers = servers or [
        {"id": "primary", "name": "Primary", "url": "https://primary.test", "token": "token", "enabled": True, "weight": 1},
        {"id": "backup", "name": "Backup", "url": "https://backup.test", "token": "token2", "enabled": True, "weight": 2},
    ]
    clients = clients or {
        "primary": FakeClient({
            "a": {"blocked": False, "upload_bytes": GB, "download_bytes": 2 * GB, "max_download_bytes": 10 * GB},
            "b": {"blocked": True, "upload_bytes": 512 * 1024 * 1024, "download_bytes": 512 * 1024 * 1024, "max_download_bytes": 2 * GB},
        }),
        "backup": FakeClient(None),
    }

    class FakeMultiServerAPI:
        def iter_clients(self, include_disabled=False):
            for server in servers:
                if include_disabled or server.get("enabled", True):
                    yield server, clients[server["id"]]

        @staticmethod
        def active_user_count(users):
            if isinstance(users, dict):
                return sum(1 for user in users.values() if isinstance(user, dict) and not user.get("blocked", False))
            if isinstance(users, list):
                return sum(1 for user in users if isinstance(user, dict) and not user.get("blocked", False))
            return 0

    api_client_stub = types.ModuleType("utils.api_client")
    api_client_stub.get_server_configs = lambda: servers
    api_client_stub.MultiServerAPI = FakeMultiServerAPI
    sys.modules["utils.api_client"] = api_client_stub

    reseller_stub = types.ModuleType("utils.reseller")
    reseller_stub.get_all_resellers = lambda: resellers or {}
    sys.modules["utils.reseller"] = reseller_stub

    spec = importlib.util.spec_from_file_location("cli_api_under_test", CLI_API_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    response = online_response if online_response is not None else OnlineResponse(200, {"primary": [2, {"nested": 3}]})
    module.requests = types.SimpleNamespace(get=lambda *args, **kwargs: response)
    return module


class ServerInfoDashboardTests(unittest.TestCase):
    def test_snapshot_includes_daily_sales_online_and_unhealthy_servers(self):
        payments = {
            "today-paid": {"status": "completed", "price": 10, "updated_at": "2026-06-04 10:00:00", "plan_gb": 10},
            "yesterday-paid": {"status": "paid", "price": "20", "created_at": "2026-06-03", "plan_gb": 20},
            "today-pending": {"status": "pending", "price": 99, "updated_at": "2026-06-04", "plan_gb": 10},
            "failed": {"status": "failed", "price": 50, "updated_at": "2026-06-02", "plan_gb": 10},
            "old-paid": {"status": "succeeded", "price": 5, "updated_at": "2026-05-28", "plan_gb": 5},
        }
        cli_api = load_cli_api(payments=payments, online_response=OnlineResponse(401, {"ignored": 3}))

        snapshot = cli_api.build_server_info_snapshot(now=datetime(2026, 6, 4, 12, 0, 0))
        text = cli_api.format_server_info(snapshot)

        self.assertEqual(snapshot["online"]["count"], 1)
        self.assertEqual(snapshot["online"]["status"], "ok")
        self.assertEqual(snapshot["sales"]["daily_sales"][0]["label"], "Jun 04")
        self.assertEqual(snapshot["sales"]["daily_sales"][0]["revenue"], 10)
        self.assertEqual(snapshot["sales"]["daily_sales"][0]["paid"], 1)
        self.assertEqual(snapshot["sales"]["daily_sales"][1]["revenue"], 20)
        self.assertEqual(snapshot["sales"]["buckets"]["all"]["pending"], 1)
        self.assertEqual(snapshot["sales"]["buckets"]["all"]["revenue"], 35)
        self.assertIn("Jun 04: $10.00 • 1 paid", text)
        self.assertIn("Online Users: 1", text)
        self.assertNotIn("Online Check: error (HTTP 401)", text)
        self.assertIn("⚠️ Pending Payments: 1", text)
        self.assertIn("Backup: unhealthy", text)

    def test_sold_traffic_counts_direct_and_reseller_configs_only(self):
        payments = {
            "direct": {"status": "completed", "price": 10, "updated_at": "2026-06-04", "plan_gb": 10, "username": "direct1", "server_id": "primary"},
            "direct-duplicate": {"status": "completed", "price": 10, "updated_at": "2026-06-04", "plan_gb": 10, "username": "direct1", "server_id": "primary"},
            "legacy-direct": {"status": "paid", "price": 20, "updated_at": "2026-06-03", "plan_gb": 20, "username": "legacy"},
            "missing-direct": {"status": "succeeded", "price": 5, "updated_at": "2026-06-02", "plan_gb": 5, "username": "missing", "server_id": "primary"},
            "pending": {"status": "pending", "price": 99, "updated_at": "2026-06-04", "plan_gb": 99, "username": "pending"},
            "rejected": {"status": "rejected", "price": 99, "updated_at": "2026-06-04", "plan_gb": 99, "username": "rejected"},
            "settlement": {"status": "completed", "price": 99, "updated_at": "2026-06-04", "plan_gb": "Settlement", "username": "settlement", "type": "settlement"},
        }
        servers = [
            {"id": "primary", "name": "Primary", "url": "https://primary.test", "token": "token", "enabled": True, "weight": 1},
            {"id": "backup", "name": "Backup", "url": "https://backup.test", "token": "token2", "enabled": True, "weight": 1},
        ]
        clients = {
            "primary": FakeClient({
                "direct1": {"blocked": False, "upload_bytes": GB, "download_bytes": 2 * GB, "max_download_bytes": 10 * GB},
                "manual": {"blocked": False, "upload_bytes": 100 * GB, "download_bytes": 100 * GB, "max_download_bytes": 200 * GB},
            }),
            "backup": FakeClient([
                {"username": "legacy", "blocked": False, "upload_bytes": 4 * GB, "download_bytes": 0, "max_download_bytes": 20 * GB},
                {"username": "resell1", "blocked": False, "upload_bytes": 5 * GB, "download_bytes": 5 * GB, "max_download_bytes": 40 * GB},
            ]),
        }
        resellers = {
            "42": {
                "configs": [
                    {"username": "resell1", "gb": 40, "server_id": "backup"},
                    {"username": "resell1", "gb": 40, "server_id": "backup"},
                    {"username": "missing-reseller", "gb": 2, "server_id": "backup"},
                    {"gb": 7, "server_id": "backup"},
                ]
            }
        }
        cli_api = load_cli_api(payments=payments, servers=servers, clients=clients, resellers=resellers)

        snapshot = cli_api.build_server_info_snapshot(now=datetime(2026, 6, 4, 12, 0, 0))
        traffic = snapshot["traffic"]
        text = cli_api.format_server_info(snapshot)

        self.assertEqual(traffic["direct"]["sold_configs"], 3)
        self.assertEqual(traffic["direct"]["matched_configs"], 2)
        self.assertEqual(traffic["direct"]["used_bytes"], 7 * GB)
        self.assertEqual(traffic["direct"]["sold_bytes"], 35 * GB)
        self.assertEqual(traffic["reseller"]["sold_configs"], 2)
        self.assertEqual(traffic["reseller"]["matched_configs"], 1)
        self.assertEqual(traffic["reseller"]["used_bytes"], 10 * GB)
        self.assertEqual(traffic["reseller"]["sold_bytes"], 42 * GB)
        self.assertEqual(traffic["total"]["used_bytes"], 17 * GB)
        self.assertEqual(traffic["total"]["sold_bytes"], 77 * GB)
        self.assertAlmostEqual(traffic["total"]["usage_percent"], 17 / 77 * 100)
        self.assertEqual(traffic["missing_configs"], 2)
        self.assertEqual(traffic["skipped_no_username"], 1)
        self.assertIn("Total Sold: 17.00GB served / 77.00GB sold (22.1%)", text)
        self.assertIn("Direct: 7.00GB / 35.00GB • 2 configs", text)
        self.assertIn("Reseller: 10.00GB / 42.00GB • 1 configs", text)
        self.assertIn("Missing Sold Configs: 2", text)
        self.assertNotIn("200.00GB", text)

    def test_online_payload_parser_supports_nested_shapes(self):
        cli_api = load_cli_api()

        self.assertEqual(cli_api.parse_online_users_payload({"a": [1, {"b": 2}], "c": {"d": 3}}), 6)
        self.assertEqual(cli_api.parse_online_users_payload([0, {"nested": [4, "5"]}]), 9)
        self.assertIsNone(cli_api.parse_online_users_payload({"unsupported": object()}))

    def test_online_userlist_count_excludes_blocked_and_disabled_servers(self):
        servers = [
            {"id": "primary", "name": "Primary", "url": "https://primary.test", "token": "token", "enabled": True, "weight": 1},
            {"id": "backup", "name": "Backup", "url": "https://backup.test", "token": "token2", "enabled": True, "weight": 1},
            {"id": "disabled", "name": "Disabled", "url": "https://disabled.test", "token": "token3", "enabled": False, "weight": 1},
        ]
        clients = {
            "primary": FakeClient({
                "a": {"blocked": False},
                "b": {"blocked": True},
            }),
            "backup": FakeClient([
                {"username": "c", "blocked": False},
                {"username": "d", "blocked": False},
                {"username": "e", "blocked": True},
            ]),
            "disabled": FakeClient({
                "ignored": {"blocked": False},
            }),
        }
        cli_api = load_cli_api(servers=servers, clients=clients)

        snapshot = cli_api.build_server_info_snapshot(now=datetime(2026, 6, 4, 12, 0, 0))
        text = cli_api.format_server_info(snapshot)

        self.assertEqual(snapshot["online"]["count"], 3)
        self.assertEqual(snapshot["online"]["status"], "ok")
        self.assertIn("Online Users: 3", text)

    def test_online_userlist_partial_failure_still_formats_count(self):
        cli_api = load_cli_api()

        snapshot = cli_api.build_server_info_snapshot(now=datetime(2026, 6, 4, 12, 0, 0))
        text = cli_api.format_server_info(snapshot)

        self.assertEqual(snapshot["online"]["count"], 1)
        self.assertEqual(snapshot["online"]["status"], "ok")
        self.assertIn("Online Users: 1", text)
        self.assertNotIn("Online Users: N/A", text)

    def test_online_failure_formats_as_na_not_zero(self):
        servers = [
            {"id": "primary", "name": "Primary", "url": "https://primary.test", "token": "token", "enabled": True, "weight": 1},
            {"id": "backup", "name": "Backup", "url": "https://backup.test", "token": "token2", "enabled": True, "weight": 1},
        ]
        clients = {"primary": FakeClient(None), "backup": FakeClient(None)}
        cli_api = load_cli_api(servers=servers, clients=clients)

        snapshot = cli_api.build_server_info_snapshot(now=datetime(2026, 6, 4, 12, 0, 0))
        text = cli_api.format_server_info(snapshot)

        self.assertIsNone(snapshot["online"]["count"])
        self.assertEqual(snapshot["online"]["status"], "error")
        self.assertIn("Online Users: N/A", text)
        self.assertNotIn("Online Users: 0", text)

    def test_online_unavailable_when_no_enabled_server_is_configured(self):
        servers = [
            {"id": "disabled", "name": "Disabled", "url": "https://disabled.test", "token": "token", "enabled": False, "weight": 1},
        ]
        clients = {"disabled": FakeClient({"ignored": {"blocked": False}})}
        cli_api = load_cli_api(servers=servers, clients=clients)

        snapshot = cli_api.build_server_info_snapshot(now=datetime(2026, 6, 4, 12, 0, 0))
        text = cli_api.format_server_info(snapshot)

        self.assertIsNone(snapshot["online"]["count"])
        self.assertEqual(snapshot["online"]["status"], "unavailable")
        self.assertIn("Online Users: N/A", text)


class DummyMarkup:
    def __init__(self, *args, **kwargs):
        self.buttons = []

    def add(self, *args, **kwargs):
        self.buttons.extend(args)
        return self


class DummyButton:
    def __init__(self, text, **kwargs):
        self.text = text
        self.callback_data = kwargs.get("callback_data")


class DummyBot:
    def __init__(self):
        self.replies = []
        self.edits = []
        self.answers = []
        self.actions = []

    def message_handler(self, *args, **kwargs):
        return lambda func: func

    def callback_query_handler(self, *args, **kwargs):
        return lambda func: func

    def send_chat_action(self, *args, **kwargs):
        self.actions.append((args, kwargs))

    def reply_to(self, *args, **kwargs):
        self.replies.append((args, kwargs))

    def edit_message_text(self, *args, **kwargs):
        self.edits.append((args, kwargs))

    def answer_callback_query(self, *args, **kwargs):
        self.answers.append((args, kwargs))


def load_serverinfo_module():
    for name in list(sys.modules):
        if name == "utils" or name.startswith("utils."):
            sys.modules.pop(name, None)

    bot = DummyBot()
    telebot_stub = types.ModuleType("telebot")
    telebot_stub.types = types.SimpleNamespace(InlineKeyboardMarkup=DummyMarkup, InlineKeyboardButton=DummyButton)
    sys.modules["telebot"] = telebot_stub
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    command_stub = types.ModuleType("utils.command")
    command_stub.bot = bot
    command_stub.CLI_PATH = "/fake/cli.py"
    command_stub.is_admin = lambda user_id: user_id == 1
    command_stub.run_cli_command = lambda command: "dashboard text"
    sys.modules["utils.command"] = command_stub

    spec = importlib.util.spec_from_file_location("serverinfo_under_test", SERVERINFO_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, bot


class ServerInfoTelegramTests(unittest.TestCase):
    def test_server_info_reply_includes_refresh_markup(self):
        module, bot = load_serverinfo_module()
        message = types.SimpleNamespace(from_user=types.SimpleNamespace(id=1), chat=types.SimpleNamespace(id=10))

        module.server_info(message)

        self.assertEqual(bot.replies[0][0][1], "dashboard text")
        markup = bot.replies[0][1]["reply_markup"]
        self.assertEqual(markup.buttons[0].callback_data, "server_info:refresh")

    def test_refresh_edits_existing_message_and_blocks_unauthorized_users(self):
        module, bot = load_serverinfo_module()
        call = types.SimpleNamespace(
            id="ok",
            data="server_info:refresh",
            from_user=types.SimpleNamespace(id=1),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=10), message_id=77),
        )

        module.handle_server_info_refresh(call)

        self.assertEqual(bot.edits[0][0][0], "dashboard text")
        self.assertEqual(bot.edits[0][1]["chat_id"], 10)
        self.assertEqual(bot.edits[0][1]["message_id"], 77)

        blocked_call = types.SimpleNamespace(
            id="blocked",
            data="server_info:refresh",
            from_user=types.SimpleNamespace(id=2),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(id=10), message_id=77),
        )
        module.handle_server_info_refresh(blocked_call)

        self.assertEqual(bot.answers[-1][0][1], "Unauthorized.")


if __name__ == "__main__":
    unittest.main()
