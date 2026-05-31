import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def shell_function_body(script_text, function_name):
    start_marker = f"{function_name}() {{"
    start = script_text.index(start_marker)
    next_function = re.search(r"\n[a-zA-Z_][a-zA-Z0-9_]*\(\) \{", script_text[start + len(start_marker):])
    if not next_function:
        return script_text[start:]
    end = start + len(start_marker) + next_function.start()
    return script_text[start:end]


class TelegramEnvPreservationTests(unittest.TestCase):
    def test_menu_reconfigure_and_add_server_do_not_stop_before_start(self):
        menu_text = (REPO_ROOT / "menu.sh").read_text()

        configure_body = shell_function_body(menu_text, "configure_telegram_bot")
        add_server_body = shell_function_body(menu_text, "add_telegram_vpn_server")

        self.assertNotIn("telegram -a stop", configure_body)
        self.assertNotIn("telegram -a stop", add_server_body)
        self.assertIn("telegram -a start", configure_body)
        self.assertIn("telegram -a start", add_server_body)

    def test_runbot_stop_preserves_telegram_env_file(self):
        runbot_text = (REPO_ROOT / "core" / "scripts" / "telegrambot" / "runbot.sh").read_text()
        stop_body = shell_function_body(runbot_text, "stop_service")

        self.assertNotIn("rm -f", stop_body)
        self.assertNotIn("/etc/dijiq/core/scripts/telegrambot/.env", stop_body)
        self.assertIn("Configuration preserved", stop_body)


if __name__ == "__main__":
    unittest.main()
