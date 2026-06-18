import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "payment_records.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("payment_records_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PaymentRecordsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.path = Path(self.tmpdir.name) / "payments.json"
        self.payment_records = load_module()
        self.payment_records.PAYMENTS_FILE = str(self.path)

    def write_payments(self, payments):
        self.path.write_text(json.dumps(payments), encoding="utf-8")

    def read_payments(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_complete_payment_record_updates_fields_status_and_history_atomically(self):
        self.write_payments({
            "pay-1": {
                "status": "processing",
                "user_id": 1988,
                "updates": [{"status": "processing", "previous_status": "pending"}],
            }
        })

        completed = self.payment_records.complete_payment_record(
            "pay-1",
            {"username": "s1988a", "server_id": "server2"},
        )

        self.assertTrue(completed)
        record = self.read_payments()["pay-1"]
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["username"], "s1988a")
        self.assertEqual(record["server_id"], "server2")
        self.assertIn("updated_at", record)
        self.assertEqual(record["updates"][-1]["status"], "completed")
        self.assertEqual(record["updates"][-1]["previous_status"], "processing")
        self.assertIn("timestamp", record["updates"][-1])

    def test_complete_payment_record_returns_false_for_missing_or_invalid_records(self):
        self.write_payments({"pay-1": {"status": "processing", "updates": []}})

        self.assertFalse(self.payment_records.complete_payment_record("missing", {"username": "s1"}))
        self.assertFalse(self.payment_records.complete_payment_record("pay-1", None))

        record = self.read_payments()["pay-1"]
        self.assertEqual(record, {"status": "processing", "updates": []})

    def test_update_payment_status_creates_missing_legacy_updates_list(self):
        self.write_payments({"pay-1": {"status": "pending"}})

        self.assertTrue(self.payment_records.update_payment_status("pay-1", "expired"))

        record = self.read_payments()["pay-1"]
        self.assertEqual(record["status"], "expired")
        self.assertEqual(record["updates"][-1]["previous_status"], "pending")
        self.assertEqual(record["updates"][-1]["status"], "expired")


if __name__ == "__main__":
    unittest.main()
