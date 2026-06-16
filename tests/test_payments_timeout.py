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


def load_payments_module():
    if "dotenv" not in sys.modules:
        dotenv_stub = types.ModuleType("dotenv")
        dotenv_stub.load_dotenv = lambda *args, **kwargs: None
        sys.modules["dotenv"] = dotenv_stub
    spec = importlib.util.spec_from_file_location("payments_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CryptoPaymentTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.original_env = {
            "CRYPTO_MERCHANT_ID": os.environ.get("CRYPTO_MERCHANT_ID"),
            "CRYPTO_API_KEY": os.environ.get("CRYPTO_API_KEY"),
            "DIJIQ_CRYPTO_API_TIMEOUT_SECONDS": os.environ.get("DIJIQ_CRYPTO_API_TIMEOUT_SECONDS"),
        }

    def tearDown(self):
        for name, value in self.original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_create_and_check_payment_use_crypto_timeout_env(self):
        payments = load_payments_module()
        os.environ["CRYPTO_MERCHANT_ID"] = "merchant"
        os.environ["CRYPTO_API_KEY"] = "secret"
        os.environ["DIJIQ_CRYPTO_API_TIMEOUT_SECONDS"] = "4.5"
        calls = []

        class Response:
            status_code = 200

            def json(self):
                return {"result": {"status": "pending"}}

        def post(url, **kwargs):
            calls.append((url, kwargs))
            return Response()

        original_post = payments.requests.post
        payments.requests.post = post
        try:
            payment = payments.CryptoPayment()
            self.assertIn("result", payment.create_payment(10, "40", 123))
            self.assertIn("result", payment.check_payment_status("payment-id"))
        finally:
            payments.requests.post = original_post

        self.assertEqual(calls[0][1]["timeout"], 4.5)
        self.assertEqual(calls[1][1]["timeout"], 4.5)


if __name__ == "__main__":
    unittest.main()
