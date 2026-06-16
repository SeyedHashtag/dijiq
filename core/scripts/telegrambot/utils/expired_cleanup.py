import io
import hashlib
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
from utils.translations import get_button_text, get_message_text


TEST_CONFIGS_FILE = '/etc/dijiq/core/scripts/telegrambot/test_configs.json'
PAYMENTS_FILE = '/etc/dijiq/core/scripts/telegrambot/payments.json'
RESELLERS_FILE = '/etc/dijiq/core/scripts/telegrambot/resellers.json'
STATE_FILE = '/etc/dijiq/core/scripts/telegrambot/expired_user_cleanup.json'
SCHEDULE_FILE = '/etc/dijiq/core/scripts/telegrambot/expired_cleanup_schedule.json'

GB_BYTES = 1024 ** 3
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
CLEANUP_SCAN_INTERVAL_SECONDS = 3600
DELETE_RESULTS = {'deleted', 'already_missing'}
ADMIN_CLEANUP_PAGE_SIZE = 8
ADMIN_CLEANUP_FILTERS = (
    'manual_review',
    'duplicate_payment',
    'pending',
    'due',
    'deleted',
    'already_missing',
    'delete_failed',
    'server_unavailable',
    'renewed',
)
ADMIN_CLEANUP_STATUS_ORDER = (
    'manual_review',
    'duplicate_payment',
    'pending',
    'due',
    'deleted',
    'already_missing',
    'delete_failed',
    'server_unavailable',
    'renewed',
)
ADMIN_CLEANUP_STATUS_LABELS = {
    'manual_review': 'Manual Review',
    'duplicate_payment': 'Duplicate',
    'pending': 'Pending',
    'due': 'Due',
    'deleted': 'Deleted',
    'already_missing': 'Already Missing',
    'delete_failed': 'Delete Failed',
    'server_unavailable': 'Server Unavailable',
    'renewed': 'Renewed',
    'unknown': 'Unknown',
}
ADMIN_CLEANUP_FILTER_DESCRIPTIONS = {
    'pending': 'Notified users waiting for the grace period before automatic cleanup.',
    'due': 'Notified users whose grace period has passed and are ready for automatic cleanup.',
    'manual_review': 'Server-only or orphaned records that need an admin decision.',
    'duplicate_payment': 'Duplicate configs from repeated payment creation that need an admin decision.',
    'deleted': 'Users deleted by expired cleanup.',
    'already_missing': 'Users that were already absent from the VPN server.',
    'delete_failed': 'Users cleanup tried to delete but the server rejected or failed.',
    'server_unavailable': 'Users skipped because their VPN server was unavailable.',
    'renewed': 'Users that cleanup saw as active again after renewal or reset.',
}
ADMIN_CLEANUP_REASON_LABELS = {
    'time_expired': 'Time expired',
    'traffic_exhausted': 'Traffic quota exhausted',
    'duplicate_payment': 'Duplicate payment review',
    'missing_on_server': 'User was not found on the VPN server',
    'server_unavailable': 'VPN server was unavailable',
    'delete_failed': 'Deletion failed and will be retried',
    'unknown': 'Reason unavailable',
}
ADMIN_CLEANUP_REVIEW_FILTER_CODES = {
    'manual_review': 'mr',
    'duplicate_payment': 'dp',
}
ADMIN_CLEANUP_REVIEW_FILTERS_BY_CODE = {
    value: key for key, value in ADMIN_CLEANUP_REVIEW_FILTER_CODES.items()
}
ADMIN_CLEANUP_REVIEW_ACTIONS = {
    'rk': 'review_keep',
    'rd': 'review_delete',
}
RESELLER_CLEANUP_METADATA_FIELDS = (
    'cleanup_status',
    'cleanup_error',
    'cleanup_notified_at',
    'cleanup_deleted_at',
    'cleanup_delete_result',
    'cleanup_notification_error',
    'cleanup_last_state',
)

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


def _load_current_resellers_for_cleanup_save():
    try:
        from utils import reseller as reseller_store

        original_path = reseller_store.RESELLERS_FILE
        reseller_store.RESELLERS_FILE = RESELLERS_FILE
        try:
            return reseller_store.load_resellers()
        finally:
            reseller_store.RESELLERS_FILE = original_path
    except Exception:
        data = _load_json_file(RESELLERS_FILE, {})
        return data if isinstance(data, dict) else {}


def _save_current_resellers_for_cleanup_save(resellers):
    try:
        from utils import reseller as reseller_store

        original_path = reseller_store.RESELLERS_FILE
        reseller_store.RESELLERS_FILE = RESELLERS_FILE
        try:
            reseller_store.save_resellers(resellers if isinstance(resellers, dict) else {})
            return
        finally:
            reseller_store.RESELLERS_FILE = original_path
    except Exception:
        _save_json_file(RESELLERS_FILE, resellers if isinstance(resellers, dict) else {})


def _get_reseller_config_by_ref(resellers, ref):
    if not isinstance(resellers, dict) or len(ref) < 3:
        return None
    reseller = resellers.get(str(ref[1]))
    configs = reseller.get('configs', []) if isinstance(reseller, dict) else []
    if not isinstance(configs, list):
        return None
    try:
        index = int(ref[2])
    except (TypeError, ValueError):
        return None
    if 0 <= index < len(configs) and isinstance(configs[index], dict):
        return configs[index]
    return None


