import hashlib
import json
import os
from datetime import datetime


PAYMENTS_FILE = '/etc/dijiq/core/scripts/telegrambot/payments.json'
RESELLERS_FILE = '/etc/dijiq/core/scripts/telegrambot/resellers.json'
STATE_FILE = '/etc/dijiq/core/scripts/telegrambot/expired_user_cleanup.json'

GB_BYTES = 1024 ** 3
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
PAID_STATUSES = {'completed', 'paid', 'succeeded'}
DELETE_RESULTS = {'deleted', 'already_missing'}


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


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'y'}
    return bool(value)


def _safe_bytes(value):
    return max(0, _safe_int(value, 0) or 0)


def _gb_from_bytes(byte_count):
    if byte_count is None:
        return None
    return round(float(byte_count) / GB_BYTES, 3)


def _now_str():
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _state_key(server_id, username):
    return f"{server_id or 'primary'}:{username}"


def _token(*parts):
    raw = ':'.join(str(part or '') for part in parts)
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def _escape_markdown(value):
    text = str(value if value is not None else 'N/A')
    for char in ('\\', '`', '*', '_', '[', ']'):
        text = text.replace(char, f"\\{char}")
    return text


def capture_user_state(user_data):
    user_data = user_data or {}
    upload_bytes = _safe_bytes(user_data.get('upload_bytes'))
    download_bytes = _safe_bytes(user_data.get('download_bytes'))
    max_download_bytes = _safe_bytes(user_data.get('max_download_bytes'))
    used_bytes = upload_bytes + download_bytes
    remaining_bytes = None
    if max_download_bytes > 0:
        remaining_bytes = max(0, max_download_bytes - used_bytes)

    return {
        'captured_at': _now_str(),
        'days_remaining': _safe_int(user_data.get('expiration_days')),
        'gb_remaining': _gb_from_bytes(remaining_bytes),
        'gb_limit': _gb_from_bytes(max_download_bytes) if max_download_bytes > 0 else None,
        'gb_used': _gb_from_bytes(used_bytes),
        'blocked': bool(user_data.get('blocked', False)),
        'status': user_data.get('status'),
        'upload_bytes': upload_bytes,
        'download_bytes': download_bytes,
        'max_download_bytes': max_download_bytes,
    }


def expected_after_state(plan_gb, days):
    return {
        'days_remaining': _safe_int(days, 0),
        'gb_remaining': round(_safe_float(plan_gb), 3),
        'gb_limit': round(_safe_float(plan_gb), 3),
        'gb_used': 0.0,
        'blocked': False,
        'status': 'active',
        'upload_bytes': 0,
        'download_bytes': 0,
        'max_download_bytes': int(round(_safe_float(plan_gb) * GB_BYTES)),
    }


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
        used_bytes = _safe_bytes(user_data.get('upload_bytes')) + _safe_bytes(user_data.get('download_bytes'))
        if used_bytes >= max_download_bytes:
            return True

    return False


def _is_deleted_record(record):
    if not isinstance(record, dict):
        return True
    return (
        record.get('cleanup_status') in DELETE_RESULTS
        or record.get('cleanup_delete_result') in DELETE_RESULTS
        or bool(record.get('cleanup_deleted_at'))
        or bool(record.get('removed_from_vpn'))
    )


def _is_paid_customer_record(record):
    if not isinstance(record, dict):
        return False
    if record.get('type') == 'settlement' or record.get('plan_gb') == 'Settlement':
        return False
    return str(record.get('status', '')).lower() in PAID_STATUSES


def _record_username(record):
    return str(record.get('renewal_username') or record.get('username') or '').strip()


def _record_server_id(record):
    return record.get('renewal_server_id') or record.get('server_id')


def customer_renewal_token(user_id, record_id, username, server_id):
    return _token('customer', user_id, record_id, server_id or 'primary', username)


def reseller_renewal_token(reseller_id, config_index, username, server_id):
    return _token('reseller', reseller_id, config_index, server_id or 'primary', username)


