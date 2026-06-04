import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "receipt_checker.py"
)


def load_receipt_checker():
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub
    spec = importlib.util.spec_from_file_location("receipt_checker_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ReceiptCheckerShareTests(unittest.TestCase):
    def setUp(self):
        self.module = load_receipt_checker()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.module.CHECKER_SETTLEMENTS_FILE = str(Path(self.tmp_dir.name) / "checker_settlements.json")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_share_percent_defaults_and_validation(self):
        parse = self.module.parse_receipt_checker_share_percent

        self.assertEqual(parse(None), 10.0)
        self.assertEqual(parse("invalid"), 10.0)
        self.assertEqual(parse("-1"), 10.0)
        self.assertEqual(parse("101"), 10.0)
        self.assertEqual(parse("12.345"), 12.35)

    def test_checker_stats_include_share_paid_and_unpaid(self):
        payments = {
            "approved-new": {
                "routed_to_checker": True,
                "receipt_checker_user_id": 42,
                "receipt_type": "regular",
                "status": "completed",
                "price": 100,
                "checker_share_amount": 12.5,
                "converted_amount": 5800000,
                "converted_currency": "Tomans",
                "reviewed_at": "2026-06-04 10:00:00",
                "reviewed_action": "approve",
                "reviewed_by_user_id": 42,
            },
            "approved-legacy": {
                "routed_to_checker": True,
                "receipt_checker_user_id": 42,
                "receipt_type": "settlement",
                "status": "completed",
                "price": 50,
                "reviewed_at": "2026-06-04 11:00:00",
                "reviewed_action": "approve",
                "reviewed_by_user_id": 100,
            },
            "pending": {
                "routed_to_checker": True,
                "receipt_checker_user_id": 42,
                "receipt_type": "regular",
                "status": "pending_approval",
            },
            "rejected": {
                "routed_to_checker": True,
                "receipt_checker_user_id": 42,
                "receipt_type": "regular",
                "status": "rejected",
            },
            "other-checker": {
                "routed_to_checker": True,
                "receipt_checker_user_id": 77,
                "receipt_type": "regular",
                "status": "completed",
                "price": 1000,
            },
            "not-routed": {
                "routed_to_checker": False,
                "receipt_checker_user_id": 42,
                "receipt_type": "regular",
                "status": "completed",
                "price": 1000,
            },
        }
        self.module.save_checker_settlements([
            {"checker_user_id": 42, "amount": 7.0},
            {"checker_user_id": 77, "amount": 100.0},
        ])

        with patch.dict(os.environ, {
            "RECEIPT_CHECKER_USER_ID": "42",
            "RECEIPT_CHECKER_TYPES": "regular,settlement",
            "RECEIPT_CHECKER_SHARE_PERCENT": "10",
        }, clear=False):
            stats = self.module.build_receipt_checker_stats(payments)

        self.assertEqual(stats["approved_total"], 150.0)
        self.assertEqual(stats["owed_total"], 17.5)
        self.assertEqual(stats["paid_total"], 7.0)
        self.assertEqual(stats["unpaid_total"], 10.5)
        self.assertEqual(stats["legacy_estimated_count"], 1)
        self.assertEqual(stats["types"]["regular"]["pending"], 1)
        self.assertEqual(stats["types"]["regular"]["rejected"], 1)
        self.assertEqual(stats["types"]["settlement"]["approved"], 1)
        self.assertEqual(stats["converted_approved_total"], 5800000.0)
        self.assertEqual(stats["latest_review"]["payment_id"], "approved-legacy")

    def test_add_checker_settlement_checkpoint_audit(self):
        snapshot = {
            "share_percent": 10.0,
            "approved_total": 200.0,
            "owed_total": 20.0,
            "paid_total": 5.0,
            "unpaid_total": 15.0,
        }

        checkpoint = self.module.add_checker_settlement(8, 123, snapshot, checker_id=42)
        settlements = self.module.get_checker_settlements(42)

        self.assertEqual(checkpoint["amount"], 8.0)
        self.assertEqual(checkpoint["admin_user_id"], 123)
        self.assertEqual(checkpoint["checker_user_id"], 42)
        self.assertEqual(checkpoint["paid_before"], 5.0)
        self.assertEqual(checkpoint["unpaid_before"], 15.0)
        self.assertEqual(checkpoint["unpaid_after"], 7.0)
        self.assertEqual(len(settlements), 1)


if __name__ == "__main__":
    unittest.main()