def _find_latest_reseller_config(latest_resellers, ref, source_config):
    if not isinstance(latest_resellers, dict) or len(ref) < 3:
        return None
    reseller = latest_resellers.get(str(ref[1]))
    configs = reseller.get('configs', []) if isinstance(reseller, dict) else []
    if not isinstance(configs, list):
        return None

    try:
        index = int(ref[2])
    except (TypeError, ValueError):
        index = -1

    source_username = str((source_config or {}).get('username') or '').strip().lower()
    source_server_id = str((source_config or {}).get('server_id') or '').strip()
    if 0 <= index < len(configs) and isinstance(configs[index], dict):
        indexed = configs[index]
        indexed_username = str(indexed.get('username') or '').strip().lower()
        indexed_server_id = str(indexed.get('server_id') or '').strip()
        if indexed_username == source_username and (not source_server_id or indexed_server_id == source_server_id):
            return indexed

    for config in configs:
        if not isinstance(config, dict):
            continue
        username = str(config.get('username') or '').strip().lower()
        server_id = str(config.get('server_id') or '').strip()
        if username == source_username and (not source_server_id or server_id == source_server_id):
            return config
    return None


def _save_reseller_cleanup_metadata(stale_resellers, dirty_refs):
    refs = set(dirty_refs or set())
    if not refs:
        _save_current_resellers_for_cleanup_save(stale_resellers if isinstance(stale_resellers, dict) else {})
        return

    latest_resellers = _load_current_resellers_for_cleanup_save()
    for ref in refs:
        source_config = _get_reseller_config_by_ref(stale_resellers, ref)
        target_config = _find_latest_reseller_config(latest_resellers, ref, source_config)
        if source_config is None or target_config is None:
            continue
        for field in RESELLER_CLEANUP_METADATA_FIELDS:
            if field in source_config:
                target_config[field] = source_config[field]
            else:
                target_config.pop(field, None)

    _save_current_resellers_for_cleanup_save(latest_resellers)


def _load_cleanup_schedule_metadata():
    data = _load_json_file(SCHEDULE_FILE, {})
    return data if isinstance(data, dict) else {}


def _save_cleanup_schedule_metadata(data):
    _save_json_file(SCHEDULE_FILE, data if isinstance(data, dict) else {})


def get_expired_cleanup_schedule_metadata():
    return dict(_load_cleanup_schedule_metadata())


def get_expired_cleanup_startup_delay(interval_seconds=CLEANUP_SCAN_INTERVAL_SECONDS, now=None, metadata=None):
    now = now or datetime.now()
    metadata = metadata if isinstance(metadata, dict) else _load_cleanup_schedule_metadata()
    interval_seconds = max(0, _safe_int(interval_seconds, CLEANUP_SCAN_INTERVAL_SECONDS) or 0)
    attempt_times = [
        _parse_time(metadata.get('last_finished_at')),
        _parse_time(metadata.get('last_started_at')),
    ]
    attempt_times = [value for value in attempt_times if value is not None]
    if not attempt_times:
        return 0

    elapsed = (now - max(attempt_times)).total_seconds()
    if elapsed < 0:
        return interval_seconds
    return max(0, int(interval_seconds - elapsed))


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


def _state_record_id(state_key):
    return hashlib.sha1(str(state_key).encode('utf-8')).hexdigest()[:16]


def _find_state_key_by_record_id(record_id):
    state = _load_json_file(STATE_FILE, {})
    if not isinstance(state, dict):
        return None, None, {}
    for state_key, entry in state.items():
        if _state_record_id(state_key) == record_id and isinstance(entry, dict):
            return state_key, entry, state
    return None, None, state


def _candidate_from_state_entry(entry):
    return {
        'source': entry.get('source'),
        'username': entry.get('username'),
        'server_id': entry.get('server_id'),
        'telegram_user_id': entry.get('telegram_user_id'),
        'reseller_id': entry.get('reseller_id'),
    }


def _is_deleted_record(record):
    return (
        record.get('cleanup_status') in DELETE_RESULTS
        or record.get('cleanup_deleted_at')
    )


def _is_already_missing_record(record):
    return (
        record.get('cleanup_status') == 'already_missing'
        or record.get('cleanup_delete_result') == 'already_missing'
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
    filter_key = str(filter_key or 'pending')
    return filter_key if filter_key in ADMIN_CLEANUP_FILTERS else 'pending'


def _is_duplicate_payment_review(record):
    return (
        isinstance(record, dict)
        and record.get('effective_status') == 'manual_review'
        and record.get('manual_review_reason') == 'duplicate_payment'
    )


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

    if (
        entry.get('cleanup_status') == 'manual_review'
        and entry.get('manual_review_reason') == 'duplicate_payment'
    ):
        return 'duplicate_payment', ADMIN_CLEANUP_REASON_LABELS['duplicate_payment']

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
        'review_status': entry.get('review_status'),
        'reviewed_at': entry.get('reviewed_at'),
        'reviewed_by': entry.get('reviewed_by'),
        'notified_at': entry.get('notified_at'),
        'delete_after': entry.get('delete_after'),
        'deleted_at': entry.get('deleted_at'),
        'cleanup_status': cleanup_status,
        'effective_status': effective_status,
        'delete_result': entry.get('delete_result'),
        'reason_code': reason_code,
        'reason': reason,
        'manual_review_reason': entry.get('manual_review_reason'),
        'review_note': entry.get('review_note'),
        'last_state': entry.get('last_state'),
    }