def _plan_for_record(record, plans, source):
    if not isinstance(record, dict) or not isinstance(plans, dict):
        return None, 'renewal_ineligible_plan_missing'

    plan_gb = str(record.get('plan_gb') if record.get('plan_gb') is not None else record.get('gb', '')).strip()
    if plan_gb not in plans:
        return None, 'renewal_ineligible_plan_missing'

    plan = plans.get(plan_gb) or {}
    target = plan.get('target', 'both')
    if source == 'customer' and target == 'reseller':
        return None, 'renewal_ineligible_plan_mismatch'
    if source == 'reseller_customer' and target == 'customer':
        return None, 'renewal_ineligible_plan_mismatch'

    if _safe_int(record.get('days')) != _safe_int(plan.get('days')):
        return None, 'renewal_ineligible_plan_mismatch'

    if _safe_bool(record.get('unlimited', False)) != _safe_bool(plan.get('unlimited', False)):
        return None, 'renewal_ineligible_plan_mismatch'

    return plan, None


def _live_quota_matches_plan(user_data, plan_gb):
    max_download_bytes = _safe_bytes((user_data or {}).get('max_download_bytes'))
    if max_download_bytes <= 0:
        return False
    live_gb = max_download_bytes / GB_BYTES
    return abs(live_gb - _safe_float(plan_gb)) <= 0.01


def _build_offer(record, source, username, server_id, api_client, user_data, plans, extra=None):
    if not api_client or not user_data:
        return {
            'eligible': False,
            'reason': 'renewal_ineligible_missing',
            'source': source,
            'username': username,
            'server_id': server_id,
        }

    if not is_user_expired(user_data):
        return {
            'eligible': False,
            'reason': 'renewal_ineligible_not_expired',
            'source': source,
            'username': username,
            'server_id': server_id,
            'before_state': capture_user_state(user_data),
        }

    plan, reason = _plan_for_record(record, plans, source)
    if reason:
        return {
            'eligible': False,
            'reason': reason,
            'source': source,
            'username': username,
            'server_id': server_id,
            'before_state': capture_user_state(user_data),
        }

    plan_gb = str(record.get('plan_gb') if record.get('plan_gb') is not None else record.get('gb'))
    if not _live_quota_matches_plan(user_data, plan_gb):
        return {
            'eligible': False,
            'reason': 'renewal_ineligible_plan_mismatch',
            'source': source,
            'username': username,
            'server_id': server_id,
            'before_state': capture_user_state(user_data),
        }

    price = _safe_float(plan.get('price'))
    if source == 'reseller_customer':
        price = price * 0.8

    offer = {
        'eligible': True,
        'source': source,
        'username': username,
        'server_id': server_id or getattr(api_client, 'server_id', None) or 'primary',
        'api_client': api_client,
        'plan_gb': plan_gb,
        'days': _safe_int(plan.get('days'), 0),
        'unlimited': _safe_bool(plan.get('unlimited', False)),
        'price': price,
        'full_price': _safe_float(plan.get('price')),
        'plan': plan,
        'before_state': capture_user_state(user_data),
        'expected_after_state': expected_after_state(plan_gb, plan.get('days')),
    }
    if extra:
        offer.update(extra)
    return offer


def _matching_customer_records(user_id, username=None, server_id=None, payments=None):
    payments = payments if payments is not None else _load_json_file(PAYMENTS_FILE, {})
    records = []
    for record_id, record in (payments or {}).items():
        if not _is_paid_customer_record(record) or _is_deleted_record(record):
            continue
        if str(record.get('user_id')) != str(user_id):
            continue
        record_username = _record_username(record)
        if not record_username:
            continue
        if username and record_username.lower() != str(username).strip().lower():
            continue
        record_server_id = _record_server_id(record)
        if server_id and record_server_id and str(record_server_id) != str(server_id):
            continue
        records.append((str(record_id), record))

    records.sort(key=lambda item: str(item[1].get('updated_at') or item[1].get('created_at') or ''), reverse=True)
    return records


def find_customer_renewal_offer(user_id, username, api_client, user_data, plans, payments=None, server_id=None):
    first_ineligible_offer = None
    for record_id, record in _matching_customer_records(user_id, username=username, server_id=server_id, payments=payments):
        record_username = _record_username(record)
        record_server_id = _record_server_id(record) or server_id or getattr(api_client, 'server_id', None)
        token = customer_renewal_token(user_id, record_id, record_username, record_server_id)
        offer = _build_offer(
            record,
            'customer',
            record_username,
            record_server_id,
            api_client,
            user_data,
            plans,
            extra={
                'token': token,
                'base_record_id': record_id,
                'base_record': record,
            },
        )
        if offer.get('eligible'):
            return offer
        if first_ineligible_offer is None:
            first_ineligible_offer = offer
    if first_ineligible_offer:
        return first_ineligible_offer
    return {
        'eligible': False,
        'reason': 'renewal_ineligible_no_record',
        'source': 'customer',
        'username': username,
        'server_id': server_id or getattr(api_client, 'server_id', None),
        'before_state': capture_user_state(user_data),
    }


