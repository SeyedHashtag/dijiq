import io
import json
import os
import threading
from datetime import datetime, timedelta

try:
    from telebot import types
except ImportError:
    class _InlineKeyboardButton:
        def __init__(self, text, callback_data=None, **kwargs):
            self.text = text
            self.callback_data = callback_data
            self.kwargs = kwargs

        def to_dict(self):
            data = {"text": self.text}
            if self.callback_data is not None:
                data["callback_data"] = self.callback_data
            data.update(self.kwargs)
            return data

    class _InlineKeyboardMarkup:
        def __init__(self, row_width=1, **kwargs):
            self.row_width = row_width
            self.keyboard = []

        def add(self, *buttons):
            if not buttons:
                return self
            if self.row_width and self.row_width > 1:
                for index in range(0, len(buttons), self.row_width):
                    self.keyboard.append(list(buttons[index:index + self.row_width]))
            else:
                for button in buttons:
                    self.keyboard.append([button])
            return self

        def row(self, *buttons):
            self.keyboard.append(list(buttons))
            return self

    class _Types:
        InlineKeyboardButton = _InlineKeyboardButton
        InlineKeyboardMarkup = _InlineKeyboardMarkup

    types = _Types()

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
ADMIN_CLEANUP_PAGE_SIZE = 8
ADMIN_CLEANUP_FILTERS = (
    'queue',
    'pending',
    'due',
    'deleted',
    'already_missing',
    'delete_failed',
    'server_unavailable',
    'renewed',
)
ADMIN_CLEANUP_STATUS_ORDER = (
    'pending',
    'due',
    'deleted',
    'already_missing',
    'delete_failed',
    'server_unavailable',
    'renewed',
)
ADMIN_CLEANUP_STATUS_LABELS = {
    'queue': 'Queue',
    'pending': 'Pending',
    'due': 'Due',
    'deleted': 'Deleted',
    'already_missing': 'Already Missing',
    'delete_failed': 'Delete Failed',
    'server_unavailable': 'Server Unavailable',
    'renewed': 'Renewed',
    'unknown': 'Unknown',
}
ADMIN_CLEANUP_REASON_LABELS = {
    'time_expired': 'Time expired',
    'traffic_exhausted': 'Traffic quota exhausted',
    'missing_on_server': 'User was not found on the VPN server',
    'server_unavailable': 'VPN server was unavailable',
    'delete_failed': 'Deletion failed and will be retried',
    'unknown': 'Reason unavailable',
}

_cleanup_lock = threading.RLock()
_cleanup_refresh_lock = threading.Lock()
_cleanup_refresh_state = {
    'running': False,
    'started_at': None,
    'finished_at': None,
    'error': None,
}

ACCOUNT_TYPE_LABELS = {
    'en': {
        'test': 'your test account',
        'customer': 'your paid account',
        'reseller_customer': 'your customer account',
    },
    'fa': {
        'test': 'حساب آزمایشی شما',
        'customer': 'حساب خریداری‌شده شما',
        'reseller_customer': 'حساب مشتری شما',
    },
    'tk': {
        'test': 'synag hasabyňyz',
        'customer': 'tölegli hasabyňyz',
        'reseller_customer': 'müşderiňiziň hasaby',
    },
    'ru': {
        'test': 'ваш тестовый аккаунт',
        'customer': 'ваш оплаченный аккаунт',
        'reseller_customer': 'аккаунт вашего клиента',
    },
}