def _record_matches_filter(record, filter_key):
    filter_key = _normalize_admin_cleanup_filter(filter_key)
    if filter_key == 'duplicate_payment':
        return _is_duplicate_payment_review(record)
    if filter_key == 'manual_review':
        return record.get('effective_status') == 'manual_review' and not _is_duplicate_payment_review(record)
    return record.get('effective_status') == filter_key


def _record_sort_key(record):
    status = record.get('effective_status')
    if status == 'manual_review':
        return (0, record.get('reviewed_at') or '', record.get('username') or '')
    if status in {'pending', 'due'}:
        return (1, record.get('delete_after') or '', record.get('username') or '')
    timestamp = _parse_time(record.get('deleted_at')) or _parse_time(record.get('notified_at')) or datetime.min
    return (
        2,
        -timestamp.year,
        -timestamp.month,
        -timestamp.day,
        -timestamp.hour,
        -timestamp.minute,
        -timestamp.second,
        record.get('username') or '',
    )


def get_expired_cleanup_records(filter_key='pending', now=None):
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
        if _is_duplicate_payment_review(record):
            counts['duplicate_payment'] += 1
            continue
        status = record.get('effective_status')
        if status in counts:
            counts[status] += 1
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


def _clear_state_delete_metadata(entry):
    if not isinstance(entry, dict):
        return
    for key in ('deleted_at', 'delete_result', 'cleanup_error'):
        entry.pop(key, None)


def _load_cleanup_record_stores():
    return {
        'test_configs': _load_json_file(TEST_CONFIGS_FILE, {}),
        'payments': _load_json_file(PAYMENTS_FILE, {}),
        'resellers': _load_json_file(RESELLERS_FILE, {}),
        '_dirty': set(),
        '_reseller_dirty_refs': set(),
    }


def _save_dirty_cleanup_record_stores(stores):
    if not isinstance(stores, dict):
        return
    dirty = stores.get('_dirty') or set()
    if 'test_configs' in dirty:
        _save_json_file(TEST_CONFIGS_FILE, stores.get('test_configs') if isinstance(stores.get('test_configs'), dict) else {})
    if 'payments' in dirty:
        _save_json_file(PAYMENTS_FILE, stores.get('payments') if isinstance(stores.get('payments'), dict) else {})
    if 'resellers' in dirty:
        _save_reseller_cleanup_metadata(
            stores.get('resellers') if isinstance(stores.get('resellers'), dict) else {},
            stores.get('_reseller_dirty_refs') or set(),
        )
    dirty.clear()
    if isinstance(stores.get('_reseller_dirty_refs'), set):
        stores['_reseller_dirty_refs'].clear()


def _mark_store_dirty(stores, key):
    if isinstance(stores, dict):
        stores.setdefault('_dirty', set()).add(key)


def _mark_reseller_ref_dirty(stores, ref):
    if not isinstance(stores, dict) or len(ref) < 3:
        return
    try:
        config_index = int(ref[2])
    except (TypeError, ValueError):
        return
    stores.setdefault('_reseller_dirty_refs', set()).add(('reseller', str(ref[1]), config_index))
    _mark_store_dirty(stores, 'resellers')


def _clear_candidate_delete_metadata(candidate, stores=None):
    ref = candidate.get('_record_ref') or ()
    if not ref:
        return

    kind = ref[0]
    if kind == 'test':
        data = stores.get('test_configs') if isinstance(stores, dict) else _load_json_file(TEST_CONFIGS_FILE, {})
        entry = data.get(ref[1]) if isinstance(data, dict) else None
        if isinstance(entry, dict):
            for key in ('cleanup_deleted_at', 'cleanup_delete_result', 'cleanup_error'):
                entry.pop(key, None)
            if stores is not None:
                _mark_store_dirty(stores, 'test_configs')
            else:
                _save_json_file(TEST_CONFIGS_FILE, data)
        return

    if kind == 'payment':
        data = stores.get('payments') if isinstance(stores, dict) else _load_json_file(PAYMENTS_FILE, {})
        entry = data.get(ref[1]) if isinstance(data, dict) else None
        if isinstance(entry, dict):
            for key in ('cleanup_deleted_at', 'cleanup_delete_result', 'cleanup_error'):
                entry.pop(key, None)
            if stores is not None:
                _mark_store_dirty(stores, 'payments')
            else:
                _save_json_file(PAYMENTS_FILE, data)
        return

    if kind == 'reseller':
        data = stores.get('resellers') if isinstance(stores, dict) else _load_json_file(RESELLERS_FILE, {})
        reseller = data.get(ref[1]) if isinstance(data, dict) else None
        configs = reseller.get('configs', []) if isinstance(reseller, dict) else []
        if isinstance(configs, list) and 0 <= ref[2] < len(configs) and isinstance(configs[ref[2]], dict):
            for key in ('cleanup_deleted_at', 'cleanup_delete_result', 'cleanup_error'):
                configs[ref[2]].pop(key, None)
            if stores is not None:
                _mark_reseller_ref_dirty(stores, ref)
            else:
                _save_reseller_cleanup_metadata(data, {ref})


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


def _find_user_in_records(users, username):
    target = str(username or '').strip().lower()
    if not target:
        return None
    for record_username, user_data in _iter_named_user_records(users):
        if str(record_username or '').strip().lower() == target:
            return user_data
    return None


