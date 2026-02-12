import json
import os
import threading
from datetime import datetime, timedelta

RESELLERS_FILE = '/etc/dijiq/core/scripts/telegrambot/resellers.json'
reseller_lock = threading.RLock()


def _safe_float_env(key, default):
    try:
        return float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return float(default)


DEBT_WARNING_THRESHOLD = _safe_float_env('RESELLER_DEBT_WARNING_THRESHOLD', 20.0)
DEBT_SUSPEND_THRESHOLD = _safe_float_env('RESELLER_DEBT_SUSPEND_THRESHOLD', 50.0)
DEBT_REMINDER_INTERVAL_HOURS = max(1.0, _safe_float_env('RESELLER_DEBT_REMINDER_INTERVAL_HOURS', 24.0))


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return None


def _compute_debt_state(debt):
    debt_amount = _safe_float(debt, 0.0)
    if debt_amount >= DEBT_SUSPEND_THRESHOLD:
        return 'suspended'
    if debt_amount >= DEBT_WARNING_THRESHOLD:
        return 'warning'
    return 'active'


def _ensure_reseller_defaults(record):
    data = dict(record or {})
    data['status'] = data.get('status', 'pending')
    data.setdefault('telegram_username', None)
    debt = _safe_float(data.get('debt', 0.0))
    data['debt'] = debt
    data.setdefault('configs', [])
    data.setdefault('created_at', _now_str())
    data.setdefault('last_payment_at', None)
    data.setdefault('debt_since', None)
    data.setdefault('debt_last_reminded_at', None)
    data.setdefault('debt_last_admin_alert_level', 'none')
    data.setdefault('debt_last_admin_alert_at', None)

    if debt > 0 and not data.get('debt_since'):
        data['debt_since'] = _now_str()
    if debt <= 0:
        data['debt_since'] = None
        data['debt_last_reminded_at'] = None
        data['debt_last_admin_alert_level'] = 'none'

    data['debt_state'] = _compute_debt_state(debt)
    return data


def load_resellers():
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}


def save_resellers(resellers):
    with reseller_lock:
        os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
        with open(RESELLERS_FILE, 'w') as f:
            json.dump(resellers, f, indent=4)


def get_reseller_data(user_id):
    resellers = load_resellers()
    data = resellers.get(str(user_id))
    if not data:
        return None
    return _ensure_reseller_defaults(data)


def get_all_resellers():
    resellers = load_resellers()
    normalized = {}
    for rid, data in resellers.items():
        normalized[str(rid)] = _ensure_reseller_defaults(data)
    return normalized


def update_reseller_status(user_id, status, telegram_username=None):
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                resellers = {}
        except Exception:
            resellers = {}

        current = _ensure_reseller_defaults(resellers.get(user_id, {}))
        current['status'] = status
        if telegram_username is not None:
            username_clean = str(telegram_username).strip().lstrip('@')
            current['telegram_username'] = username_clean or None
        resellers[user_id] = _ensure_reseller_defaults(current)

        os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
        with open(RESELLERS_FILE, 'w') as f:
            json.dump(resellers, f, indent=4)
        return True


def add_reseller_debt(user_id, amount, config_data):
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                return False
        except Exception:
            return False

        if user_id in resellers:
            current = _ensure_reseller_defaults(resellers[user_id])
            before = _safe_float(current.get('debt', 0.0))
            amount_value = _safe_float(amount, 0.0)
            current['debt'] = before + amount_value

            if 'configs' not in current:
                current['configs'] = []

            config_data['timestamp'] = _now_str()
            current['configs'].append(config_data)
            if before <= 0 and current['debt'] > 0:
                current['debt_since'] = _now_str()

            current = _ensure_reseller_defaults(current)
            resellers[user_id] = current

            os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
            with open(RESELLERS_FILE, 'w') as f:
                json.dump(resellers, f, indent=4)
            return True
        return False


def clear_reseller_debt(user_id):
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                return False
        except Exception:
            return False

        if user_id in resellers:
            current = _ensure_reseller_defaults(resellers[user_id])
            current['debt'] = 0.0
            current = _ensure_reseller_defaults(current)
            resellers[user_id] = current
            os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
            with open(RESELLERS_FILE, 'w') as f:
                json.dump(resellers, f, indent=4)
            return True
        return False


