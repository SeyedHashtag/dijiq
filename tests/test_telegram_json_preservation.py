import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE_SCRIPTS = {
    REPO_ROOT / "upgrade.sh",
    REPO_ROOT / "core/scripts/dijiq/backup.sh",
    REPO_ROOT / "core/scripts/dijiq/restore.sh",
}


def repo_text_files():
    for path in REPO_ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        if "tests" in path.parts:
            continue
        if path in MAINTENANCE_SCRIPTS:
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


class TelegramJsonPreservationTests(unittest.TestCase):
    def test_runtime_telegram_json_files_are_preserved_by_directory_patterns(self):
        referenced_json_files = referenced_telegram_json_files()
        self.assertTrue(referenced_json_files)

        upgrade_text = (REPO_ROOT / "upgrade.sh").read_text()
        backup_text = (REPO_ROOT / "core/scripts/dijiq/backup.sh").read_text()
        restore_text = (REPO_ROOT / "core/scripts/dijiq/restore.sh").read_text()

        for script_text in (upgrade_text, backup_text):
            self.assertIn("/etc/dijiq/*.env", script_text)
            self.assertIn("/etc/dijiq/*.json", script_text)
            self.assertIn("/etc/dijiq/core/scripts/telegrambot/*.env", script_text)
            self.assertIn("/etc/dijiq/core/scripts/telegrambot/*.json", script_text)

        self.assertIn('restore_root_state_files "$RESTORE_DIR"', restore_text)
        self.assertIn('restore_telegram_state_files "$RESTORE_DIR/core/scripts/telegrambot"', restore_text)
        self.assertIn('restore_telegram_state_files "$RESTORE_DIR"', restore_text)

        maintenance_text = "\n".join((upgrade_text, backup_text, restore_text))
        for path in referenced_json_files:
            self.assertNotIn(path, maintenance_text)
            self.assertNotIn(path[len("/etc/dijiq/"):], maintenance_text)


if __name__ == "__main__":
    unittest.main()