def _new_server_lookup_context():
    return {
        'checked_any': False,
        'unavailable': False,
        'servers': {},
        'exact': {},
        'usernames': {},
    }


def _remember_server_users(context, server_id, client, users):
    server_id = str(server_id or getattr(client, 'server_id', None) or 'primary')
    server_key = server_id.lower()
    context['checked_any'] = True
    context['servers'][server_key] = {
        'server_id': server_id,
        'client': client,
        'available': users is not None,
    }
    if users is None:
        context['unavailable'] = True
        return

    for username, user_data in _iter_named_user_records(users):
        username = str(username or '').strip()
        if not username:
            continue
        username_key = username.lower()
        context['exact'][_state_key(server_id, username).lower()] = (client, user_data)
        context['usernames'].setdefault(username_key, []).append((server_id, client, user_data))


def _lookup_user_from_context(context, username, preferred_server_id=None):
    if not isinstance(context, dict):
        return None, None, None

    username = str(username or '').strip()
    if not username:
        return None, None, 'missing'

    if preferred_server_id:
        server_state = context.get('servers', {}).get(str(preferred_server_id).lower())
        if not server_state:
            return None, None, 'unavailable'
        client = server_state.get('client')
        if not server_state.get('available'):
            return client, None, 'unavailable'
        match = context.get('exact', {}).get(_state_key(preferred_server_id, username).lower())
        if match:
            return match[0], match[1], 'found'
        return client, None, 'missing'

    matches = context.get('usernames', {}).get(username.lower()) or []
    if matches:
        _server_id, client, user_data = matches[0]
        return client, user_data, 'found'

    if context.get('unavailable') or not context.get('checked_any'):
        return None, None, 'unavailable'
    return None, None, 'missing'


def discover_cleanup_candidates(include_already_missing=False, stores=None):
    candidates = []

    test_configs = stores.get('test_configs') if isinstance(stores, dict) else _load_json_file(TEST_CONFIGS_FILE, {})
    if isinstance(test_configs, dict):
        for telegram_id, entry in test_configs.items():
            if not isinstance(entry, dict):
                continue
            if _is_deleted_record(entry) and not (include_already_missing and _is_already_missing_record(entry)):
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

    payments = stores.get('payments') if isinstance(stores, dict) else _load_json_file(PAYMENTS_FILE, {})
    if isinstance(payments, dict):
        for payment_id, record in payments.items():
            if not _completed_payment(record):
                continue
            if _is_deleted_record(record) and not (include_already_missing and _is_already_missing_record(record)):
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

    resellers = stores.get('resellers') if isinstance(stores, dict) else _load_json_file(RESELLERS_FILE, {})
    if isinstance(resellers, dict):
        for reseller_id, reseller_data in resellers.items():
            if not isinstance(reseller_data, dict):
                continue
            configs = reseller_data.get('configs', [])
            if not isinstance(configs, list):
                continue
            for index, config in enumerate(configs):
                if not isinstance(config, dict):
                    continue
                if _is_deleted_record(config) and not (include_already_missing and _is_already_missing_record(config)):
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


def _iter_server_user_snapshots(multi_api):
    fetch_users = getattr(multi_api, '_fetch_users_for_servers', None)
    if callable(fetch_users):
        try:
            for index, entry in enumerate(fetch_users(include_disabled=True)):
                if not isinstance(entry, dict):
                    continue
                yield index, entry.get('server'), entry.get('client'), entry.get('users')
            return
        except Exception:
            pass

    try:
        client_iter = multi_api.iter_clients(include_disabled=True)
    except Exception:
        return

    for index, (server, client) in enumerate(client_iter):
        try:
            users = client.get_users()
        except Exception:
            users = None
        yield index, server, client, users


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


def discover_matching_cleanup_candidates(server_candidates, include_already_missing=False, local_candidates=None):
    usernames, exact_keys, exact_candidates, username_candidates = _server_candidate_match_sets(server_candidates)
    if not usernames:
        return []
    matched = []
    candidates = (
        local_candidates
        if local_candidates is not None
        else discover_cleanup_candidates(include_already_missing=include_already_missing)
    )
    for candidate in candidates:
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


def discover_already_missing_cleanup_candidates(state):
    candidates = []
    if not isinstance(state, dict):
        return candidates

    for entry in state.values():
        if not isinstance(entry, dict) or entry.get('cleanup_status') != 'already_missing':
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
            '_repair_already_missing': True,
        })

    return candidates


def _scan_server_cleanup_candidates(multi_api):
    candidates = []
    lookup_context = _new_server_lookup_context()
    if multi_api is None:
        return candidates, lookup_context

    for index, server, client, users in _iter_server_user_snapshots(multi_api):
        if client is None:
            continue
        server_id = str(
            (server or {}).get('id')
            or getattr(client, 'server_id', None)
            or f'server{index + 1}'
        )
        _remember_server_users(lookup_context, server_id, client, users)
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

    return candidates, lookup_context


def discover_server_cleanup_candidates(multi_api):
    candidates, _lookup_context = _scan_server_cleanup_candidates(multi_api)
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


