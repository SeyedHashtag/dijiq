import io
import json
import os
import threading
from datetime import datetime, timedelta

from utils.api_client import MultiServerAPI
from utils.command import bot, is_admin
from utils.language import get_user_language
from utils.translations import get_message_text


TEST_CONFIGS_FILE = '/etc/dijiq/core/scripts/telegrambot/test_configs.json'
PAYMENTS_FILE = '/etc/dijiq/core/scripts/telegrambot/payments.json'
RESELLERS_FILE = '/etc/dijiq/core/scripts/telegrambot/resellers.json'
STATE_FILE = '/etc/dijiq/core/scripts/telegrambot/expired_user_cleanup.json'

GB_BYTES = 1024 ** 3
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
DELETE_RESULTS = {'deleted', 'already_missing'}

_cleanup_lock = threading.RLock()


def _now_str(now=None):
    return (now or datetime.now()).strftime(TIMESTAMP_FORMAT)


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), TIMESTAMP_FORMAT)
    except Exception:
        return None


def _load_json_file(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                return data if data is not None else default
    except Exception:
        pass
    return default


def _save_json_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)


def _safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bytes(value):
    value = _safe_int(value, 0)
    return max(0, value or 0)


def _safe_gb(byte_count):
    if byte_count is None:
        return None
    return round(float(byte_count) / GB_BYTES, 3)


def _state_key(server_id, username):
    return f"{server_id or 'primary'}:{username}"


def _is_deleted_record(record):
    return (
        record.get('cleanup_status') in DELETE_RESULTS
        or record.get('cleanup_deleted_at')
    )


def is_user_expired(user_data):
    if not isinstance(user_data, dict):
        return False

    if not bool(user_data.get('blocked', False)):
        return False

    expiration_days = _safe_int(user_data.get('expiration_days'))
    if expiration_days is not None and expiration_days <= 0:
        return True

    max_download_bytes = _safe_bytes(user_data.get('max_download_bytes'))
    if max_download_bytes > 0:
        used_bytes = (
            _safe_bytes(user_data.get('upload_bytes'))
            + _safe_bytes(user_data.get('download_bytes'))
        )
        if used_bytes >= max_download_bytes:
            return True

    return False


def capture_last_state(user_data, now=None):
    upload_bytes = _safe_bytes(user_data.get('upload_bytes'))
    download_bytes = _safe_bytes(user_data.get('download_bytes'))
    max_download_bytes = _safe_bytes(user_data.get('max_download_bytes'))
    used_bytes = upload_bytes + download_bytes
    remaining_bytes = None
    if max_download_bytes > 0:
        remaining_bytes = max(0, max_download_bytes - used_bytes)

    return {
        'captured_at': _now_str(now),
        'days_remaining': _safe_int(user_data.get('expiration_days')),
        'gb_remaining': _safe_gb(remaining_bytes),
        'gb_limit': _safe_gb(max_download_bytes) if max_download_bytes > 0 else None,
        'gb_used': _safe_gb(used_bytes),
        'blocked': bool(user_data.get('blocked', False)),
        'status': user_data.get('status'),
        'upload_bytes': upload_bytes,
        'download_bytes': download_bytes,
        'max_download_bytes': max_download_bytes,
    }


def _metadata_fields(status, now_value, notification_error=None, cleanup_error=None, last_state=None, delete_result=None):
    fields = {
        'cleanup_status': status,
        'cleanup_error': cleanup_error,
    }
    if status == 'notified':
        fields['cleanup_notified_at'] = now_value
    if status in DELETE_RESULTS:
        fields['cleanup_deleted_at'] = now_value
        fields['cleanup_delete_result'] = delete_result or status
    if notification_error is not None:
        fields['cleanup_notification_error'] = notification_error
    if last_state is not None:
        fields['cleanup_last_state'] = last_state
    return fields


def _apply_fields(target, fields):
    for key, value in fields.items():
        if value is None and key == 'cleanup_error':
            target.pop(key, None)
        else:
            target[key] = value


def _completed_payment(record):
    if not isinstance(record, dict):
        return False
    if record.get('type') == 'settlement' or record.get('plan_gb') == 'Settlement':
        return False
    return str(record.get('status', '')).lower() in {'completed', 'paid', 'succeeded'}


