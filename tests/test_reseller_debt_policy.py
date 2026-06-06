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


if __name__ == "__main__":
    unittest.main()