def resolve_customer_renewal_token(user_id, token, plans, multi_api=None, payments=None):
    from utils.api_client import MultiServerAPI

    multi_api = multi_api or MultiServerAPI()
    payments = payments if payments is not None else _load_json_file(PAYMENTS_FILE, {})
    for record_id, record in _matching_customer_records(user_id, payments=payments):
        username = _record_username(record)
        server_id = _record_server_id(record)
        if customer_renewal_token(user_id, record_id, username, server_id) != token:
            continue
        api_client, user_data = multi_api.find_user(username, preferred_server_id=server_id)
        return _build_offer(
            record,
            'customer',
            username,
            server_id,
            api_client,
            user_data,
            plans,
            extra={
                'token': token,
                'base_record_id': record_id,
                'base_record': record,
            },
        )
    return {'eligible': False, 'reason': 'renewal_ineligible_missing', 'source': 'customer'}


def _iter_reseller_configs(reseller_id, reseller_data=None):
    if reseller_data is None:
        resellers = _load_json_file(RESELLERS_FILE, {})
        reseller_data = resellers.get(str(reseller_id), {})
    configs = reseller_data.get('configs', []) if isinstance(reseller_data, dict) else []
    if not isinstance(configs, list):
        return []
    return [(index, config) for index, config in enumerate(configs) if isinstance(config, dict)]


def find_reseller_renewal_offer(reseller_id, config_index, api_client, user_data, plans, reseller_data=None):
    configs = dict(_iter_reseller_configs(reseller_id, reseller_data=reseller_data))
    config = configs.get(config_index)
    if not config or _is_deleted_record(config):
        return {'eligible': False, 'reason': 'renewal_ineligible_missing', 'source': 'reseller_customer'}

    username = str(config.get('username') or '').strip()
    server_id = config.get('server_id') or getattr(api_client, 'server_id', None)
    token = reseller_renewal_token(reseller_id, config_index, username, server_id)
    return _build_offer(
        config,
        'reseller_customer',
        username,
        server_id,
        api_client,
        user_data,
        plans,
        extra={
            'token': token,
            'reseller_id': str(reseller_id),
            'config_index': config_index,
            'config': config,
        },
    )


def resolve_reseller_renewal_token(reseller_id, token, plans, multi_api=None, reseller_data=None):
    from utils.api_client import MultiServerAPI

    multi_api = multi_api or MultiServerAPI()
    if reseller_data is None:
        resellers = _load_json_file(RESELLERS_FILE, {})
        reseller_data = resellers.get(str(reseller_id), {})

    for config_index, config in _iter_reseller_configs(reseller_id, reseller_data=reseller_data):
        if _is_deleted_record(config):
            continue
        username = str(config.get('username') or '').strip()
        server_id = config.get('server_id')
        if reseller_renewal_token(reseller_id, config_index, username, server_id) != token:
            continue
        api_client, user_data = multi_api.find_user(username, preferred_server_id=server_id)
        return find_reseller_renewal_offer(
            reseller_id,
            config_index,
            api_client,
            user_data,
            plans,
            reseller_data=reseller_data,
        )

    return {'eligible': False, 'reason': 'renewal_ineligible_missing', 'source': 'reseller_customer'}


def customer_payment_metadata(offer):
    return {
        'type': 'renewal',
        'renewal_source': 'customer',
        'renewal_username': offer.get('username'),
        'renewal_server_id': offer.get('server_id'),
        'renewal_base_record_id': offer.get('base_record_id'),
        'renewal_before_state': offer.get('before_state'),
    }


def reseller_renewal_record(offer, before_state, after_state):
    return {
        'timestamp': _now_str(),
        'price': offer.get('price'),
        'gb': offer.get('plan_gb'),
        'days': offer.get('days'),
        'unlimited': offer.get('unlimited', False),
        'before_state': before_state,
        'after_state': after_state,
    }


def _mark_cleanup_state_renewed(username, server_id):
    state = _load_json_file(STATE_FILE, {})
    if not isinstance(state, dict):
        return
    key = _state_key(server_id, username)
    if key in state:
        state.pop(key, None)
        _save_json_file(STATE_FILE, state)


