import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENEWAL_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "renewal.py"
GB_BYTES = 1024 ** 3


class FakeClient:
    def __init__(self, server_id, users=None):
        self.server_id = server_id
        self.users = dict(users or {})
        self.reset_calls = []

    def get_user(self, username):
        return self.users.get(username)

    def reset_user(self, username):
        self.reset_calls.append(username)
        user = self.users.get(username)
        if user is None:
            return None
        user.update({
            "blocked": False,
            "expiration_days": 30,
            "upload_bytes": 0,
            "download_bytes": 0,
            "status": "active",
        })
        return {"ok": True}

    def get_user_uri(self, username):
        return {"normal_sub": f"https://sub.example/{username}", "ipv4": ""}


class FakeMultiAPI:
    def __init__(self, clients):
        self.clients = dict(clients)

    def find_user(self, username, preferred_server_id=None):
        if preferred_server_id:
            client = self.clients.get(preferred_server_id)
            if client and client.get_user(username):
                return client, client.get_user(username)
        for client in self.clients.values():
            user = client.get_user(username)
            if user:
                return client, user
        return None, None


def load_renewal_module():
    for name in list(sys.modules):
        if name == "utils" or name.startswith("utils."):
            sys.modules.pop(name, None)

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg

    api_client_stub = types.ModuleType("utils.api_client")
    api_client_stub.MultiServerAPI = lambda: FakeMultiAPI({})
    sys.modules["utils.api_client"] = api_client_stub

    edit_plans_stub = types.ModuleType("utils.edit_plans")
    edit_plans_stub.load_plans = lambda: {}
    sys.modules["utils.edit_plans"] = edit_plans_stub

    currency_stub = types.ModuleType("utils.currency_format")
    currency_stub.format_usd_amount = lambda value: f"{float(value):.2f}"
    sys.modules["utils.currency_format"] = currency_stub

    translations_stub = types.ModuleType("utils.translations")
    translations_stub.get_message_text = lambda _language, key: {
        "renewal_offer_details": (
            "Renew {username} {plan_gb}GB {days}d ${price}\n"
            "Before\n{before}\nAfter\n{after}{payment_prompt}"
        ),
        "renewal_quota_reset_warning": "Quota resets",
        "renewal_success": (
            "Renewed {username} {plan_gb}GB {days}d\n"
            "Before\n{before}\nAfter\n{after}\n{ipv4_info}{sub_url}"
        ),
        "select_payment_method": "Select payment method",
    }.get(key, key)
    sys.modules["utils.translations"] = translations_stub

    spec = importlib.util.spec_from_file_location("renewal_under_test", RENEWAL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.base = Path(self.tmpdir.name)
        self.renewal = load_renewal_module()
        self.renewal.PAYMENTS_FILE = str(self.base / "payments.json")
        self.renewal.RESELLERS_FILE = str(self.base / "resellers.json")
        self.renewal.STATE_FILE = str(self.base / "expired_user_cleanup.json")
        self.plans = {
            "5": {"price": 12.0, "days": 30, "unlimited": False, "target": "both"},
            "10": {"price": 20.0, "days": 60, "unlimited": True, "target": "both"},
        }

    def write_json(self, path, data):
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    def read_json(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def expired_user(self, max_gb=5):
        return {
            "blocked": True,
            "expiration_days": 0,
            "upload_bytes": GB_BYTES,
            "download_bytes": 2 * GB_BYTES,
            "max_download_bytes": max_gb * GB_BYTES,
            "status": "expired",
        }

    def base_payment(self, **overrides):
        data = {
            "user_id": 123,
            "username": "alice",
            "server_id": "s1",
            "plan_gb": "5",
            "days": 30,
            "unlimited": False,
            "status": "completed",
            "price": 10.0,
        }
        data.update(overrides)
        return data

    def test_customer_offer_is_eligible_for_expired_matching_current_plan(self):
        payments = {"base-1": self.base_payment()}
        client = FakeClient("s1", {"alice": self.expired_user()})

        offer = self.renewal.find_customer_renewal_offer(
            123,
            "alice",
            client,
            client.get_user("alice"),
            self.plans,
            payments=payments,
        )

        self.assertTrue(offer["eligible"])
        self.assertEqual(offer["username"], "alice")
        self.assertEqual(offer["base_record_id"], "base-1")
        self.assertEqual(offer["price"], 12.0)
        self.assertEqual(offer["days"], 30)
        self.assertEqual(offer["before_state"]["gb_limit"], 5.0)
        self.assertEqual(offer["expected_after_state"]["gb_used"], 0.0)
        self.assertEqual(len(offer["token"]), 16)

    def test_customer_offer_rejects_missing_active_blocked_active_deleted_and_plan_mismatch(self):
        payments = {"base-1": self.base_payment()}
        client = FakeClient("s1", {"alice": self.expired_user()})

        missing_offer = self.renewal.find_customer_renewal_offer(
            123, "alice", None, None, self.plans, payments=payments
        )
        self.assertEqual(missing_offer["reason"], "renewal_ineligible_missing")

        active_user = dict(self.expired_user(), blocked=False, expiration_days=12)
        active_offer = self.renewal.find_customer_renewal_offer(
            123, "alice", client, active_user, self.plans, payments=payments
        )
        self.assertEqual(active_offer["reason"], "renewal_ineligible_not_expired")

        manually_blocked_user = dict(self.expired_user(), expiration_days=12, upload_bytes=0, download_bytes=0)
        blocked_offer = self.renewal.find_customer_renewal_offer(
            123, "alice", client, manually_blocked_user, self.plans, payments=payments
        )
        self.assertEqual(blocked_offer["reason"], "renewal_ineligible_not_expired")

        deleted_offer = self.renewal.find_customer_renewal_offer(
            123,
            "alice",
            client,
            client.get_user("alice"),
            self.plans,
            payments={"base-1": self.base_payment(cleanup_status="deleted")},
        )
        self.assertEqual(deleted_offer["reason"], "renewal_ineligible_no_record")

        day_mismatch_offer = self.renewal.find_customer_renewal_offer(
            123,
            "alice",
            client,
            client.get_user("alice"),
            self.plans,
            payments={"base-1": self.base_payment(days=15)},
        )
        self.assertEqual(day_mismatch_offer["reason"], "renewal_ineligible_plan_mismatch")

        quota_mismatch_offer = self.renewal.find_customer_renewal_offer(
            123,
            "alice",
            client,
            self.expired_user(max_gb=4),
            self.plans,
            payments=payments,
        )
        self.assertEqual(quota_mismatch_offer["reason"], "renewal_ineligible_plan_mismatch")

    def test_customer_offer_rejects_reseller_only_plan(self):
        plans = {
            "1": {"price": 2.0, "days": 7, "unlimited": False, "target": "reseller"},
        }
        payments = {"base-1": self.base_payment(plan_gb="1", days=7, unlimited=False)}
        client = FakeClient("s1", {"alice": self.expired_user(max_gb=1)})

        offer = self.renewal.find_customer_renewal_offer(
            123,
            "alice",
            client,
            client.get_user("alice"),
            plans,
            payments=payments,
        )

        self.assertFalse(offer["eligible"])
        self.assertEqual(offer["reason"], "renewal_ineligible_plan_mismatch")

    def test_missing_legacy_unlimited_metadata_does_not_block_matching_renewal(self):
        plans = {
            "5": {"price": 12.0, "days": 30, "unlimited": True, "target": "both"},
        }
        customer_record = self.base_payment()
        customer_record.pop("unlimited", None)
        client = FakeClient("s1", {"alice": self.expired_user()})

        customer_offer = self.renewal.find_customer_renewal_offer(
            123,
            "alice",
            client,
            client.get_user("alice"),
            plans,
            payments={"base-1": customer_record},
        )

        reseller_data = {
            "configs": [{
                "username": "bob",
                "server_id": "s1",
                "gb": "5",
                "days": 30,
                "price": 9.6,
            }]
        }
        reseller_client = FakeClient("s1", {"bob": self.expired_user()})
        reseller_offer = self.renewal.find_reseller_renewal_offer(
            "1988",
            0,
            reseller_client,
            reseller_client.get_user("bob"),
            plans,
            reseller_data=reseller_data,
        )

        self.assertTrue(customer_offer["eligible"])
        self.assertTrue(reseller_offer["eligible"])

    def test_explicit_unlimited_mismatch_still_blocks_renewal(self):
        plans = {
            "5": {"price": 12.0, "days": 30, "unlimited": True, "target": "both"},
        }
        client = FakeClient("s1", {"alice": self.expired_user()})
        customer_offer = self.renewal.find_customer_renewal_offer(
            123,
            "alice",
            client,
            client.get_user("alice"),
            plans,
            payments={"base-1": self.base_payment(unlimited=False)},
        )

        reseller_data = {
            "configs": [{
                "username": "bob",
                "server_id": "s1",
                "gb": "5",
                "days": 30,
                "unlimited": False,
                "price": 9.6,
            }]
        }
        reseller_client = FakeClient("s1", {"bob": self.expired_user()})
        reseller_offer = self.renewal.find_reseller_renewal_offer(
            "1988",
            0,
            reseller_client,
            reseller_client.get_user("bob"),
            plans,
            reseller_data=reseller_data,
        )

        self.assertEqual(customer_offer["reason"], "renewal_ineligible_plan_mismatch")
        self.assertEqual(reseller_offer["reason"], "renewal_ineligible_plan_mismatch")

    def test_customer_renewal_resets_existing_user_and_clears_cleanup_state(self):
        client = FakeClient("s1", {"alice": self.expired_user()})
        multi_api = FakeMultiAPI({"s1": client})
        self.write_json(self.renewal.PAYMENTS_FILE, {"base-1": self.base_payment()})
        self.write_json(self.renewal.STATE_FILE, {
            "s1:alice": {"username": "alice", "server_id": "s1", "cleanup_status": "notified"}
        })
        payment_record = {
            "type": "renewal",
            "user_id": 123,
            "plan_gb": "5",
            "days": 30,
            "unlimited": False,
            "renewal_source": "customer",
            "renewal_username": "alice",
            "renewal_server_id": "s1",
            "renewal_base_record_id": "base-1",
        }

        result = self.renewal.execute_customer_renewal(payment_record, plans=self.plans, multi_api=multi_api)

        self.assertTrue(result["success"])
        self.assertEqual(client.reset_calls, ["alice"])
        self.assertFalse(client.get_user("alice")["blocked"])
        self.assertEqual(result["before_state"]["status"], "expired")
        self.assertEqual(result["after_state"]["status"], "active")
        saved_payments = self.read_json(self.renewal.PAYMENTS_FILE)
        self.assertEqual(saved_payments["base-1"]["cleanup_status"], "renewed")
        self.assertEqual(self.read_json(self.renewal.STATE_FILE), {})

    def test_customer_renewal_rechecks_expiry_at_execution_time(self):
        active_user = dict(self.expired_user(), blocked=False, expiration_days=30)
        client = FakeClient("s1", {"alice": active_user})
        payment_record = {
            "type": "renewal",
            "plan_gb": "5",
            "days": 30,
            "unlimited": False,
            "renewal_username": "alice",
            "renewal_server_id": "s1",
            "renewal_base_record_id": "base-1",
        }

        result = self.renewal.execute_customer_renewal(
            payment_record,
            plans=self.plans,
            multi_api=FakeMultiAPI({"s1": client}),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "renewal_ineligible_not_expired")
        self.assertEqual(client.reset_calls, [])

    def test_reseller_offer_uses_discount_and_resets_existing_user(self):
        reseller_data = {
            "configs": [{
                "username": "bob",
                "server_id": "s1",
                "gb": "5",
                "days": 30,
                "unlimited": False,
                "price": 9.6,
            }]
        }
        client = FakeClient("s1", {"bob": self.expired_user()})

        offer = self.renewal.find_reseller_renewal_offer(
            "1988",
            0,
            client,
            client.get_user("bob"),
            self.plans,
            reseller_data=reseller_data,
        )
        result = self.renewal.execute_reseller_renewal(offer, multi_api=FakeMultiAPI({"s1": client}))

        self.assertTrue(offer["eligible"])
        self.assertAlmostEqual(offer["price"], 9.6)
        self.assertEqual(offer["full_price"], 12.0)
        self.assertTrue(result["success"])
        self.assertEqual(client.reset_calls, ["bob"])

    def test_reseller_offer_accepts_reseller_only_plan(self):
        reseller_data = {
            "configs": [{
                "username": "bob",
                "server_id": "s1",
                "gb": "1",
                "days": 7,
                "unlimited": False,
                "price": 1.6,
            }]
        }
        plans = {
            "1": {"price": 2.0, "days": 7, "unlimited": False, "target": "reseller"},
        }
        client = FakeClient("s1", {"bob": self.expired_user(max_gb=1)})

        offer = self.renewal.find_reseller_renewal_offer(
            "1988",
            0,
            client,
            client.get_user("bob"),
            plans,
            reseller_data=reseller_data,
        )

        self.assertTrue(offer["eligible"])
        self.assertAlmostEqual(offer["price"], 1.6)


if __name__ == "__main__":
    unittest.main()
