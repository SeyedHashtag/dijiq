import json
import os
from datetime import datetime

TEST_CONFIGS_FILE = '/etc/hysteria/core/scripts/telegrambot/test_configs.json'

def load_test_configs():
    try:
        if os.path.exists(TEST_CONFIGS_FILE):
            with open(TEST_CONFIGS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_test_configs(configs):
    os.makedirs(os.path.dirname(TEST_CONFIGS_FILE), exist_ok=True)
    with open(TEST_CONFIGS_FILE, 'w') as f:
        json.dump(configs, f, indent=4)

def has_used_test_config(user_id):
    configs = load_test_configs()
    return str(user_id) in configs

def mark_test_config_used(user_id):
    configs = load_test_configs()
    configs[str(user_id)] = {
        'used_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    save_test_configs(configs) 