STATE_LABELS = {
    'en': {
        'state': 'State',
        'status': 'Status',
        'blocked': 'Blocked',
        'days_remaining': 'Days remaining',
        'gb_used': 'GB used',
        'gb_limit': 'GB limit',
        'gb_remaining': 'GB remaining',
        'yes': 'yes',
        'no': 'no',
        'unknown': 'unknown',
        'not_found': 'not found on server',
    },
    'fa': {
        'state': 'وضعیت',
        'status': 'وضعیت پنل',
        'blocked': 'مسدود',
        'days_remaining': 'روز باقی‌مانده',
        'gb_used': 'گیگابایت مصرف‌شده',
        'gb_limit': 'سقف گیگابایت',
        'gb_remaining': 'گیگابایت باقی‌مانده',
        'yes': 'بله',
        'no': 'خیر',
        'unknown': 'نامشخص',
        'not_found': 'روی سرور پیدا نشد',
    },
    'tk': {
        'state': 'Ýagdaý',
        'status': 'Status',
        'blocked': 'Bloklanan',
        'days_remaining': 'Galan gün',
        'gb_used': 'Ulanylan GB',
        'gb_limit': 'GB çägi',
        'gb_remaining': 'Galan GB',
        'yes': 'hawa',
        'no': 'ýok',
        'unknown': 'näbelli',
        'not_found': 'serwerde tapylmady',
    },
    'ru': {
        'state': 'Состояние',
        'status': 'Статус',
        'blocked': 'Заблокирован',
        'days_remaining': 'Осталось дней',
        'gb_used': 'Использовано ГБ',
        'gb_limit': 'Лимит ГБ',
        'gb_remaining': 'Осталось ГБ',
        'yes': 'да',
        'no': 'нет',
        'unknown': 'неизвестно',
        'not_found': 'не найден на сервере',
    },
}


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


def _labels_for(language):
    return STATE_LABELS.get(language, STATE_LABELS['en'])


def _account_type_label(source, language):
    labels = ACCOUNT_TYPE_LABELS.get(language, ACCOUNT_TYPE_LABELS['en'])
    return labels.get(source, labels.get('customer'))


def _format_state_value(value, unknown):
    return unknown if value is None else value


def _format_state_summary(last_state, language, missing=False):
    labels = _labels_for(language)
    if missing:
        return f"{labels['state']}: {labels['not_found']}"

    if not isinstance(last_state, dict):
        return f"{labels['state']}: {labels['unknown']}"

    status = _format_state_value(last_state.get('status'), labels['unknown'])
    days_remaining = _format_state_value(last_state.get('days_remaining'), labels['unknown'])
    gb_used = _format_state_value(last_state.get('gb_used'), labels['unknown'])
    gb_limit = _format_state_value(last_state.get('gb_limit'), labels['unknown'])
    gb_usage = f"{gb_used}/{gb_limit}"

    return (
        f"{labels['state']}:\n"
        f"{labels['status']}: {status}\n"
        f"{labels['days_remaining']}: {days_remaining}\n"
        f"{labels['gb_used']}: {gb_usage}"
    )


def _escape_markdown(value):
    text = str(value if value is not None else 'N/A')
    for char in ('\\', '`', '*', '_', '[', ']'):
        text = text.replace(char, f"\\{char}")
    return text


def _get_admin_cleanup_text(language, key, fallback):
    text = get_message_text(language, key)
    return text or fallback


def _normalize_admin_cleanup_filter(filter_key):
    filter_key = str(filter_key or 'queue')
    return filter_key if filter_key in ADMIN_CLEANUP_FILTERS else 'queue'


def _effective_cleanup_status(entry, now=None):
    if not isinstance(entry, dict):
        return 'unknown'

    status = str(entry.get('cleanup_status') or entry.get('delete_result') or 'unknown')
    if status == 'notified':
        delete_after = _parse_time(entry.get('delete_after'))
        if delete_after and (now or datetime.now()) >= delete_after:
            return 'due'
        return 'pending'
    if status in ADMIN_CLEANUP_STATUS_ORDER:
        return status
    if entry.get('delete_result') in DELETE_RESULTS:
        return str(entry.get('delete_result'))
    return status or 'unknown'