def set_reseller_debt(user_id, amount):
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                return False
        except Exception:
            return False

        if user_id in resellers:
            current = _ensure_reseller_defaults(resellers[user_id])
            previous_debt = _safe_float(current.get('debt', 0.0))
            new_debt = _safe_float(amount, 0.0)
            current['debt'] = max(0.0, new_debt)

            if previous_debt <= 0 and current['debt'] > 0:
                current['debt_since'] = _now_str()
            if current['debt'] <= 0:
                current['debt_since'] = None

            current = _ensure_reseller_defaults(current)
            resellers[user_id] = current
            os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
            with open(RESELLERS_FILE, 'w') as f:
                json.dump(resellers, f, indent=4)
            return True
        return False


def apply_reseller_payment(user_id, amount):
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                return False, None
        except Exception:
            return False, None

        if user_id not in resellers:
            return False, None

        try:
            paid_amount = float(amount)
        except (TypeError, ValueError):
            return False, None

        current = _ensure_reseller_defaults(resellers[user_id])
        current_debt = _safe_float(current.get('debt', 0.0))
        new_debt = max(0.0, current_debt - paid_amount)
        current['debt'] = new_debt

        if paid_amount > 0:
            current['last_payment_at'] = _now_str()
        if new_debt <= 0:
            current['debt_since'] = None

        current = _ensure_reseller_defaults(current)
        resellers[user_id] = current

        os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
        with open(RESELLERS_FILE, 'w') as f:
            json.dump(resellers, f, indent=4)
        return True, new_debt


def evaluate_reseller_debt_policies():
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                return []
        except Exception:
            return []

        now = datetime.now()
        reminder_delta = timedelta(hours=DEBT_REMINDER_INTERVAL_HOURS)
        events = []
        changed = False

        for user_id, record in resellers.items():
            current = _ensure_reseller_defaults(record)
            debt = _safe_float(current.get('debt', 0.0))
            debt_state = current.get('debt_state', 'active')

            if debt > 0 and not current.get('debt_since'):
                current['debt_since'] = _now_str()

            remind_due = False
            if debt > 0 and debt_state in {'warning', 'suspended'} and current.get('status') == 'approved':
                last_reminded_at = _parse_time(current.get('debt_last_reminded_at'))
                if not last_reminded_at or (now - last_reminded_at) >= reminder_delta:
                    remind_due = True
                    current['debt_last_reminded_at'] = _now_str()
                    changed = True

            alert_level = 'none'
            if debt_state == 'warning' and debt > 0:
                alert_level = 'warning'
            elif debt_state == 'suspended' and debt > 0:
                alert_level = 'suspended'

            admin_alert_due = False
            previous_alert_level = str(current.get('debt_last_admin_alert_level', 'none'))
            if alert_level != previous_alert_level:
                if alert_level in {'warning', 'suspended'} and current.get('status') == 'approved':
                    admin_alert_due = True
                current['debt_last_admin_alert_level'] = alert_level
                current['debt_last_admin_alert_at'] = _now_str()
                changed = True

            if debt <= 0 and current.get('status') == 'approved' and previous_alert_level != 'none':
                current['debt_last_admin_alert_level'] = 'none'
                current['debt_last_admin_alert_at'] = _now_str()
                changed = True

            if current != record:
                changed = True
                resellers[user_id] = current

            if remind_due or admin_alert_due:
                debt_since = _parse_time(current.get('debt_since'))
                debt_age_days = 0
                if debt_since:
                    debt_age_days = max(0, (now - debt_since).days)

                unlock_amount = 0.0
                if debt_state == 'suspended':
                    unlock_amount = max(0.0, debt - DEBT_WARNING_THRESHOLD)

                events.append({
                    'user_id': str(user_id),
                    'debt': debt,
                    'debt_state': debt_state,
                    'status': current.get('status', 'pending'),
                    'debt_age_days': debt_age_days,
                    'debt_since': current.get('debt_since'),
                    'last_payment_at': current.get('last_payment_at'),
                    'unlock_amount': unlock_amount,
                    'notify_user': remind_due,
                    'notify_admin': admin_alert_due,
                })

        if changed:
            os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
            with open(RESELLERS_FILE, 'w') as f:
                json.dump(resellers, f, indent=4)

        return events