def discover_cleanup_candidates():
    candidates = []

    test_configs = _load_json_file(TEST_CONFIGS_FILE, {})
    if isinstance(test_configs, dict):
        for telegram_id, entry in test_configs.items():
            if not isinstance(entry, dict) or _is_deleted_record(entry):
                continue
            username = str(entry.get('username') or '').strip()
            if not username:
                continue
            candidates.append({
                'source': 'test',
                'username': username,
                'server_id': entry.get('server_id'),
                'telegram_user_id': str(entry.get('telegram_id') or telegram_id),
                '_record_ref': ('test', str(telegram_id)),
            })

    payments = _load_json_file(PAYMENTS_FILE, {})
    if isinstance(payments, dict):
        for payment_id, record in payments.items():
            if not _completed_payment(record) or _is_deleted_record(record):
                continue
            username = str(record.get('username') or '').strip()
            if not username:
                continue
            candidates.append({
                'source': 'customer',
                'username': username,
                'server_id': record.get('server_id'),
                'telegram_user_id': str(record.get('user_id') or ''),
                '_record_ref': ('payment', str(payment_id)),
            })

    resellers = _load_json_file(RESELLERS_FILE, {})
    if isinstance(resellers, dict):
        for reseller_id, reseller_data in resellers.items():
            if not isinstance(reseller_data, dict):
                continue
            configs = reseller_data.get('configs', [])
            if not isinstance(configs, list):
                continue
            for index, config in enumerate(configs):
                if not isinstance(config, dict) or _is_deleted_record(config):
                    continue
                username = str(config.get('username') or '').strip()
                if not username:
                    continue
                candidates.append({
                    'source': 'reseller_customer',
                    'username': username,
                    'server_id': config.get('server_id'),
                    'reseller_id': str(reseller_id),
                    '_record_ref': ('reseller', str(reseller_id), index),
                })

    deduped = {}
    for candidate in candidates:
        deduped.setdefault(_state_key(candidate.get('server_id'), candidate['username']), candidate)
    return list(deduped.values())


def _update_candidate_record(candidate, fields):
    ref = candidate.get('_record_ref') or ()
    if not ref:
        return

    kind = ref[0]
    if kind == 'test':
        data = _load_json_file(TEST_CONFIGS_FILE, {})
        entry = data.get(ref[1]) if isinstance(data, dict) else None
        if isinstance(entry, dict):
            _apply_fields(entry, fields)
            _save_json_file(TEST_CONFIGS_FILE, data)
        return

    if kind == 'payment':
        data = _load_json_file(PAYMENTS_FILE, {})
        entry = data.get(ref[1]) if isinstance(data, dict) else None
        if isinstance(entry, dict):
            _apply_fields(entry, fields)
            _save_json_file(PAYMENTS_FILE, data)
        return

    if kind == 'reseller':
        data = _load_json_file(RESELLERS_FILE, {})
        reseller = data.get(ref[1]) if isinstance(data, dict) else None
        configs = reseller.get('configs', []) if isinstance(reseller, dict) else []
        if isinstance(configs, list) and 0 <= ref[2] < len(configs) and isinstance(configs[ref[2]], dict):
            _apply_fields(configs[ref[2]], fields)
            _save_json_file(RESELLERS_FILE, data)


def _get_user_lookup(multi_api, username, preferred_server_id=None):
    checked_any = False
    unavailable = False

    if preferred_server_id:
        client = multi_api.get_client(preferred_server_id)
        if not client:
            return None, None, 'unavailable'
        user_data = client.get_user(username)
        if user_data is not None:
            return client, user_data, 'found'
        users = client.get_users()
        if users is None:
            return client, None, 'unavailable'
        return client, None, 'missing'

    for _, client in multi_api.iter_clients(include_disabled=True):
        checked_any = True
        user_data = client.get_user(username)
        if user_data is not None:
            return client, user_data, 'found'
        users = client.get_users()
        if users is None:
            unavailable = True

    if unavailable or not checked_any:
        return None, None, 'unavailable'
    return None, None, 'missing'


def _notify_candidate(candidate, grace_hours):
    source = candidate.get('source')
    recipient_id = candidate.get('reseller_id') if source == 'reseller_customer' else candidate.get('telegram_user_id')
    if not recipient_id:
        return 'missing_recipient'

    try:
        language = get_user_language(int(recipient_id))
        key = (
            'expired_cleanup_reseller_notice'
            if source == 'reseller_customer'
            else 'expired_cleanup_customer_notice'
        )
        message = get_message_text(language, key).format(
            username=candidate.get('username'),
            grace_hours=int(grace_hours),
        )
        bot.send_message(int(recipient_id), message, parse_mode='Markdown')
        return None
    except Exception as e:
        return str(e)


def _state_entry(candidate, now_value, grace_hours, notification_error=None):
    return {
        'username': candidate.get('username'),
        'server_id': candidate.get('server_id') or 'primary',
        'source': candidate.get('source'),
        'telegram_user_id': candidate.get('telegram_user_id'),
        'reseller_id': candidate.get('reseller_id'),
        'notified_at': now_value,
        'delete_after': (datetime.strptime(now_value, TIMESTAMP_FORMAT) + timedelta(hours=grace_hours)).strftime(TIMESTAMP_FORMAT),
        'cleanup_status': 'notified',
        'notification_error': notification_error,
    }