def _cleanup_reason(entry):
    if not isinstance(entry, dict):
        return 'unknown', ADMIN_CLEANUP_REASON_LABELS['unknown']

    status = str(entry.get('cleanup_status') or entry.get('delete_result') or '')
    delete_result = str(entry.get('delete_result') or '')
    if status == 'server_unavailable':
        return 'server_unavailable', ADMIN_CLEANUP_REASON_LABELS['server_unavailable']
    if status == 'delete_failed':
        return 'delete_failed', ADMIN_CLEANUP_REASON_LABELS['delete_failed']
    if status == 'already_missing' or delete_result == 'already_missing':
        return 'missing_on_server', ADMIN_CLEANUP_REASON_LABELS['missing_on_server']

    last_state = entry.get('last_state')
    if not isinstance(last_state, dict):
        return 'missing_on_server', ADMIN_CLEANUP_REASON_LABELS['missing_on_server']

    expiration_days = _safe_int(last_state.get('days_remaining'))
    if expiration_days is None:
        expiration_days = _safe_int(last_state.get('expiration_days'))
    if expiration_days is not None and expiration_days <= 0:
        return 'time_expired', ADMIN_CLEANUP_REASON_LABELS['time_expired']

    max_download_bytes = _safe_bytes(last_state.get('max_download_bytes'))
    if max_download_bytes > 0:
        used_bytes = _safe_bytes(last_state.get('upload_bytes')) + _safe_bytes(last_state.get('download_bytes'))
        if used_bytes >= max_download_bytes:
            return 'traffic_exhausted', ADMIN_CLEANUP_REASON_LABELS['traffic_exhausted']

    return 'unknown', ADMIN_CLEANUP_REASON_LABELS['unknown']


def _cleanup_record_from_state(state_key, entry, now=None):
    reason_code, reason = _cleanup_reason(entry)
    effective_status = _effective_cleanup_status(entry, now=now)
    cleanup_status = entry.get('cleanup_status') or effective_status
    return {
        'state_key': state_key,
        'username': entry.get('username'),
        'server_id': entry.get('server_id'),
        'source': entry.get('source'),
        'telegram_user_id': entry.get('telegram_user_id'),
        'reseller_id': entry.get('reseller_id'),
        'notified_at': entry.get('notified_at'),
        'delete_after': entry.get('delete_after'),
        'deleted_at': entry.get('deleted_at'),
        'cleanup_status': cleanup_status,
        'effective_status': effective_status,
        'delete_result': entry.get('delete_result'),
        'reason_code': reason_code,
        'reason': reason,
        'last_state': entry.get('last_state'),
    }


def _record_matches_filter(record, filter_key):
    filter_key = _normalize_admin_cleanup_filter(filter_key)
    if filter_key == 'queue':
        return record.get('effective_status') in {'pending', 'due'}
    return record.get('effective_status') == filter_key


def _record_sort_key(record):
    status = record.get('effective_status')
    if status in {'pending', 'due'}:
        return (0, record.get('delete_after') or '', record.get('username') or '')
    timestamp = _parse_time(record.get('deleted_at')) or _parse_time(record.get('notified_at')) or datetime.min
    return (
        1,
        -timestamp.year,
        -timestamp.month,
        -timestamp.day,
        -timestamp.hour,
        -timestamp.minute,
        -timestamp.second,
        record.get('username') or '',
    )


def get_expired_cleanup_records(filter_key='queue', now=None):
    now = now or datetime.now()
    state = _load_json_file(STATE_FILE, {})
    if not isinstance(state, dict):
        return []

    records = []
    for state_key, entry in state.items():
        if not isinstance(entry, dict):
            continue
        record = _cleanup_record_from_state(state_key, entry, now=now)
        if filter_key == 'all' or _record_matches_filter(record, filter_key):
            records.append(record)

    return sorted(records, key=_record_sort_key)


def get_expired_cleanup_counts(now=None):
    counts = {status: 0 for status in ADMIN_CLEANUP_STATUS_ORDER}
    for record in get_expired_cleanup_records(filter_key='all', now=now):
        status = record.get('effective_status')
        if status in counts:
            counts[status] += 1
    counts['queue'] = counts['pending'] + counts['due']
    return counts


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


def _iter_named_user_records(users):
    if isinstance(users, dict):
        for username, data in users.items():
            if isinstance(data, dict):
                yield str(data.get('username') or username), data
    elif isinstance(users, list):
        for data in users:
            if isinstance(data, dict) and data.get('username'):
                yield str(data.get('username')), data


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


