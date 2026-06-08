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
DEBT_SETTLEMENT_THRESHOLD = _safe_float_env('RESELLER_SETTLEMENT_THRESHOLD', 1.0)
DEBT_REMINDER_INTERVAL_HOURS = max(1.0, _safe_float_env('RESELLER_DEBT_REMINDER_INTERVAL_HOURS', 24.0))
DEBT_SUSPEND_DEADLINE_HOURS = max(1.0, _safe_float_env('RESELLER_DEBT_SUSPEND_DEADLINE_HOURS', 48.0))
DEBT_BAN_DEADLINE_HOURS = max(1.0, _safe_float_env('RESELLER_DEBT_BAN_DEADLINE_HOURS', 72.0))
UNBAN_GRACE_BAN_DEADLINE_HOURS = max(1.0, _safe_float_env('RESELLER_UNBAN_GRACE_BAN_DEADLINE_HOURS', 24.0))
SUSPENDED_REASON_DEBT = 'debt'
SUSPENDED_REASON_UNBAN_GRACE = 'unban_grace'
RESELLER_TRUST_START_LIMIT = 5.0
RESELLER_TRUST_LIMIT_STEP = 5.0
RESELLER_TRUST_PAID_STEP = 10.0
RESELLER_TRUST_MAX_LIMIT = 30.0


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _reseller_config_total(record):
    configs = (record or {}).get('configs', [])
    if not isinstance(configs, list):
        return 0.0
    return sum(
        _safe_float(config.get('price', 0.0))
        for config in configs
        if isinstance(config, dict)
    )


def get_reseller_total_paid(record):
    data = record or {}
    if 'total_paid' in data:
        return max(0.0, _safe_float(data.get('total_paid', 0.0)))
    debt = _safe_float(data.get('debt', 0.0))
    return max(0.0, _reseller_config_total(data) - debt)


