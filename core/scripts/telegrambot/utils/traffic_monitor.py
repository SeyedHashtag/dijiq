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
RESELLERS_FILE = '/etc/dijiq/core/scripts/telegrambot/resellers.json'
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


def _extract_reseller_id(username):
    """Extract the reseller's Telegram ID from a reseller-created config username.

    Reseller configs use the format: reseller{reseller_id}t{timestamp}{chosen_username}
    Returns the reseller's integer Telegram ID, or None if the username is not a
    reseller-created config.
    """
    if not username:
        return None
    match = re.match(r'^reseller(\d+)t', username)
    if match:
        return int(match.group(1))
    return None


def _get_reseller_total_days(reseller_id, username):
    """Look up the total plan days for a reseller client config.

    Searches the reseller's configs list in resellers.json by username.
    Returns the integer total days, or None if not found.
    """
    try:
        if not os.path.exists(RESELLERS_FILE):
            return None
        with open(RESELLERS_FILE, 'r') as f:
            resellers = json.load(f)
        record = resellers.get(str(reseller_id))
        if not record:
            return None
        for cfg in record.get('configs', []):
            if cfg.get('username') == username:
                try:
                    return int(cfg['days'])
                except (KeyError, TypeError, ValueError):
                    return None
    except Exception:
        pass
    return None


def _should_reset_days_alerts(state, total_days, expiration_days):
    """Reset day-based alerts when the plan is renewed (total_days reference changes)."""
    if state.get('total_days') != total_days:
        return True
    # Reset if expiration_days has gone back up to near the original total (plan renewed)
    if total_days > 0 and expiration_days >= total_days * (1 - ALERT_RESET_RATIO):
        return True
    return False


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

        # ── Regular user GB alerts ──────────────────────────────────────────
        telegram_id = _extract_telegram_id(username)
        if telegram_id is not None:
            max_download_bytes = user_data.get('max_download_bytes', 0) or 0
            if max_download_bytes > 0:
                upload_bytes = user_data.get('upload_bytes', 0) or 0
                download_bytes = user_data.get('download_bytes', 0) or 0
                total_usage_bytes = upload_bytes + download_bytes

                if total_usage_bytes > 0:
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

        # ── Reseller client alerts (GB + days) ─────────────────────────────
        reseller_id = _extract_reseller_id(username)
        if reseller_id is None:
            continue

        language = get_user_language(reseller_id)
        state = alerts.get(username, {})

        # — GB alert for reseller client —
        max_download_bytes = user_data.get('max_download_bytes', 0) or 0
        if max_download_bytes > 0:
            upload_bytes = user_data.get('upload_bytes', 0) or 0
            download_bytes = user_data.get('download_bytes', 0) or 0
            total_usage_bytes = upload_bytes + download_bytes

            if total_usage_bytes > 0:
                usage_percent = (total_usage_bytes / max_download_bytes) * 100

                if _should_reset_alerts(state, max_download_bytes, total_usage_bytes):
                    # Only reset GB-related keys, keep days keys intact
                    state.pop('gb_notified', None)
                    state.pop('max_download_bytes', None)
                    state.pop('last_usage_bytes', None)
                    changed = True

                gb_notified = set(state.get('gb_notified', []))

                for threshold in ALERT_THRESHOLDS:
                    if usage_percent >= threshold and threshold not in gb_notified:
                        message = get_message_text(language, "reseller_client_traffic_alert").format(
                            percent=int(usage_percent),
                            username=username,
                            used_gb=total_usage_bytes / (1024 ** 3),
                            limit_gb=max_download_bytes / (1024 ** 3),
                        )
                        try:
                            bot.send_message(reseller_id, message, parse_mode="Markdown")
                        except Exception as e:
                            print(f"Failed to notify reseller {reseller_id} for client {username} (GB): {e}")
                            continue

                        gb_notified.add(threshold)
                        changed = True

                state['gb_notified'] = sorted(gb_notified)
                state['max_download_bytes'] = max_download_bytes
                state['last_usage_bytes'] = total_usage_bytes

        # — Days alert for reseller client —
        expiration_days = user_data.get('expiration_days', None)
        if expiration_days is not None:
            try:
                expiration_days = int(expiration_days)
            except (TypeError, ValueError):
                expiration_days = None

        if expiration_days is not None and expiration_days >= 0:
            total_days = _get_reseller_total_days(reseller_id, username)
            if total_days and total_days > 0:
                days_used = total_days - expiration_days
                days_percent = (days_used / total_days) * 100

                if _should_reset_days_alerts(state, total_days, expiration_days):
                    state.pop('days_notified', None)
                    state.pop('total_days', None)
                    changed = True

                days_notified = set(state.get('days_notified', []))

                for threshold in ALERT_THRESHOLDS:
                    if days_percent >= threshold and threshold not in days_notified:
                        message = get_message_text(language, "reseller_client_days_alert").format(
                            percent=int(days_percent),
                            username=username,
                            days_used=max(0, days_used),
                            total_days=total_days,
                            days_remaining=expiration_days,
                        )
                        try:
                            bot.send_message(reseller_id, message, parse_mode="Markdown")
                        except Exception as e:
                            print(f"Failed to notify reseller {reseller_id} for client {username} (days): {e}")
                            continue

                        days_notified.add(threshold)
                        changed = True

                state['days_notified'] = sorted(days_notified)
                state['total_days'] = total_days

        state['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        alerts[username] = state

    if changed:
        _save_alerts(alerts)
