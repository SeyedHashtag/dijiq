import json
import os

TEST_MODE_FILE = '/etc/hysteria/core/scripts/telegrambot/test_mode.json'

def load_test_mode():
    try:
        if os.path.exists(TEST_MODE_FILE):
            with open(TEST_MODE_FILE, 'r') as f:
                data = json.load(f)
                return data.get('enabled', False)
    except Exception:
        pass
    return False

def save_test_mode(enabled):
    os.makedirs(os.path.dirname(TEST_MODE_FILE), exist_ok=True)
    with open(TEST_MODE_FILE, 'w') as f:
        json.dump({'enabled': enabled}, f)

def toggle_test_mode():
    current = load_test_mode()
    save_test_mode(not current)
    return not current 
