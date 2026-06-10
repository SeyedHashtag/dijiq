import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def repo_text_files():
    for path in REPO_ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        if path.suffix in {".py", ".sh", ".md"} or path.name in {"upgrade.sh", "README.md"}:
            yield path


def referenced_telegram_json_files():
    pattern = re.compile(r"['\"](/etc/dijiq/core/scripts/telegrambot/[^'\"]+\.json)['\"]")
    files = set()
    for path in repo_text_files():
        text = path.read_text(errors="ignore")
        files.update(pattern.findall(text))
    return files


def shell_array_values(script_path, array_name):
    text = script_path.read_text()
    match = re.search(rf"{array_name}=\(\s*(.*?)\s*\)", text, flags=re.DOTALL)
    if not match:
        return set()
    return set(re.findall(r'"([^"]+)"', match.group(1)))


class TelegramJsonPreservationTests(unittest.TestCase):
    def test_runtime_telegram_json_files_are_preserved_by_upgrade_backup_and_restore(self):
        expected_absolute = referenced_telegram_json_files()
        expected_relative = {
            path[len("/etc/dijiq/"):]
            for path in expected_absolute
        }

        self.assertTrue(expected_absolute)

        upgrade_files = shell_array_values(REPO_ROOT / "upgrade.sh", "FILES")
        backup_files = shell_array_values(REPO_ROOT / "core/scripts/dijiq/backup.sh", "FILES_TO_BACKUP")
        restore_files = shell_array_values(REPO_ROOT / "core/scripts/dijiq/restore.sh", "telegram_state_files")

        self.assertFalse(expected_absolute - upgrade_files)
        self.assertFalse(expected_absolute - backup_files)
        self.assertFalse(expected_relative - restore_files)


if __name__ == "__main__":
    unittest.main()