def _server_candidate_match_sets(candidates):
    usernames = set()
    exact_keys = set()
    exact_candidates = {}
    username_candidates = {}
    for candidate in candidates or []:
        username = str(candidate.get('username') or '').strip()
        if not username:
            continue
        username_key = username.lower()
        usernames.add(username_key)
        username_candidates.setdefault(username_key, []).append(candidate)
        server_id = candidate.get('server_id')
        if server_id:
            key = _state_key(server_id, username).lower()
            exact_keys.add(key)
            exact_candidates[key] = candidate
    return usernames, exact_keys, exact_candidates, username_candidates


def _candidate_matches_server_candidates(candidate, usernames, exact_keys):
    username = str(candidate.get('username') or '').strip()
    if not username or username.lower() not in usernames:
        return False
    server_id = candidate.get('server_id')
    if not server_id:
        return True
    return _state_key(server_id, username).lower() in exact_keys


def discover_matching_cleanup_candidates(server_candidates):
    usernames, exact_keys, exact_candidates, username_candidates = _server_candidate_match_sets(server_candidates)
    if not usernames:
        return []
    matched = []
    for candidate in discover_cleanup_candidates():
        if not _candidate_matches_server_candidates(candidate, usernames, exact_keys):
            continue

        username = str(candidate.get('username') or '').strip()
        server_id = candidate.get('server_id')
        server_candidate = None
        if server_id:
            server_candidate = exact_candidates.get(_state_key(server_id, username).lower())
        else:
            username_matches = username_candidates.get(username.lower(), [])
            if len(username_matches) == 1:
                server_candidate = username_matches[0]

        if server_candidate:
            candidate = {
                **candidate,
                '_user_data': server_candidate.get('_user_data'),
                '_lookup_status': server_candidate.get('_lookup_status'),
                '_api_client': server_candidate.get('_api_client'),
            }
        matched.append(candidate)
    return matched


def discover_state_cleanup_candidates(state):
    candidates = []
    if not isinstance(state, dict):
        return candidates

    for entry in state.values():
        if not isinstance(entry, dict):
            continue
        cleanup_status = entry.get('cleanup_status')
        if cleanup_status in DELETE_RESULTS or cleanup_status == 'renewed':
            continue
        username = str(entry.get('username') or '').strip()
        if not username:
            continue
        candidates.append({
            'source': entry.get('source') or 'server_user',
            'username': username,
            'server_id': entry.get('server_id'),
            'telegram_user_id': entry.get('telegram_user_id'),
            'reseller_id': entry.get('reseller_id'),
        })

    return candidates


def discover_server_cleanup_candidates(multi_api):
    candidates = []
    if multi_api is None:
        return candidates

    try:
        client_iter = multi_api.iter_clients(include_disabled=True)
    except Exception:
        return candidates

    for index, (server, client) in enumerate(client_iter):
        server_id = str(
            (server or {}).get('id')
            or getattr(client, 'server_id', None)
            or f'server{index + 1}'
        )
        users = client.get_users()
        if users is None:
            continue

        for username, user_data in _iter_named_user_records(users):
            if not username or not is_user_expired(user_data):
                continue
            candidates.append({
                'source': 'server_user',
                'username': username,
                'server_id': server_id,
                '_user_data': user_data,
                '_lookup_status': 'found',
                '_api_client': client,
            })

    return candidates


def _merge_cleanup_candidates(*candidate_groups):
    merged = []
    seen_keys = set()
    wildcard_usernames = set()

    for candidates in candidate_groups:
        for candidate in candidates or []:
            username = str(candidate.get('username') or '').strip()
            if not username:
                continue

            server_id = candidate.get('server_id')
            username_key = username.lower()
            key = _state_key(server_id, username)

            if key in seen_keys:
                continue
            if server_id and username_key in wildcard_usernames:
                continue

            merged.append(candidate)
            seen_keys.add(key)
            if not server_id:
                wildcard_usernames.add(username_key)

    return merged


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