def _update_candidate_record(candidate, fields, stores=None):
    ref = candidate.get('_record_ref') or ()
    if not ref:
        return

    kind = ref[0]
    if kind == 'test':
        data = stores.get('test_configs') if isinstance(stores, dict) else _load_json_file(TEST_CONFIGS_FILE, {})
        entry = data.get(ref[1]) if isinstance(data, dict) else None
        if isinstance(entry, dict):
            _apply_fields(entry, fields)
            if stores is not None:
                _mark_store_dirty(stores, 'test_configs')
            else:
                _save_json_file(TEST_CONFIGS_FILE, data)
        return

    if kind == 'payment':
        data = stores.get('payments') if isinstance(stores, dict) else _load_json_file(PAYMENTS_FILE, {})
        entry = data.get(ref[1]) if isinstance(data, dict) else None
        if isinstance(entry, dict):
            _apply_fields(entry, fields)
            if stores is not None:
                _mark_store_dirty(stores, 'payments')
            else:
                _save_json_file(PAYMENTS_FILE, data)
        return

    if kind == 'reseller':
        data = stores.get('resellers') if isinstance(stores, dict) else _load_json_file(RESELLERS_FILE, {})
        reseller = data.get(ref[1]) if isinstance(data, dict) else None
        configs = reseller.get('configs', []) if isinstance(reseller, dict) else []
        if isinstance(configs, list) and 0 <= ref[2] < len(configs) and isinstance(configs[ref[2]], dict):
            _apply_fields(configs[ref[2]], fields)
            if stores is not None:
                _mark_reseller_ref_dirty(stores, ref)
            else:
                _save_reseller_cleanup_metadata(data, {ref})


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
        user_data = _find_user_in_records(users, username)
        if user_data is not None:
            return client, user_data, 'found'
        return client, None, 'missing'

    for _, client in multi_api.iter_clients(include_disabled=True):
        checked_any = True
        user_data = client.get_user(username)
        if user_data is not None:
            return client, user_data, 'found'
        users = client.get_users()
        if users is None:
            unavailable = True
            continue
        user_data = _find_user_in_records(users, username)
        if user_data is not None:
            return client, user_data, 'found'

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
        markup = None
        try:
            from utils.edit_plans import load_plans
            from utils.renewal import find_customer_renewal_offer, find_reseller_renewal_offer

            plans = load_plans()
            if source == 'customer':
                offer = find_customer_renewal_offer(
                    candidate.get('telegram_user_id'),
                    candidate.get('username'),
                    candidate.get('_api_client'),
                    candidate.get('_user_data'),
                    plans,
                    server_id=candidate.get('server_id'),
                )
                if offer.get('eligible'):
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(
                        get_button_text(language, "renew_plan") or "Renew Plan",
                        callback_data=f"renew_plan:{offer['token']}"
                    ))
            elif source == 'reseller_customer':
                ref = candidate.get('_record_ref') or ()
                if len(ref) >= 3 and ref[0] == 'reseller':
                    offer = find_reseller_renewal_offer(
                        candidate.get('reseller_id'),
                        int(ref[2]),
                        candidate.get('_api_client'),
                        candidate.get('_user_data'),
                        plans,
                    )
                    if offer.get('eligible'):
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton(
                            get_button_text(language, "renew_plan") or "Renew Plan",
                            callback_data=f"reseller:renew:{offer['token']}"
                        ))
        except Exception as e:
            print(f"Failed to build renewal cleanup action for {candidate.get('username')}: {e}")

        bot.send_message(int(recipient_id), message, parse_mode='Markdown', reply_markup=markup)
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


def _manual_review_entry(candidate, now_value, last_state=None):
    entry = {
        'username': candidate.get('username'),
        'server_id': candidate.get('server_id') or 'primary',
        'source': 'server_user',
        'first_seen_at': now_value,
        'last_checked_at': now_value,
        'cleanup_status': 'manual_review',
        'last_state': last_state,
    }
    for key in ('manual_review_reason', 'review_note', 'payment_id', 'keeper_username'):
        if candidate.get(key):
            entry[key] = candidate.get(key)
    return entry


def _is_duplicate_payment_manual_review(entry):
    return (
        isinstance(entry, dict)
        and entry.get('cleanup_status') == 'manual_review'
        and entry.get('manual_review_reason') == 'duplicate_payment'
    )


def _convert_server_user_to_manual_review(entry, now_value):
    entry['cleanup_status'] = 'manual_review'
    entry.setdefault('first_seen_at', entry.get('notified_at') or now_value)
    entry['last_checked_at'] = now_value
    entry.pop('delete_after', None)
    entry.pop('notification_error', None)
    entry.pop('notified_at', None)


def _mark_renewed(state, key, candidate, now_value, last_state=None):
    entry = state.setdefault(key, {})
    entry.update({
        'username': candidate.get('username'),
        'server_id': candidate.get('server_id') or entry.get('server_id') or 'primary',
        'source': candidate.get('source') or entry.get('source'),
        'telegram_user_id': candidate.get('telegram_user_id') or entry.get('telegram_user_id'),
        'reseller_id': candidate.get('reseller_id') or entry.get('reseller_id'),
        'cleanup_status': 'renewed',
        'reviewed_at': now_value,
        'last_checked_at': now_value,
        'last_state': last_state,
    })


def _mark_deleted(state, key, candidate, status, now_value, last_state=None, delete_result=None, stores=None):
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
    _update_candidate_record(candidate, fields, stores=stores)


