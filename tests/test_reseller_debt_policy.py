import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESELLER_PATH = ROOT / "core" / "scripts" / "telegrambot" / "utils" / "reseller.py"


def load_reseller_module():
    spec = importlib.util.spec_from_file_location("reseller_policy_under_test", RESELLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResellerDebtPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.resellers_file = Path(self.tmpdir.name) / "resellers.json"
        self.reseller = load_reseller_module()
        self.reseller.RESELLERS_FILE = str(self.resellers_file)

    def write_resellers(self, data):
        self.resellers_file.write_text(json.dumps(data), encoding="utf-8")

    def read_resellers(self):
        return json.loads(self.resellers_file.read_text(encoding="utf-8"))

    def hours_ago(self, hours):
        return (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    def test_trust_limit_tiers_cap_at_thirty(self):
        cases = [
            (0.0, 5.0),
            (9.99, 5.0),
            (10.0, 10.0),
            (20.0, 15.0),
            (30.0, 20.0),
            (40.0, 25.0),
            (50.0, 30.0),
            (200.0, 30.0),
        ]

        for total_paid, expected_limit in cases:
            with self.subTest(total_paid=total_paid):
                self.assertEqual(self.reseller.get_reseller_trust_limit(total_paid), expected_limit)

    def test_missing_total_paid_is_derived_from_legacy_turnover_minus_debt(self):
        self.write_resellers({
            "1988": {
                "status": "approved",
                "debt": 15.0,
                "configs": [
                    {"price": 20.0},
                    {"price": 10.0},
                ],
            }
        })

        data = self.reseller.get_reseller_data("1988")

        self.assertEqual(data["total_paid"], 15.0)
        self.assertEqual(data["trust_limit"], 10.0)

    def test_missing_total_paid_ignores_removed_cleanup_history(self):
        self.write_resellers({
            "1988": {
                "status": "approved",
                "debt": 5.0,
                "configs": [
                    {"price": 20.0},
                    {
                        "price": 10.0,
                        "removed_from_vpn": True,
                        "removal_reason": "banned_reseller_cleanup",
                    },
                ],
            }
        })

        data = self.reseller.get_reseller_data("1988")

        self.assertEqual(data["total_paid"], 15.0)

    def test_successful_payment_increments_total_paid_by_debt_credit(self):
        self.write_resellers({
            "1988": {
                "status": "approved",
                "debt": 15.0,
                "total_paid": 20.0,
                "configs": [
                    {"price": 20.0},
                    {"price": 15.0},
                ],
            }
        })

        success, new_debt = self.reseller.apply_reseller_payment("1988", 10.0)
        saved = self.read_resellers()["1988"]

        self.assertTrue(success)
        self.assertEqual(new_debt, 5.0)
        self.assertEqual(saved["total_paid"], 30.0)
        self.assertEqual(saved["trust_limit"], 20.0)
        self.assertIsNotNone(saved["last_payment_at"])

    def test_overpayment_only_increments_total_paid_by_debt_reduction(self):
        self.write_resellers({
            "1988": {
                "status": "approved",
                "debt": 8.0,
                "total_paid": 0.0,
                "configs": [{"price": 8.0}],
            }
        })

        success, new_debt = self.reseller.apply_reseller_payment("1988", 20.0)
        saved = self.read_resellers()["1988"]

        self.assertTrue(success)
        self.assertEqual(new_debt, 0.0)
        self.assertEqual(saved["total_paid"], 8.0)
        self.assertEqual(saved["trust_limit"], 5.0)

    def test_manual_payment_validation_rejects_overpayment(self):
        valid, normalized, reason = self.reseller.validate_reseller_manual_payment_amount(20.0, 8.0)

        self.assertFalse(valid)
        self.assertEqual(normalized, 20.0)
        self.assertEqual(reason, "over_debt")

    def test_manual_payment_validation_rejects_non_positive_amounts(self):
        for amount in (0.0, -1.0):
            with self.subTest(amount=amount):
                valid, normalized, reason = self.reseller.validate_reseller_manual_payment_amount(amount, 8.0)

                self.assertFalse(valid)
                self.assertEqual(normalized, amount)
                self.assertEqual(reason, "invalid")

    def test_can_reseller_add_debt_uses_current_trust_limit(self):
        reseller_data = {
            "debt": 4.0,
            "total_paid": 0.0,
            "configs": [],
        }

        can_add, trust_limit, available_credit = self.reseller.can_reseller_add_debt(reseller_data, 1.0)
        self.assertTrue(can_add)
        self.assertEqual(trust_limit, 5.0)
        self.assertEqual(available_credit, 1.0)

        can_add, trust_limit, available_credit = self.reseller.can_reseller_add_debt(reseller_data, 1.01)
        self.assertFalse(can_add)
        self.assertEqual(trust_limit, 5.0)
        self.assertEqual(available_credit, 1.0)

    def test_approved_reseller_auto_suspends_after_suspend_deadline(self):
        self.write_resellers({
            "1988": {
                "status": "approved",
                "debt": 30.0,
                "debt_since": self.hours_ago(49),
                "configs": [],
            }
        })

        events = self.reseller.evaluate_reseller_debt_policies()
        saved = self.read_resellers()["1988"]

        self.assertEqual(saved["status"], "suspended")
        self.assertEqual(saved["suspended_reason"], "debt")
        self.assertTrue(any(event["auto_suspended"] for event in events))

    def test_low_debt_reseller_auto_suspends_after_suspend_deadline(self):
        self.write_resellers({
            "1988": {
                "status": "approved",
                "debt": 9.70,
                "debt_since": self.hours_ago(49),
                "configs": [],
            }
        })

        events = self.reseller.evaluate_reseller_debt_policies()
        saved = self.read_resellers()["1988"]

        self.assertEqual(saved["status"], "suspended")
        self.assertEqual(saved["debt_state"], "suspended")
        self.assertEqual(saved["suspended_reason"], "debt")
        auto_suspended_event = next(event for event in events if event["auto_suspended"])
        self.assertEqual(auto_suspended_event["unlock_amount"], 9.70)

    def test_auto_suspended_reseller_auto_bans_after_ban_deadline(self):
        self.write_resellers({
            "1988": {
                "status": "suspended",
                "suspended_reason": "debt",
                "debt": 30.0,
                "debt_since": self.hours_ago(73),
                "configs": [],
            }
        })

        events = self.reseller.evaluate_reseller_debt_policies()
        saved = self.read_resellers()["1988"]

        self.assertEqual(saved["status"], "banned")
        self.assertIsNone(saved["suspended_reason"])
        self.assertTrue(any(event["auto_banned"] for event in events))

    def test_unbanned_reseller_auto_bans_after_grace_deadline(self):
        self.write_resellers({
            "1988": {
                "status": "suspended",
                "suspended_reason": self.reseller.SUSPENDED_REASON_UNBAN_GRACE,
                "suspended_at": self.hours_ago(25),
                "debt": 0.0,
                "configs": [],
            }
        })

        events = self.reseller.evaluate_reseller_debt_policies()
        saved = self.read_resellers()["1988"]

        self.assertEqual(saved["status"], "banned")
        self.assertIsNone(saved["suspended_reason"])
        self.assertIsNone(saved["suspended_at"])
        self.assertTrue(any(event["auto_banned"] for event in events))

    def test_unban_status_change_moves_banned_reseller_to_temporary_suspended(self):
        self.write_resellers({
            "1988": {
                "status": "banned",
                "debt": 0.0,
                "configs": [],
            }
        })

        self.reseller.update_reseller_status(
            "1988",
            "suspended",
            suspended_reason=self.reseller.SUSPENDED_REASON_UNBAN_GRACE,
        )
        saved = self.read_resellers()["1988"]

        self.assertEqual(saved["status"], "suspended")
        self.assertEqual(saved["suspended_reason"], self.reseller.SUSPENDED_REASON_UNBAN_GRACE)
        self.assertIsNotNone(saved["suspended_at"])

    def test_cleared_auto_suspension_restores_approved_status(self):
        self.write_resellers({
            "1988": {
                "status": "suspended",
                "suspended_reason": "debt",
                "debt": 30.0,
                "debt_since": "2000-01-01 00:00:00",
                "configs": [],
            }
        })

        success, new_debt = self.reseller.apply_reseller_payment("1988", 30.0)
        saved = self.read_resellers()["1988"]

        self.assertTrue(success)
        self.assertEqual(new_debt, 0.0)
        self.assertEqual(saved["status"], "approved")
        self.assertEqual(saved["debt"], 0.0)
        self.assertIsNone(saved["debt_since"])
        self.assertIsNotNone(saved["last_payment_at"])
        self.assertIsNone(saved["suspended_reason"])

    def test_manual_suspension_is_not_auto_restored_when_debt_is_cleared(self):
        self.write_resellers({
            "1988": {
                "status": "suspended",
                "suspended_reason": None,
                "debt": 30.0,
                "debt_since": "2000-01-01 00:00:00",
                "configs": [],
            }
        })

        success, new_debt = self.reseller.apply_reseller_payment("1988", 30.0)
        saved = self.read_resellers()["1988"]

        self.assertTrue(success)
        self.assertEqual(new_debt, 0.0)
        self.assertEqual(saved["status"], "suspended")
        self.assertIsNone(saved["suspended_reason"])

    def test_cleanup_candidates_include_only_configs_after_last_payment(self):
        candidates = self.reseller.get_banned_reseller_cleanup_candidates({
            "status": "banned",
            "last_payment_at": "2026-06-01 12:00:00",
            "configs": [
                {"username": "old", "timestamp": "2026-06-01 11:59:59", "price": 2},
                {"username": "new", "timestamp": "2026-06-01 12:00:01", "price": 3},
                {"username": "", "timestamp": "2026-06-01 12:00:02", "price": 4},
                {"timestamp": "2026-06-01 12:00:03", "price": 5},
            ],
        })

        self.assertEqual([candidate["username"] for candidate in candidates], ["new"])
        self.assertEqual(candidates[0]["config_index"], 1)

    def test_cleanup_candidates_without_payment_include_all_reseller_configs(self):
        candidates = self.reseller.get_banned_reseller_cleanup_candidates({
            "status": "banned",
            "last_payment_at": None,
            "configs": [
                {"username": "first", "timestamp": "2026-05-01 00:00:00", "price": 2},
                {"username": "second", "timestamp": "2026-06-01 00:00:00", "price": 3},
            ],
        })

        self.assertEqual([candidate["username"] for candidate in candidates], ["first", "second"])

    def test_cleanup_candidates_skip_already_tagged_removed_configs(self):
        candidates = self.reseller.get_banned_reseller_cleanup_candidates({
            "status": "banned",
            "last_payment_at": None,
            "configs": [
                {
                    "username": "already",
                    "timestamp": "2026-06-01 00:00:00",
                    "price": 2,
                    "removed_from_vpn": True,
                    "removal_reason": "banned_reseller_cleanup",
                },
                {"username": "new", "timestamp": "2026-06-02 00:00:00", "price": 3},
            ],
        })

        self.assertEqual([candidate["username"] for candidate in candidates], ["new"])

    def test_cleanup_deletes_success_and_missing_records_and_keeps_failures(self):
        class FakeClient:
            def __init__(self, delete_result):
                self.delete_result = delete_result
                self.deleted = []

            def delete_user(self, username):
                self.deleted.append(username)
                return self.delete_result

        class FakeMultiAPI:
            def __init__(self):
                self.success_client = FakeClient({"ok": True})
                self.failed_client = FakeClient(None)

            def find_user(self, username, preferred_server_id=None):
                if username == "deleted":
                    return self.success_client, {"username": username}
                if username == "failed":
                    return self.failed_client, {"username": username}
                return None, None

        self.write_resellers({
            "1988": {
                "status": "banned",
                "debt": 15.0,
                "last_payment_at": "2026-06-01 12:00:00",
                "configs": [
                    {"username": "paid", "timestamp": "2026-06-01 11:00:00", "price": 4.0},
                    {"username": "deleted", "timestamp": "2026-06-01 13:00:00", "price": 5.0},
                    {"username": "missing", "timestamp": "2026-06-01 14:00:00", "price": 3.0},
                    {"username": "failed", "timestamp": "2026-06-01 15:00:00", "price": 2.0},
                ],
            }
        })

        success, result = self.reseller.cleanup_banned_reseller_users("1988", FakeMultiAPI())
        saved = self.read_resellers()["1988"]

        self.assertTrue(success)
        self.assertEqual([item["username"] for item in result["deleted"]], ["deleted"])
        self.assertEqual([item["username"] for item in result["already_missing"]], ["missing"])
        self.assertEqual([item["username"] for item in result["failed"]], ["failed"])
        self.assertEqual([config["username"] for config in saved["configs"]], ["paid", "deleted", "missing", "failed"])
        tagged_by_username = {config["username"]: config for config in saved["configs"]}
        self.assertFalse(tagged_by_username["paid"].get("removed_from_vpn", False))
        self.assertTrue(tagged_by_username["deleted"]["removed_from_vpn"])
        self.assertEqual(tagged_by_username["deleted"]["removal_reason"], "banned_reseller_cleanup")
        self.assertEqual(tagged_by_username["deleted"]["removed_cleanup_status"], "deleted_from_vpn")
        self.assertEqual(
            tagged_by_username["deleted"]["removal_note"],
            "Removed during banned reseller unpaid user cleanup",
        )
        self.assertIn("removed_at", tagged_by_username["deleted"])
        self.assertTrue(tagged_by_username["missing"]["removed_from_vpn"])
        self.assertEqual(tagged_by_username["missing"]["removed_cleanup_status"], "already_missing")
        self.assertFalse(tagged_by_username["failed"].get("removed_from_vpn", False))
        self.assertEqual(saved["debt"], 7.0)
        self.assertEqual(result["remaining_debt"], 7.0)
        self.assertEqual(result["tagged_count"], 2)

    def test_cleanup_reduces_debt_no_below_zero(self):
        class MissingMultiAPI:
            def find_user(self, username, preferred_server_id=None):
                return None, None

        self.write_resellers({
            "1988": {
                "status": "banned",
                "debt": 2.0,
                "last_payment_at": None,
                "configs": [
                    {"username": "one", "timestamp": "2026-06-01 13:00:00", "price": 5.0},
                ],
            }
        })

        success, result = self.reseller.cleanup_banned_reseller_users("1988", MissingMultiAPI())
        saved = self.read_resellers()["1988"]

        self.assertTrue(success)
        self.assertEqual(saved["debt"], 0.0)
        self.assertEqual(len(saved["configs"]), 1)
        self.assertEqual(saved["configs"][0]["username"], "one")
        self.assertTrue(saved["configs"][0]["removed_from_vpn"])
        self.assertEqual(saved["configs"][0]["removed_cleanup_status"], "already_missing")
        self.assertEqual(saved["total_paid"], 0.0)
        self.assertEqual(result["remaining_debt"], 0.0)

    def test_cleanup_keeps_failed_config_value_in_debt(self):
        class FakeClient:
            def __init__(self, delete_result):
                self.delete_result = delete_result

            def delete_user(self, username):
                return self.delete_result

        class FakeMultiAPI:
            def find_user(self, username, preferred_server_id=None):
                if username == "removed":
                    return FakeClient({"ok": True}), {"username": username}
                return FakeClient(None), {"username": username}

        self.write_resellers({
            "1988": {
                "status": "banned",
                "debt": 4.0,
                "last_payment_at": None,
                "configs": [
                    {"username": "removed", "timestamp": "2026-06-01 13:00:00", "price": 5.0},
                    {"username": "failed", "timestamp": "2026-06-01 14:00:00", "price": 2.0},
                ],
            }
        })

        success, result = self.reseller.cleanup_banned_reseller_users("1988", FakeMultiAPI())
        saved = self.read_resellers()["1988"]

        self.assertTrue(success)
        self.assertEqual([config["username"] for config in saved["configs"]], ["removed", "failed"])
        self.assertTrue(saved["configs"][0]["removed_from_vpn"])
        self.assertEqual(saved["configs"][0]["removed_cleanup_status"], "deleted_from_vpn")
        self.assertFalse(saved["configs"][1].get("removed_from_vpn", False))
        self.assertEqual(saved["debt"], 2.0)
        self.assertEqual(result["remaining_debt"], 2.0)


if __name__ == "__main__":
    unittest.main()