def _mark_deleted(state, key, candidate, status, now_value, last_state=None, delete_result=None):
    entry = state.setdefault(key, {})
    entry.update({
        'username': candidate.get('username'),
        'server_id': candidate.get('server_id') or entry.get('server_id') or 'primary',
        'source': candidate.get('source'),
        'telegram_user_id': candidate.get('telegram_user_id'),
        'reseller_id': candidate.get('reseller_id'),
        'deleted_at': now_value,
        'cleanup_status': status,
        'delete_result': delete_result or status,
        'last_state': last_state,
    })
    fields = _metadata_fields(
        status,
        now_value,
        last_state=last_state,
        delete_result=delete_result or status,
    )
    _update_candidate_record(candidate, fields)


def run_expired_user_cleanup(grace_hours=24, now=None, multi_api=None):
    now = now or datetime.now()
    now_value = _now_str(now)
    grace_delta = timedelta(hours=grace_hours)

    with _cleanup_lock:
        state = _load_json_file(STATE_FILE, {})
        if not isinstance(state, dict):
            state = {}

        multi_api = multi_api or MultiServerAPI()
        candidates = discover_cleanup_candidates()

        for candidate in candidates:
            username = candidate.get('username')
            key = _state_key(candidate.get('server_id'), username)
            entry = state.get(key) if isinstance(state.get(key), dict) else None
            if entry and entry.get('cleanup_status') in DELETE_RESULTS:
                continue

            api_client, user_data, lookup_status = _get_user_lookup(
                multi_api,
                username,
                preferred_server_id=candidate.get('server_id'),
            )

            if lookup_status == 'unavailable':
                if entry:
                    entry['cleanup_status'] = 'server_unavailable'
                    entry['cleanup_error'] = 'server_unavailable'
                    entry['last_checked_at'] = now_value
                continue

            if lookup_status == 'found' and not is_user_expired(user_data):
                if entry:
                    state.pop(key, None)
                    _update_candidate_record(candidate, {'cleanup_status': 'renewed', 'cleanup_error': None})
                continue

            if not entry:
                notification_error = _notify_candidate(candidate, grace_hours)
                state[key] = _state_entry(candidate, now_value, grace_hours, notification_error=notification_error)
                _update_candidate_record(
                    candidate,
                    _metadata_fields('notified', now_value, notification_error=notification_error),
                )
                continue

            notified_at = _parse_time(entry.get('notified_at'))
            delete_after = _parse_time(entry.get('delete_after'))
            if delete_after is None and notified_at is not None:
                delete_after = notified_at + grace_delta
                entry['delete_after'] = delete_after.strftime(TIMESTAMP_FORMAT)

            if delete_after is None or now < delete_after:
                entry['cleanup_status'] = 'notified'
                entry['last_checked_at'] = now_value
                continue

            if lookup_status == 'missing':
                _mark_deleted(state, key, candidate, 'already_missing', now_value, last_state=entry.get('last_state'), delete_result='already_missing')
                continue

            last_state = capture_last_state(user_data, now=now)
            entry['last_state'] = last_state
            delete_result = api_client.delete_user(username) if api_client else None
            if delete_result is None:
                entry['cleanup_status'] = 'delete_failed'
                entry['cleanup_error'] = 'delete_failed'
                entry['last_checked_at'] = now_value
                _update_candidate_record(
                    candidate,
                    _metadata_fields('delete_failed', now_value, cleanup_error='delete_failed', last_state=last_state),
                )
                continue

            _mark_deleted(state, key, candidate, 'deleted', now_value, last_state=last_state, delete_result='deleted')

        _save_json_file(STATE_FILE, state)
        return state


def get_deleted_users_for_json(days=60, now=None):
    now = now or datetime.now()
    cutoff = now - timedelta(days=days)
    state = _load_json_file(STATE_FILE, {})
    if not isinstance(state, dict):
        return []

    deleted_users = []
    for entry in state.values():
        if not isinstance(entry, dict) or entry.get('delete_result') not in DELETE_RESULTS:
            continue
        deleted_at = _parse_time(entry.get('deleted_at'))
        if not deleted_at or deleted_at < cutoff:
            continue
        deleted_users.append({
            'username': entry.get('username'),
            'server_id': entry.get('server_id'),
            'source': entry.get('source'),
            'telegram_user_id': entry.get('telegram_user_id'),
            'reseller_id': entry.get('reseller_id'),
            'notified_at': entry.get('notified_at'),
            'deleted_at': entry.get('deleted_at'),
            'delete_result': entry.get('delete_result'),
            'last_state': entry.get('last_state'),
        })

    return sorted(deleted_users, key=lambda item: item.get('deleted_at') or '', reverse=True)


@bot.message_handler(commands=['deleted_expired_users', 'deleted_expired_users_json'])
def send_deleted_expired_users_json(message):
    if not is_admin(message.from_user.id):
        return

    deleted_users = get_deleted_users_for_json(days=60)
    payload = json.dumps(deleted_users, indent=2).encode('utf-8')
    document = io.BytesIO(payload)
    document.name = 'deleted_expired_users_last_60_days.json'
    bot.send_document(
        message.chat.id,
        document,
        caption=f"Deleted expired users from the past 60 days: {len(deleted_users)}",
    )