def run_expired_user_cleanup(grace_hours=24, now=None, multi_api=None):
    now = now or datetime.now()
    now_value = _now_str(now)
    grace_delta = timedelta(hours=grace_hours)

    with _cleanup_lock:
        state = _load_json_file(STATE_FILE, {})
        if not isinstance(state, dict):
            state = {}

        multi_api = multi_api or MultiServerAPI()
        record_stores = _load_cleanup_record_stores()
        server_candidates, lookup_context = _scan_server_cleanup_candidates(multi_api)
        state_candidates = discover_state_cleanup_candidates(state)
        already_missing_candidates = discover_already_missing_cleanup_candidates(state)
        local_candidates = discover_cleanup_candidates(
            include_already_missing=True,
            stores=record_stores,
        )
        candidates = _merge_cleanup_candidates(
            discover_matching_cleanup_candidates(
                _merge_cleanup_candidates(server_candidates, state_candidates, already_missing_candidates),
                include_already_missing=True,
                local_candidates=local_candidates,
            ),
            state_candidates,
            already_missing_candidates,
            server_candidates,
        )

        for candidate in candidates:
            username = candidate.get('username')
            key = _state_key(candidate.get('server_id'), username)
            entry = state.get(key) if isinstance(state.get(key), dict) else None
            if entry and entry.get('source') == 'server_user' and entry.get('cleanup_status') == 'notified':
                _convert_server_user_to_manual_review(entry, now_value)
            if entry and entry.get('cleanup_status') == 'deleted':
                continue

            if candidate.get('_lookup_status') == 'found':
                api_client = candidate.get('_api_client')
                user_data = candidate.get('_user_data')
                lookup_status = 'found'
            else:
                api_client, user_data, lookup_status = _lookup_user_from_context(
                    lookup_context,
                    username,
                    preferred_server_id=candidate.get('server_id'),
                )
                if lookup_status is None:
                    api_client, user_data, lookup_status = _get_user_lookup(
                        multi_api,
                        username,
                        preferred_server_id=candidate.get('server_id'),
                    )

            if lookup_status == 'unavailable':
                if entry:
                    if entry.get('cleanup_status') == 'already_missing':
                        entry['cleanup_error'] = 'server_unavailable'
                        entry['last_checked_at'] = now_value
                        continue
                    if entry.get('cleanup_status') != 'manual_review':
                        entry['cleanup_status'] = 'server_unavailable'
                    entry['cleanup_error'] = 'server_unavailable'
                    entry['last_checked_at'] = now_value
                continue

            if lookup_status == 'found' and not is_user_expired(user_data):
                if entry:
                    if _is_duplicate_payment_manual_review(entry):
                        entry['last_state'] = capture_last_state(user_data, now=now)
                        entry['last_checked_at'] = now_value
                        entry.pop('cleanup_error', None)
                        continue
                    if entry.get('cleanup_status') == 'manual_review':
                        _mark_renewed(state, key, candidate, now_value, last_state=capture_last_state(user_data, now=now))
                    else:
                        state.pop(key, None)
                        _update_candidate_record(
                            candidate,
                            {'cleanup_status': 'renewed', 'cleanup_error': None},
                            stores=record_stores,
                        )
                continue

            if lookup_status == 'missing':
                if entry and entry.get('cleanup_status') == 'already_missing':
                    entry['last_checked_at'] = now_value
                    continue
                _mark_deleted(
                    state,
                    key,
                    candidate,
                    'already_missing',
                    now_value,
                    last_state=entry.get('last_state') if entry else None,
                    delete_result='already_missing',
                    stores=record_stores,
                )
                continue

            if not entry:
                last_state = capture_last_state(user_data, now=now) if lookup_status == 'found' else None
                if candidate.get('source') == 'server_user':
                    state[key] = _manual_review_entry(candidate, now_value, last_state=last_state)
                    continue
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
                    stores=record_stores,
                )
                continue

            if entry.get('cleanup_status') == 'manual_review':
                entry['last_state'] = capture_last_state(user_data, now=now) if lookup_status == 'found' else entry.get('last_state')
                entry['last_checked_at'] = now_value
                entry.pop('cleanup_error', None)
                continue

            if entry.get('source') == 'server_user' and candidate.get('source') == 'server_user':
                entry.update(_manual_review_entry(
                    candidate,
                    now_value,
                    last_state=capture_last_state(user_data, now=now) if lookup_status == 'found' else entry.get('last_state'),
                ))
                continue

            notified_at = _parse_time(entry.get('notified_at'))
            delete_after = _parse_time(entry.get('delete_after'))
            if delete_after is None and notified_at is not None:
                delete_after = notified_at + grace_delta
                entry['delete_after'] = delete_after.strftime(TIMESTAMP_FORMAT)

            if delete_after is None or now < delete_after:
                entry['cleanup_status'] = 'notified'
                entry['last_checked_at'] = now_value
                if entry.get('delete_result') == 'already_missing':
                    last_state = capture_last_state(user_data, now=now)
                    entry['last_state'] = last_state
                    _clear_state_delete_metadata(entry)
                    _clear_candidate_delete_metadata(candidate, stores=record_stores)
                    _update_candidate_record(
                        candidate,
                        _metadata_fields('notified', now_value, last_state=last_state),
                        stores=record_stores,
                    )
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
                    stores=record_stores,
                )
                continue

            _mark_deleted(state, key, candidate, 'deleted', now_value, last_state=last_state, delete_result='deleted', stores=record_stores)

        _save_dirty_cleanup_record_stores(record_stores)
        _save_json_file(STATE_FILE, state)
        return state