def _notify_candidate(candidate, grace_hours, last_state=None, missing=False):
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
            account_type=_account_type_label(source, language),
            state_summary=_format_state_summary(last_state, language, missing=missing),
        )
        bot.send_message(int(recipient_id), message, parse_mode='Markdown')
        return None
    except Exception as e:
        return str(e)


def _state_entry(candidate, now_value, grace_hours, notification_error=None, last_state=None):
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
        'last_state': last_state,
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
        server_candidates = discover_server_cleanup_candidates(multi_api)
        state_candidates = discover_state_cleanup_candidates(state)
        candidates = _merge_cleanup_candidates(
            discover_matching_cleanup_candidates(_merge_cleanup_candidates(server_candidates, state_candidates)),
            state_candidates,
            server_candidates,
        )

        for candidate in candidates:
            username = candidate.get('username')
            key = _state_key(candidate.get('server_id'), username)
            entry = state.get(key) if isinstance(state.get(key), dict) else None
            if entry and entry.get('cleanup_status') in DELETE_RESULTS:
                continue

            if not entry and candidate.get('_lookup_status') == 'found':
                api_client = candidate.get('_api_client')
                user_data = candidate.get('_user_data')
                lookup_status = 'found'
            else:
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

            if lookup_status == 'missing':
                _mark_deleted(
                    state,
                    key,
                    candidate,
                    'already_missing',
                    now_value,
                    last_state=entry.get('last_state') if entry else None,
                    delete_result='already_missing',
                )
                continue

            if not entry:
                last_state = capture_last_state(user_data, now=now) if lookup_status == 'found' else None
                notification_error = _notify_candidate(
                    candidate,
                    grace_hours,
                    last_state=last_state,
                    missing=lookup_status == 'missing',
                )
                state[key] = _state_entry(
                    candidate,
                    now_value,
                    grace_hours,
                    notification_error=notification_error,
                    last_state=last_state,
                )
                _update_candidate_record(
                    candidate,
                    _metadata_fields('notified', now_value, notification_error=notification_error, last_state=last_state),
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

            last_state = entry.get('last_state') or capture_last_state(user_data, now=now)
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
    deleted_users = []
    for record in get_expired_cleanup_records(filter_key='all', now=now):
        if record.get('delete_result') not in DELETE_RESULTS:
            continue
        deleted_at = _parse_time(record.get('deleted_at'))
        if not deleted_at or deleted_at < cutoff:
            continue
        deleted_users.append(record)

    return sorted(deleted_users, key=lambda item: item.get('deleted_at') or '', reverse=True)


def get_expired_cleanup_export_records(filter_key='all', now=None):
    filter_key = 'all' if filter_key == 'all' else _normalize_admin_cleanup_filter(filter_key)
    return get_expired_cleanup_records(filter_key=filter_key, now=now)


def _status_label(status):
    return ADMIN_CLEANUP_STATUS_LABELS.get(status, status.replace('_', ' ').title())


def _build_admin_cleanup_row(index, record):
    status = _status_label(record.get('effective_status'))
    username = _escape_markdown(record.get('username') or 'N/A')
    server_id = _escape_markdown(record.get('server_id') or 'primary')
    source = _escape_markdown(record.get('source') or 'unknown')
    delete_time = record.get('delete_after') or record.get('deleted_at') or 'N/A'
    reason = _escape_markdown(record.get('reason') or ADMIN_CLEANUP_REASON_LABELS['unknown'])
    return (
        f"{index}. `{username}` | `{server_id}` | {source}\n"
        f"   Status: *{_escape_markdown(status)}* | Time: `{_escape_markdown(delete_time)}`\n"
        f"   Reason: {reason}"
    )


def _paginate_records(records, page):
    total_pages = max(1, (len(records) + ADMIN_CLEANUP_PAGE_SIZE - 1) // ADMIN_CLEANUP_PAGE_SIZE)
    page = max(0, min(_safe_int(page, 0) or 0, total_pages - 1))
    start = page * ADMIN_CLEANUP_PAGE_SIZE
    return records[start:start + ADMIN_CLEANUP_PAGE_SIZE], total_pages, page


def _build_admin_cleanup_text(language, filter_key='queue', page=0, now=None):
    filter_key = _normalize_admin_cleanup_filter(filter_key)
    counts = get_expired_cleanup_counts(now=now)
    records = get_expired_cleanup_records(filter_key=filter_key, now=now)
    page_records, total_pages, page = _paginate_records(records, page)
    title = _get_admin_cleanup_text(language, "admin_expired_cleanup_title", "🧹 *Expired Cleanup*")
    label = _status_label(filter_key)
    count_lines = [
        f"Queue: *{counts.get('queue', 0)}* (Pending {counts.get('pending', 0)} / Due {counts.get('due', 0)})",
        f"Deleted: *{counts.get('deleted', 0)}* | Missing: *{counts.get('already_missing', 0)}*",
        f"Failed: *{counts.get('delete_failed', 0)}* | Unavailable: *{counts.get('server_unavailable', 0)}* | Renewed: *{counts.get('renewed', 0)}*",
    ]

    if page_records:
        start = page * ADMIN_CLEANUP_PAGE_SIZE
        rows = "\n\n".join(_build_admin_cleanup_row(start + idx + 1, record) for idx, record in enumerate(page_records))
    else:
        rows = _get_admin_cleanup_text(language, "admin_expired_cleanup_empty", "No records in this view.")

    refresh_state = _get_cleanup_refresh_state()
    scan_line = ""
    if refresh_state.get('running'):
        scan_line = f"\nScan: *running* since `{_escape_markdown(refresh_state.get('started_at') or 'N/A')}`\n"
    elif refresh_state.get('finished_at'):
        scan_status = 'failed' if refresh_state.get('error') else 'completed'
        scan_line = f"\nScan: *{scan_status}* at `{_escape_markdown(refresh_state.get('finished_at'))}`\n"

    return (
        f"{title}\n\n"
        f"{chr(10).join(count_lines)}\n\n"
        f"{scan_line}"
        f"View: *{_escape_markdown(label)}* | Page *{page + 1}/{total_pages}*\n\n"
        f"{rows}"
    )


def _filter_button_label(filter_key, counts):
    if filter_key == 'queue':
        return f"Queue ({counts.get('queue', 0)})"
    return f"{_status_label(filter_key)} ({counts.get(filter_key, 0)})"


def _build_admin_cleanup_markup(filter_key='queue', page=0, now=None):
    filter_key = _normalize_admin_cleanup_filter(filter_key)
    records = get_expired_cleanup_records(filter_key=filter_key, now=now)
    _, total_pages, page = _paginate_records(records, page)
    counts = get_expired_cleanup_counts(now=now)
    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton(_filter_button_label('queue', counts), callback_data="admin_expired_cleanup:list:queue:0"),
        types.InlineKeyboardButton(_filter_button_label('pending', counts), callback_data="admin_expired_cleanup:list:pending:0"),
    )
    markup.add(
        types.InlineKeyboardButton(_filter_button_label('due', counts), callback_data="admin_expired_cleanup:list:due:0"),
        types.InlineKeyboardButton(_filter_button_label('deleted', counts), callback_data="admin_expired_cleanup:list:deleted:0"),
    )
    markup.add(
        types.InlineKeyboardButton(_filter_button_label('already_missing', counts), callback_data="admin_expired_cleanup:list:already_missing:0"),
        types.InlineKeyboardButton(_filter_button_label('delete_failed', counts), callback_data="admin_expired_cleanup:list:delete_failed:0"),
    )
    markup.add(
        types.InlineKeyboardButton(_filter_button_label('server_unavailable', counts), callback_data="admin_expired_cleanup:list:server_unavailable:0"),
        types.InlineKeyboardButton(_filter_button_label('renewed', counts), callback_data="admin_expired_cleanup:list:renewed:0"),
    )

    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_expired_cleanup:list:{filter_key}:{page - 1}"))
        nav_buttons.append(types.InlineKeyboardButton(f"Page {page + 1}/{total_pages}", callback_data="admin_expired_cleanup:noop"))
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"admin_expired_cleanup:list:{filter_key}:{page + 1}"))
        markup.add(*nav_buttons)

    markup.add(
        types.InlineKeyboardButton("📤 Export Current Filter", callback_data=f"admin_expired_cleanup:export:{filter_key}"),
        types.InlineKeyboardButton("📦 Export All", callback_data="admin_expired_cleanup:export:all"),
    )
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data=f"admin_expired_cleanup:refresh:{filter_key}:{page}"))
    return markup


