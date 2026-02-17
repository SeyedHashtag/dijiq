import json
import os
import re
import threading
from datetime import datetime

from utils.api_client import APIClient
from utils.command import bot
from utils.language import get_user_language
from utils.translations import get_message_text

ALERTS_FILE = '/etc/dijiq/core/scripts/telegrambot/traffic_alerts.json'
ALERT_THRESHOLDS = [80, 90]
ALERT_RESET_RATIO = 0.05

_alerts_lock = threading.Lock()


def _load_alerts():
    with _alerts_lock:
        if os.path.exists(ALERTS_FILE):
            try:
                with open(ALERTS_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}


def _save_alerts(alerts):
    with _alerts_lock:
        os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)
        with open(ALERTS_FILE, 'w') as f:
            json.dump(alerts, f, indent=2)


def _extract_telegram_id(username):
    if not username:
        return None

    match = re.match(r'^(\d+)t', username)
    if match:
        return int(match.group(1))

    match = re.match(r'^sell(\d+)t', username)
    if match:
        return int(match.group(1))

    match = re.match(r'^test(\d+)t', username)
    if match:
        return int(match.group(1))

    return None


def _should_reset_alerts(state, max_download_bytes, total_usage_bytes):
    if state.get('max_download_bytes') != max_download_bytes:
        return True

    if max_download_bytes > 0 and total_usage_bytes <= max_download_bytes * ALERT_RESET_RATIO:
        return True

    return False


def _iter_users(users):
    if isinstance(users, dict):
        for username, data in users.items():
            yield username, data
    elif isinstance(users, list):
        for data in users:
            yield data.get('username'), data


def monitor_user_traffic():
    api_client = APIClient()
    users = api_client.get_users()
    if users is None:
        return

    alerts = _load_alerts()
    changed = False

    for username, user_data in _iter_users(users):
        if not username or not user_data:
            continue

        telegram_id = _extract_telegram_id(username)
        if telegram_id is None:
            continue

        max_download_bytes = user_data.get('max_download_bytes', 0) or 0
        if max_download_bytes <= 0:
            continue

        upload_bytes = user_data.get('upload_bytes', 0) or 0
        download_bytes = user_data.get('download_bytes', 0) or 0
        total_usage_bytes = upload_bytes + download_bytes

        if total_usage_bytes <= 0:
            continue

        usage_percent = (total_usage_bytes / max_download_bytes) * 100

        state = alerts.get(username, {})
        if _should_reset_alerts(state, max_download_bytes, total_usage_bytes):
            state = {}
            changed = True

        notified = set(state.get('notified', []))

        for threshold in ALERT_THRESHOLDS:
            if usage_percent >= threshold and threshold not in notified:
                language = get_user_language(telegram_id)
                message = get_message_text(language, "traffic_quota_alert").format(
                    percent=int(usage_percent),
                    username=username,
                    used_gb=total_usage_bytes / (1024 ** 3),
                    limit_gb=max_download_bytes / (1024 ** 3),
                )
                try:
                    bot.send_message(telegram_id, message, parse_mode="Markdown")
                except Exception as e:
                    print(f"Failed to notify user {telegram_id} for {username}: {e}")
                    continue

                notified.add(threshold)
                changed = True

        if notified:
            state['notified'] = sorted(notified)
        else:
            state.pop('notified', None)

        state['max_download_bytes'] = max_download_bytes
        state['last_usage_bytes'] = total_usage_bytes
        state['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        alerts[username] = state

    if changed:
        _save_alerts(alerts)