def run_expired_user_cleanup_with_metadata(grace_hours=24, now=None, multi_api=None):
    started_at = now or datetime.now()
    metadata = _load_cleanup_schedule_metadata()
    metadata.update({
        'last_started_at': _now_str(started_at),
    })
    _save_cleanup_schedule_metadata(metadata)

    try:
        state = run_expired_user_cleanup(grace_hours=grace_hours, now=now, multi_api=multi_api)
    except Exception as e:
        finished_at = now or datetime.now()
        metadata = _load_cleanup_schedule_metadata()
        metadata.update({
            'last_finished_at': _now_str(finished_at),
            'last_error': str(e),
        })
        _save_cleanup_schedule_metadata(metadata)
        raise

    finished_at = now or datetime.now()
    metadata = _load_cleanup_schedule_metadata()
    metadata.update({
        'last_finished_at': _now_str(finished_at),
        'last_success_at': _now_str(finished_at),
        'last_error': None,
    })
    _save_cleanup_schedule_metadata(metadata)
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
    review_status = record.get('review_status')
    review_line = f"\n   Review: `{_escape_markdown(review_status)}`" if review_status else ""
    manual_reason = record.get('manual_review_reason')
    manual_reason_line = f"\n   Manual reason: `{_escape_markdown(manual_reason)}`" if manual_reason else ""
    review_note = record.get('review_note')
    review_note_line = f"\n   Note: {_escape_markdown(review_note)}" if review_note else ""
    return (
        f"{index}. `{username}` | `{server_id}` | {source}\n"
        f"   Status: *{_escape_markdown(status)}* | Time: `{_escape_markdown(delete_time)}`\n"
        f"   Reason: {reason}"
        f"{review_line}"
        f"{manual_reason_line}"
        f"{review_note_line}"
    )


