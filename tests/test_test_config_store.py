import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path


STORE_PATH = (
    Path(__file__).resolve().parents[1]
    / "core"
    / "scripts"
    / "telegrambot"
    / "utils"
    / "test_config_store.py"
)


spec = importlib.util.spec_from_file_location("test_config_store_under_test", STORE_PATH)
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class TestConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.path = Path(self.tmpdir.name) / "test_configs.json"

    def test_concurrent_per_user_updates_preserve_every_record(self):
        threads = []

        def add_user(user_id):
            def mutate(configs):
                configs[str(user_id)] = {"telegram_id": user_id, "username": f"t{user_id}"}
            store.update_test_configs(str(self.path), mutate)

        for user_id in range(100, 125):
            thread = threading.Thread(target=add_user, args=(user_id,))
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()

        configs = store.load_test_configs(str(self.path))
        self.assertEqual(len(configs), 25)
        self.assertEqual(configs["100"]["username"], "t100")
        self.assertEqual(configs["124"]["username"], "t124")

    def test_malformed_json_fails_closed_without_overwrite(self):
        malformed = '{"123": '
        self.path.write_text(malformed, encoding="utf-8")

        with self.assertRaises(store.TestConfigStoreError):
            store.load_test_configs(str(self.path))
        with self.assertRaises(store.TestConfigStoreError):
            store.update_test_configs(str(self.path), lambda configs: configs.update({"456": {}}))

        self.assertEqual(self.path.read_text(encoding="utf-8"), malformed)

    def test_recovered_history_is_deduplicated_and_current_record_is_preserved(self):
        self.path.write_text(json.dumps({
            "123": {
                "telegram_id": 123,
                "username": "t123a",
                "server_id": "s2",
                "used_at": "2026-06-01 12:00:00",
            }
        }), encoding="utf-8")
        recovered = {
            "telegram_id": 123,
            "used_at": "2026-05-01 12:00:00",
            "recovered_at": "2026-06-09 12:00:00",
            "history_record": {"username": "t123", "server_id": "s1"},
        }

        first = store.upsert_recovered_test_users(str(self.path), [recovered])
        second = store.upsert_recovered_test_users(str(self.path), [recovered])

        entry = store.load_test_configs(str(self.path))["123"]
        self.assertEqual(first, {"created": 0, "history_added": 1})
        self.assertEqual(second, {"created": 0, "history_added": 0})
        self.assertEqual(entry["username"], "t123a")
        self.assertEqual(entry["server_id"], "s2")
        self.assertEqual(entry["used_at"], "2026-06-01 12:00:00")
        self.assertEqual(entry["historical_configs"], [{"username": "t123", "server_id": "s1"}])

    def test_atomic_write_leaves_no_temporary_files(self):
        store.save_test_configs(str(self.path), {"123": {"telegram_id": 123}})

        self.assertEqual(store.load_test_configs(str(self.path))["123"]["telegram_id"], 123)
        self.assertEqual(list(Path(self.tmpdir.name).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
