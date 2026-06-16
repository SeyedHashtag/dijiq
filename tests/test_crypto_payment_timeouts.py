import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "payments.py"
)


class FakeResponse:
    status_code = 200
    text = "ok"

    def json(self):
        return {"result": {"status": "pending"}}


def load_payments_module():
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)
    spec = importlib.util.spec_from_file_location("payments_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CryptoPaymentTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.original_env = {
            key: os.environ.get(key)
            for key in ("CRYPTO_MERCHANT_ID", "CRYPTO_API_KEY", "CRYPTO_REQUEST_TIMEOUT_SECONDS")
        }
        os.environ["CRYPTO_MERCHANT_ID"] = "merchant"
        os.environ["CRYPTO_API_KEY"] = "api-key"
        os.environ["CRYPTO_REQUEST_TIMEOUT_SECONDS"] = "7"
        self.payments = load_payments_module()

    def tearDown(self):
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_create_payment_uses_configured_timeout(self):
        calls = []
        self.payments.requests.post = lambda *args, **kwargs: calls.append((args, kwargs)) or FakeResponse()

        result = self.payments.CryptoPayment().create_payment(12.5, 40, 123)

        self.assertEqual(result, {"result": {"status": "pending"}})
        self.assertEqual(calls[0][1]["timeout"], 7.0)

    def test_check_payment_status_uses_configured_timeout(self):
        calls = []
        self.payments.requests.post = lambda *args, **kwargs: calls.append((args, kwargs)) or FakeResponse()

        result = self.payments.CryptoPayment().check_payment_status("payment-id")

        self.assertEqual(result, {"result": {"status": "pending"}})
        self.assertEqual(calls[0][1]["timeout"], 7.0)


if __name__ == "__main__":
    unittest.main()