def _paginate_records(records, page):
    total_pages = max(1, (len(records) + ADMIN_CLEANUP_PAGE_SIZE - 1) // ADMIN_CLEANUP_PAGE_SIZE)
    page = max(0, min(_safe_int(page, 0) or 0, total_pages - 1))
    start = page * ADMIN_CLEANUP_PAGE_SIZE
    return records[start:start + ADMIN_CLEANUP_PAGE_SIZE], total_pages, page


def _build_admin_cleanup_text(language, filter_key='pending', page=0, now=None):
    filter_key = _normalize_admin_cleanup_filter(filter_key)
    counts = get_expired_cleanup_counts(now=now)
    records = get_expired_cleanup_records(filter_key=filter_key, now=now)
    page_records, total_pages, page = _paginate_records(records, page)
    title = _get_admin_cleanup_text(language, "admin_expired_cleanup_title", "🧹 *Expired Cleanup*")
    label = _status_label(filter_key)
    description = ADMIN_CLEANUP_FILTER_DESCRIPTIONS.get(filter_key, 'Records in the selected cleanup view.')
    count_lines = [
        f"Manual Review: *{counts.get('manual_review', 0)}* | Duplicate: *{counts.get('duplicate_payment', 0)}* | Pending: *{counts.get('pending', 0)}* | Due: *{counts.get('due', 0)}*",
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
        f"View: *{_escape_markdown(label)}* | Page *{page + 1}/{total_pages}*\n"
        f"{_escape_markdown(description)}\n\n"
        f"{rows}"
    )


def _filter_button_label(filter_key, counts):
    return f"{_status_label(filter_key)} ({counts.get(filter_key, 0)})"


def _manual_review_callback_data(action, filter_key, record_id):
    action_code = 'rd' if action == 'review_delete' else 'rk'
    filter_code = ADMIN_CLEANUP_REVIEW_FILTER_CODES.get(
        _normalize_admin_cleanup_filter(filter_key),
        ADMIN_CLEANUP_REVIEW_FILTER_CODES['manual_review'],
    )
    return f"aec:{action_code}:{filter_code}:{record_id}"


def _parse_manual_review_callback_data(data):
    parts = str(data or '').split(":")
    if len(parts) == 4 and parts[0] == "aec":
        action = ADMIN_CLEANUP_REVIEW_ACTIONS.get(parts[1])
        filter_key = ADMIN_CLEANUP_REVIEW_FILTERS_BY_CODE.get(parts[2])
        if action and filter_key and parts[3]:
            return action, filter_key, parts[3]
        return None

    if (
        len(parts) in {3, 4}
        and parts[0] == "admin_expired_cleanup"
        and parts[1] in {"review_keep", "review_delete"}
    ):
        filter_key = _normalize_admin_cleanup_filter(parts[2]) if len(parts) == 4 else "manual_review"
        record_id = parts[3] if len(parts) == 4 else parts[2]
        if record_id:
            return parts[1], filter_key, record_id

    return None


def _build_admin_cleanup_markup(filter_key='pending', page=0, now=None):
    filter_key = _normalize_admin_cleanup_filter(filter_key)
    records = get_expired_cleanup_records(filter_key=filter_key, now=now)
    page_records, total_pages, page = _paginate_records(records, page)
    counts = get_expired_cleanup_counts(now=now)
    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton(_filter_button_label('manual_review', counts), callback_data="admin_expired_cleanup:list:manual_review:0"),
        types.InlineKeyboardButton(_filter_button_label('duplicate_payment', counts), callback_data="admin_expired_cleanup:list:duplicate_payment:0"),
    )
    markup.add(
        types.InlineKeyboardButton(_filter_button_label('pending', counts), callback_data="admin_expired_cleanup:list:pending:0"),
        types.InlineKeyboardButton(_filter_button_label('due', counts), callback_data="admin_expired_cleanup:list:due:0"),
    )
    markup.add(
        types.InlineKeyboardButton(_filter_button_label('deleted', counts), callback_data="admin_expired_cleanup:list:deleted:0"),
        types.InlineKeyboardButton(_filter_button_label('already_missing', counts), callback_data="admin_expired_cleanup:list:already_missing:0"),
    )
    markup.add(
        types.InlineKeyboardButton(_filter_button_label('delete_failed', counts), callback_data="admin_expired_cleanup:list:delete_failed:0"),
        types.InlineKeyboardButton(_filter_button_label('server_unavailable', counts), callback_data="admin_expired_cleanup:list:server_unavailable:0"),
    )
    markup.add(
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

    if filter_key in {'manual_review', 'duplicate_payment'}:
        for index, record in enumerate(page_records, start=1):
            record_id = _state_record_id(record.get('state_key'))
            username = str(record.get('username') or 'N/A')
            label = username if len(username) <= 18 else username[:15] + "..."
            markup.add(
                types.InlineKeyboardButton(
                    f"Delete {index}",
                    callback_data=_manual_review_callback_data('review_delete', filter_key, record_id),
                ),
                types.InlineKeyboardButton(
                    f"Keep {index}: {label}",
                    callback_data=_manual_review_callback_data('review_keep', filter_key, record_id),
                ),
            )

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
        run_expired_user_cleanup_with_metadata(grace_hours=grace_hours)
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


def _render_admin_expired_cleanup(chat_id, message_id, admin_id, filter_key='pending', page=0):
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


def _handle_manual_review_keep(record_id, admin_id):
    now_value = _now_str()
    with _cleanup_lock:
        state_key, entry, state = _find_state_key_by_record_id(record_id)
        if not state_key or not entry:
            return "Review record not found."
        if entry.get('cleanup_status') != 'manual_review':
            return "Record is no longer in manual review."

        entry['review_status'] = 'kept'
        entry['reviewed_at'] = now_value
        entry['reviewed_by'] = str(admin_id)
        entry['last_checked_at'] = now_value
        _save_json_file(STATE_FILE, state)
        return "Kept for later review."


def _handle_manual_review_delete(record_id):
    now_value = _now_str()
    with _cleanup_lock:
        state_key, entry, state = _find_state_key_by_record_id(record_id)
        if not state_key or not entry:
            return "Review record not found."
        if entry.get('cleanup_status') != 'manual_review':
            return "Record is no longer in manual review."

        candidate = _candidate_from_state_entry(entry)
        multi_api = MultiServerAPI()
        api_client, user_data, lookup_status = _get_user_lookup(
            multi_api,
            candidate.get('username'),
            preferred_server_id=candidate.get('server_id'),
        )

        if lookup_status == 'unavailable':
            entry['cleanup_error'] = 'server_unavailable'
            entry['last_checked_at'] = now_value
            _save_json_file(STATE_FILE, state)
            return "Server unavailable. Try again later."

        if lookup_status == 'missing':
            _mark_deleted(
                state,
                state_key,
                candidate,
                'already_missing',
                now_value,
                last_state=entry.get('last_state'),
                delete_result='already_missing',
            )
            _save_json_file(STATE_FILE, state)
            return "User is already missing."

        last_state = capture_last_state(user_data, now=datetime.now())
        if not is_user_expired(user_data):
            _mark_renewed(state, state_key, candidate, now_value, last_state=last_state)
            _save_json_file(STATE_FILE, state)
            return "User is no longer expired."

        delete_result = api_client.delete_user(candidate.get('username')) if api_client else None
        if delete_result is None:
            entry['cleanup_status'] = 'delete_failed'
            entry['cleanup_error'] = 'delete_failed'
            entry['last_checked_at'] = now_value
            entry['last_state'] = last_state
            _save_json_file(STATE_FILE, state)
            return "Delete failed."

        _mark_deleted(state, state_key, candidate, 'deleted', now_value, last_state=last_state, delete_result='deleted')
        _save_json_file(STATE_FILE, state)
        return "User deleted."


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '🧹 Expired Cleanup')
def admin_expired_cleanup_menu(message):
    language = get_user_language(message.from_user.id)
    bot.reply_to(
        message,
        _build_admin_cleanup_text(language, filter_key='pending', page=0),
        reply_markup=_build_admin_cleanup_markup(filter_key='pending', page=0),
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith(("admin_expired_cleanup:", "aec:")))
def handle_admin_expired_cleanup(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Unauthorized", show_alert=True)
        return

    parts = call.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    review_callback = _parse_manual_review_callback_data(call.data)
    if review_callback:
        review_action, return_filter, record_id = review_callback
        if review_action == "review_keep":
            message = _handle_manual_review_keep(record_id, call.from_user.id)
        else:
            message = _handle_manual_review_delete(record_id)
        _render_admin_expired_cleanup(call.message.chat.id, call.message.message_id, call.from_user.id, return_filter, 0)
        bot.answer_callback_query(call.id, message)
        return

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