def _mark_payment_record_renewed(record_id, after_state):
    if not record_id:
        return
    payments = _load_json_file(PAYMENTS_FILE, {})
    record = payments.get(str(record_id)) if isinstance(payments, dict) else None
    if not isinstance(record, dict):
        return
    record['cleanup_status'] = 'renewed'
    record['cleanup_error'] = None
    record['cleanup_last_state'] = after_state
    record['updated_at'] = _now_str()
    _save_json_file(PAYMENTS_FILE, payments)


def _execute_reset(username, server_id, plan_record, source, multi_api=None):
    from utils.api_client import MultiServerAPI

    multi_api = multi_api or MultiServerAPI()
    api_client, user_data = multi_api.find_user(username, preferred_server_id=server_id)
    if not api_client or not user_data:
        return {'success': False, 'reason': 'renewal_ineligible_missing'}

    before_state = capture_user_state(user_data)
    if not is_user_expired(user_data):
        return {'success': False, 'reason': 'renewal_ineligible_not_expired', 'before_state': before_state}

    if not _live_quota_matches_plan(user_data, plan_record.get('plan_gb') or plan_record.get('gb')):
        return {'success': False, 'reason': 'renewal_ineligible_plan_mismatch', 'before_state': before_state}

    result = api_client.reset_user(username)
    if result is None:
        return {'success': False, 'reason': 'renewal_reset_failed', 'before_state': before_state}

    after_user = api_client.get_user(username) or user_data
    after_state = capture_user_state(after_user)
    _mark_cleanup_state_renewed(username, server_id or getattr(api_client, 'server_id', None))

    return {
        'success': True,
        'username': username,
        'server_id': server_id or getattr(api_client, 'server_id', None),
        'api_client': api_client,
        'before_state': before_state,
        'after_state': after_state,
        'raw_result': result,
    }


def execute_customer_renewal(payment_record, plans=None, multi_api=None):
    from utils.edit_plans import load_plans

    plans = plans if plans is not None else load_plans()
    username = payment_record.get('renewal_username')
    server_id = payment_record.get('renewal_server_id')
    if not username:
        return {'success': False, 'reason': 'renewal_ineligible_missing'}

    plan, reason = _plan_for_record(payment_record, plans, 'customer')
    if reason:
        return {'success': False, 'reason': reason}

    result = _execute_reset(username, server_id, payment_record, 'customer', multi_api=multi_api)
    if result.get('success'):
        _mark_payment_record_renewed(payment_record.get('renewal_base_record_id'), result.get('after_state'))
    return result


def execute_reseller_renewal(offer, multi_api=None):
    username = offer.get('username')
    server_id = offer.get('server_id')
    if not username:
        return {'success': False, 'reason': 'renewal_ineligible_missing'}
    return _execute_reset(username, server_id, {'gb': offer.get('plan_gb')}, 'reseller_customer', multi_api=multi_api)


def format_state_summary(state):
    if not isinstance(state, dict):
        return "Days remaining: unknown\nUsage: unknown"
    gb_limit = state.get('gb_limit')
    gb_limit_text = "Unlimited" if gb_limit is None else f"{_safe_float(gb_limit):.2f} GB"
    return (
        f"Days remaining: {state.get('days_remaining') if state.get('days_remaining') is not None else 'unknown'}\n"
        f"Usage: {_safe_float(state.get('gb_used')):.2f} / {gb_limit_text}"
    )


def format_renewal_offer(language, offer, include_payment_prompt=True):
    from utils.currency_format import format_usd_amount
    from utils.translations import get_message_text

    before = format_state_summary(offer.get('before_state'))
    after = format_state_summary(offer.get('expected_after_state'))
    payment_prompt = f"\n\n{get_message_text(language, 'select_payment_method')}" if include_payment_prompt else ""
    return get_message_text(language, 'renewal_offer_details').format(
        username=_escape_markdown(offer.get('username')),
        plan_gb=offer.get('plan_gb'),
        days=offer.get('days'),
        price=format_usd_amount(offer.get('price', 0)),
        before=before,
        after=after,
        payment_prompt=payment_prompt,
    )


def format_renewal_success(language, result, plan_gb, days, sub_url=None, ipv4_url=None):
    from utils.translations import get_message_text

    ipv4_info = f"IPv4 URL: `{ipv4_url}`\n\n" if ipv4_url else ""
    return get_message_text(language, 'renewal_success').format(
        username=_escape_markdown(result.get('username')),
        plan_gb=plan_gb,
        days=days,
        before=format_state_summary(result.get('before_state')),
        after=format_state_summary(result.get('after_state')),
        sub_url=sub_url or 'N/A',
        ipv4_info=ipv4_info,
    )