def _get_cleanup_refresh_state():
    with _cleanup_refresh_lock:
        return dict(_cleanup_refresh_state)


def _cleanup_refresh_worker(grace_hours=24):
    error = None
    try:
        run_expired_user_cleanup(grace_hours=grace_hours)
    except Exception as e:
        error = str(e)
        print(f"Error refreshing expired cleanup dashboard: {e}")
    finally:
        with _cleanup_refresh_lock:
            _cleanup_refresh_state.update({
                'running': False,
                'finished_at': _now_str(),
                'error': error,
            })


def _start_cleanup_refresh_for_dashboard(grace_hours=24):
    with _cleanup_refresh_lock:
        if _cleanup_refresh_state.get('running'):
            return False
        _cleanup_refresh_state.update({
            'running': True,
            'started_at': _now_str(),
            'finished_at': None,
            'error': None,
        })

    thread = threading.Thread(
        target=_cleanup_refresh_worker,
        kwargs={'grace_hours': grace_hours},
        daemon=True,
    )
    thread.start()
    return True


def _render_admin_expired_cleanup(chat_id, message_id, admin_id, filter_key='queue', page=0):
    language = get_user_language(admin_id)
    filter_key = _normalize_admin_cleanup_filter(filter_key)
    bot.edit_message_text(
        _build_admin_cleanup_text(language, filter_key=filter_key, page=page),
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=_build_admin_cleanup_markup(filter_key=filter_key, page=page),
        parse_mode="Markdown",
    )