def get_reseller_trust_limit(total_paid):
    paid_amount = max(0.0, _safe_float(total_paid, 0.0))
    paid_steps = int(paid_amount // RESELLER_TRUST_PAID_STEP)
    limit = RESELLER_TRUST_START_LIMIT + (paid_steps * RESELLER_TRUST_LIMIT_STEP)
    return min(RESELLER_TRUST_MAX_LIMIT, limit)


def get_reseller_available_credit(record):
    data = record or {}
    debt = _safe_float(data.get('debt', 0.0))
    trust_limit = get_reseller_trust_limit(get_reseller_total_paid(data))
    return max(0.0, trust_limit - debt)


def can_reseller_add_debt(record, amount):
    data = record or {}
    debt = _safe_float(data.get('debt', 0.0))
    amount_value = _safe_float(amount, 0.0)
    trust_limit = get_reseller_trust_limit(get_reseller_total_paid(data))
    return debt + amount_value <= trust_limit, trust_limit, max(0.0, trust_limit - debt)


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


def get_reseller_unlock_amount(debt):
    return max(0.0, _safe_float(debt, 0.0))


def validate_reseller_manual_payment_amount(amount, current_debt):
    try:
        amount_value = round(float(amount), 2)
    except (TypeError, ValueError):
        return False, 0.0, 'invalid'

    debt_value = round(max(0.0, _safe_float(current_debt, 0.0)), 2)
    if amount_value <= 0:
        return False, amount_value, 'invalid'
    if amount_value > debt_value:
        return False, amount_value, 'over_debt'
    return True, amount_value, None


def _ensure_reseller_defaults(record):
    data = dict(record or {})
    data['status'] = data.get('status', 'pending')
    data.setdefault('telegram_username', None)
    data.setdefault('suspended_reason', None)
    data.setdefault('suspended_at', None)
    debt = _safe_float(data.get('debt', 0.0))
    data['debt'] = debt
    data.setdefault('configs', [])
    total_paid = get_reseller_total_paid(data)
    data['total_paid'] = total_paid
    data['trust_limit'] = get_reseller_trust_limit(total_paid)
    data.setdefault('created_at', _now_str())
    data.setdefault('last_payment_at', None)
    data.setdefault('debt_since', None)
    data.setdefault('debt_last_reminded_at', None)
    data.setdefault('debt_last_admin_alert_level', 'none')
    data.setdefault('debt_last_admin_alert_at', None)

    if debt >= DEBT_SETTLEMENT_THRESHOLD and not data.get('debt_since'):
        data['debt_since'] = _now_str()
    if debt < DEBT_SETTLEMENT_THRESHOLD:
        data['debt_since'] = None
        data['debt_last_reminded_at'] = None
        data['debt_last_admin_alert_level'] = 'none'

    data['debt_state'] = _compute_debt_state(debt)
    return data


def _restore_auto_suspended_if_debt_cleared(data):
    if (
        _safe_float(data.get('debt', 0.0)) < DEBT_SETTLEMENT_THRESHOLD
        and data.get('status') == 'suspended'
        and data.get('suspended_reason') == SUSPENDED_REASON_DEBT
    ):
        data['status'] = 'approved'
        data['suspended_reason'] = None
        data['suspended_at'] = None
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


def update_reseller_status(user_id, status, telegram_username=None, suspended_reason=None):
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
        previous_status = current.get('status')
        previous_reason = current.get('suspended_reason')
        current['status'] = status
        if status == 'suspended':
            current['suspended_reason'] = suspended_reason
            if previous_status != 'suspended' or previous_reason != suspended_reason or not current.get('suspended_at'):
                current['suspended_at'] = _now_str()
        else:
            current['suspended_reason'] = None
            current['suspended_at'] = None
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
            if before < DEBT_SETTLEMENT_THRESHOLD and current['debt'] >= DEBT_SETTLEMENT_THRESHOLD:
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
            current = _restore_auto_suspended_if_debt_cleared(current)
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

            if previous_debt < DEBT_SETTLEMENT_THRESHOLD and current['debt'] >= DEBT_SETTLEMENT_THRESHOLD:
                current['debt_since'] = _now_str()
            if current['debt'] < DEBT_SETTLEMENT_THRESHOLD:
                current['debt_since'] = None
                current = _restore_auto_suspended_if_debt_cleared(current)

            current = _ensure_reseller_defaults(current)
            resellers[user_id] = current
            os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
            with open(RESELLERS_FILE, 'w') as f:
                json.dump(resellers, f, indent=4)
            return True
        return False


def delete_reseller(user_id):
    """Delete a reseller record from the system."""
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

        if user_id not in resellers:
            return False

        del resellers[user_id]
        
        os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
        with open(RESELLERS_FILE, 'w') as f:
            json.dump(resellers, f, indent=4)
        return True


def get_banned_reseller_cleanup_candidates(reseller_data):
    """Return reseller-created customer configs eligible for banned cleanup."""
    data = _ensure_reseller_defaults(reseller_data or {})
    configs = data.get('configs', [])
    if not isinstance(configs, list):
        configs = []

    last_payment_at = data.get('last_payment_at')
    last_payment_dt = _parse_time(last_payment_at)
    candidates = []

    for index, config in enumerate(configs):
        if not isinstance(config, dict):
            continue
        username = str(config.get('username') or '').strip()
        if not username:
            continue
        timestamp = config.get('timestamp')
        timestamp_dt = _parse_time(timestamp)
        if last_payment_dt and (not timestamp_dt or timestamp_dt <= last_payment_dt):
            continue
        candidates.append({
            'config_index': index,
            'username': username,
            'customer_name': str(config.get('customer_name') or '').strip(),
            'timestamp': timestamp or 'N/A',
            'price': _safe_float(config.get('price', 0.0)),
            'server_id': config.get('server_id'),
        })

    return candidates


def cleanup_banned_reseller_users(user_id, multi_api):
    """Delete unpaid customer configs for a banned reseller and update accounting."""
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                return False, {'reason': 'Reseller not found'}
        except Exception:
            return False, {'reason': 'Unable to load resellers'}

        if user_id not in resellers:
            return False, {'reason': 'Reseller not found'}

        current = _ensure_reseller_defaults(resellers[user_id])
        if current.get('status') != 'banned':
            return False, {'reason': 'Cleanup is only available for banned resellers'}

        candidates = get_banned_reseller_cleanup_candidates(current)
        if not candidates:
            return True, {
                'deleted': [],
                'already_missing': [],
                'failed': [],
                'removed_count': 0,
                'removed_value': 0.0,
                'remaining_debt': _safe_float(current.get('debt', 0.0)),
                'remaining_configs': len(current.get('configs', []) or []),
                'last_payment_at': current.get('last_payment_at'),
            }

        deleted = []
        already_missing = []
        failed = []
        removed_indexes = set()

        for candidate in candidates:
            username = candidate['username']
            api_client, live_user = multi_api.find_user(username, preferred_server_id=candidate.get('server_id'))
            if api_client is None or live_user is None:
                already_missing.append(candidate)
                removed_indexes.add(candidate['config_index'])
                continue

            result = api_client.delete_user(username)
            if result is None:
                failed.append(candidate)
                continue

            deleted.append(candidate)
            removed_indexes.add(candidate['config_index'])

        removed_value = sum(
            _safe_float(candidate.get('price', 0.0))
            for candidate in candidates
            if candidate.get('config_index') in removed_indexes
        )
        failed_value = sum(_safe_float(candidate.get('price', 0.0)) for candidate in failed)

        configs = current.get('configs', [])
        if not isinstance(configs, list):
            configs = []
        current['configs'] = [
            config
            for index, config in enumerate(configs)
            if index not in removed_indexes
        ]
        current['debt'] = max(failed_value, _safe_float(current.get('debt', 0.0)) - removed_value)
        current = _ensure_reseller_defaults(current)
        resellers[user_id] = current

        os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
        with open(RESELLERS_FILE, 'w') as f:
            json.dump(resellers, f, indent=4)

        return True, {
            'deleted': deleted,
            'already_missing': already_missing,
            'failed': failed,
            'removed_count': len(removed_indexes),
            'removed_value': removed_value,
            'remaining_debt': _safe_float(current.get('debt', 0.0)),
            'remaining_configs': len(current.get('configs', []) or []),
            'last_payment_at': current.get('last_payment_at'),
        }


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
        credited_amount = max(0.0, min(paid_amount, current_debt))
        new_debt = max(0.0, current_debt - paid_amount)
        current['debt'] = new_debt

        if credited_amount > 0:
            current['total_paid'] = get_reseller_total_paid(current) + credited_amount
            current['last_payment_at'] = _now_str()
        if new_debt < DEBT_SETTLEMENT_THRESHOLD:
            current['debt_since'] = None
            current = _restore_auto_suspended_if_debt_cleared(current)

        current = _ensure_reseller_defaults(current)
        resellers[user_id] = current

        os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
        with open(RESELLERS_FILE, 'w') as f:
            json.dump(resellers, f, indent=4)
        return True, new_debt


def _compute_debt_state_with_deadline(debt, debt_since, now):
    """Compute debt state considering time-based deadlines.
    
    Returns (debt_state, suspend_deadline_passed, ban_deadline_passed)
    """
    debt_amount = _safe_float(debt, 0.0)
    
    if debt_amount < DEBT_SETTLEMENT_THRESHOLD:
        return 'active', False, False
    
    # Calculate time since debt started
    debt_since_dt = _parse_time(debt_since)
    hours_in_debt = 0.0
    if debt_since_dt:
        hours_in_debt = (now - debt_since_dt).total_seconds() / 3600
    
    suspend_deadline_passed = hours_in_debt >= DEBT_SUSPEND_DEADLINE_HOURS
    ban_deadline_passed = hours_in_debt >= DEBT_BAN_DEADLINE_HOURS
    
    if debt_amount >= DEBT_SUSPEND_THRESHOLD:
        # High debt - always suspended state
        return 'suspended', suspend_deadline_passed, ban_deadline_passed
    if suspend_deadline_passed:
        return 'suspended', True, ban_deadline_passed
    if debt_amount >= DEBT_WARNING_THRESHOLD:
        return 'warning', False, ban_deadline_passed
    
    return 'active', False, False


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
        suspend_delta = timedelta(hours=DEBT_SUSPEND_DEADLINE_HOURS)
        ban_delta = timedelta(hours=DEBT_BAN_DEADLINE_HOURS)
        events = []
        changed = False

        for user_id, record in resellers.items():
            current = _ensure_reseller_defaults(record)
            debt = _safe_float(current.get('debt', 0.0))
            
            # Track original status before any automatic changes
            original_status = current.get('status', 'pending')
            
            if debt >= DEBT_SETTLEMENT_THRESHOLD and not current.get('debt_since'):
                current['debt_since'] = _now_str()

            # Compute debt state with deadline consideration
            debt_since = current.get('debt_since')
            debt_state, suspend_deadline_passed, ban_deadline_passed = _compute_debt_state_with_deadline(
                debt, debt_since, now
            )
            current['debt_state'] = debt_state

            # Automatic status changes based on deadlines.
            auto_suspended = False
            auto_banned = False
            debt_suspended = current.get('suspended_reason') == SUSPENDED_REASON_DEBT
            unban_grace_suspended = current.get('suspended_reason') == SUSPENDED_REASON_UNBAN_GRACE

            if original_status == 'suspended' and unban_grace_suspended:
                suspended_at = _parse_time(current.get('suspended_at'))
                if suspended_at and (now - suspended_at) >= timedelta(hours=UNBAN_GRACE_BAN_DEADLINE_HOURS):
                    current['status'] = 'banned'
                    current['suspended_reason'] = None
                    current['suspended_at'] = None
                    auto_banned = True
                    changed = True
            
            if debt >= DEBT_SETTLEMENT_THRESHOLD and original_status in {'approved', 'suspended'}:
                if ban_deadline_passed:
                    if original_status == 'approved' or debt_suspended:
                        current['status'] = 'banned'
                        current['suspended_reason'] = None
                        current['suspended_at'] = None
                        auto_banned = True
                        changed = True
                elif suspend_deadline_passed:
                    if current.get('status') == 'approved':
                        current['status'] = 'suspended'
                        current['suspended_reason'] = SUSPENDED_REASON_DEBT
                        current['suspended_at'] = _now_str()
                        auto_suspended = True
                        changed = True
            
            # If debt is cleared (below threshold), restore approved status if it was auto-suspended
            if (
                debt < DEBT_SETTLEMENT_THRESHOLD
                and current.get('status') == 'suspended'
                and current.get('suspended_reason') == SUSPENDED_REASON_DEBT
            ):
                current['status'] = 'approved'
                current['suspended_reason'] = None
                current['suspended_at'] = None
                changed = True

            # Reminder logic
            remind_due = False
            if debt >= DEBT_SETTLEMENT_THRESHOLD and debt_state in {'warning', 'suspended'} and current.get('status') in {'approved', 'suspended'}:
                last_reminded_at = _parse_time(current.get('debt_last_reminded_at'))
                if not last_reminded_at or (now - last_reminded_at) >= reminder_delta:
                    remind_due = True
                    current['debt_last_reminded_at'] = _now_str()
                    changed = True

            # Admin alert logic
            alert_level = 'none'
            if auto_banned:
                alert_level = 'banned'
            elif debt_state == 'warning' and debt >= DEBT_SETTLEMENT_THRESHOLD:
                alert_level = 'warning'
            elif debt_state == 'suspended' and debt >= DEBT_SETTLEMENT_THRESHOLD:
                alert_level = 'suspended'

            admin_alert_due = False
            previous_alert_level = str(current.get('debt_last_admin_alert_level', 'none'))
            if alert_level != previous_alert_level:
                if alert_level in {'warning', 'suspended', 'banned'}:
                    admin_alert_due = True
                current['debt_last_admin_alert_level'] = alert_level
                current['debt_last_admin_alert_at'] = _now_str()
                changed = True

            if debt < DEBT_SETTLEMENT_THRESHOLD and previous_alert_level != 'none':
                current['debt_last_admin_alert_level'] = 'none'
                current['debt_last_admin_alert_at'] = _now_str()
                changed = True

            if current != record:
                changed = True
                resellers[user_id] = current

            # Build event for notifications
            if remind_due or admin_alert_due or auto_suspended or auto_banned:
                debt_since_dt = _parse_time(current.get('debt_since'))
                debt_age_hours = 0.0
                debt_age_days = 0
                if debt_since_dt:
                    debt_age_hours = (now - debt_since_dt).total_seconds() / 3600
                    debt_age_days = max(0, (now - debt_since_dt).days)

                unlock_amount = get_reseller_unlock_amount(debt) if debt_state == 'suspended' else 0.0

                # Calculate time remaining until deadlines
                hours_until_suspend = max(0, DEBT_SUSPEND_DEADLINE_HOURS - debt_age_hours)
                hours_until_ban = max(0, DEBT_BAN_DEADLINE_HOURS - debt_age_hours)

                events.append({
                    'user_id': str(user_id),
                    'debt': debt,
                    'debt_state': debt_state,
                    'status': current.get('status', 'pending'),
                    'suspended_reason': current.get('suspended_reason'),
                    'debt_age_days': debt_age_days,
                    'debt_age_hours': debt_age_hours,
                    'debt_since': current.get('debt_since'),
                    'last_payment_at': current.get('last_payment_at'),
                    'unlock_amount': unlock_amount,
                    'notify_user': remind_due,
                    'notify_admin': admin_alert_due,
                    'auto_suspended': auto_suspended,
                    'auto_banned': auto_banned,
                    'hours_until_suspend': hours_until_suspend if not suspend_deadline_passed else 0,
                    'hours_until_ban': hours_until_ban if not ban_deadline_passed else 0,
                    'suspend_deadline_passed': suspend_deadline_passed,
                    'ban_deadline_passed': ban_deadline_passed,
                })

        if changed:
            os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
            with open(RESELLERS_FILE, 'w') as f:
                json.dump(resellers, f, indent=4)

        return events