def _send_cleanup_export(chat_id, filter_key='all'):
    filter_key = 'all' if filter_key == 'all' else _normalize_admin_cleanup_filter(filter_key)
    records = get_expired_cleanup_export_records(filter_key=filter_key)
    payload = json.dumps(records, indent=2).encode('utf-8')
    document = io.BytesIO(payload)
    document.name = f"expired_cleanup_{filter_key}.json"
    bot.send_document(
        chat_id,
        document,
        caption=f"Expired cleanup export ({filter_key}): {len(records)} records",
    )


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '🧹 Expired Cleanup')
def admin_expired_cleanup_menu(message):
    _start_cleanup_refresh_for_dashboard()
    language = get_user_language(message.from_user.id)
    bot.reply_to(
        message,
        _build_admin_cleanup_text(language, filter_key='queue', page=0),
        reply_markup=_build_admin_cleanup_markup(filter_key='queue', page=0),
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_expired_cleanup:"))
def handle_admin_expired_cleanup(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Unauthorized", show_alert=True)
        return

    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "noop":
        bot.answer_callback_query(call.id)
        return

    if action == "list" and len(parts) == 4:
        filter_key = _normalize_admin_cleanup_filter(parts[2])
        page = _safe_int(parts[3], 0) or 0
        _render_admin_expired_cleanup(call.message.chat.id, call.message.message_id, call.from_user.id, filter_key, page)
        bot.answer_callback_query(call.id)
        return

    if action == "refresh" and len(parts) == 4:
        filter_key = _normalize_admin_cleanup_filter(parts[2])
        page = _safe_int(parts[3], 0) or 0
        started = _start_cleanup_refresh_for_dashboard()
        _render_admin_expired_cleanup(call.message.chat.id, call.message.message_id, call.from_user.id, filter_key, page)
        bot.answer_callback_query(call.id, "Scan started." if started else "Scan already running.")
        return

    if action == "export" and len(parts) == 3:
        filter_key = parts[2]
        _send_cleanup_export(call.message.chat.id, filter_key=filter_key)
        bot.answer_callback_query(call.id, "Export sent.")
        return

    bot.answer_callback_query(call.id, "Invalid action.", show_alert=True)


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
