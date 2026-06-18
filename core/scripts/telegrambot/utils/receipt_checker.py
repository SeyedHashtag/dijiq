import json
import os
import threading
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv


TELEGRAM_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
CHECKER_SETTLEMENTS_FILE = '/etc/dijiq/core/scripts/telegrambot/checker_settlements.json'

RECEIPT_TYPE_REGULAR = 'regular'
RECEIPT_TYPE_SETTLEMENT = 'settlement'
VALID_RECEIPT_TYPES = {RECEIPT_TYPE_REGULAR, RECEIPT_TYPE_SETTLEMENT}
DEFAULT_RECEIPT_CHECKER_SHARE_PERCENT = 10.0

checker_settlement_lock = threading.RLock()


def reload_receipt_checker_env():
    load_dotenv(TELEGRAM_ENV_PATH, override=True)


def normalize_receipt_types(value):
    if not value:
        return []

    if isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = str(value).replace(';', ',').split(',')

    receipt_types = []
    for item in raw_items:
        normalized = str(item).strip().lower()
        if normalized in VALID_RECEIPT_TYPES and normalized not in receipt_types:
            receipt_types.append(normalized)
    return receipt_types


def get_receipt_checker_user_id():
    reload_receipt_checker_env()
    checker_id = os.getenv('RECEIPT_CHECKER_USER_ID', '').strip()
    if not checker_id:
        return None
    try:
        return int(checker_id)
    except (TypeError, ValueError):
        return None


def get_receipt_checker_types():
    reload_receipt_checker_env()
    return normalize_receipt_types(os.getenv('RECEIPT_CHECKER_TYPES', ''))


def parse_receipt_checker_share_percent(value, default=DEFAULT_RECEIPT_CHECKER_SHARE_PERCENT):
    try:
        percent = float(value)
    except (TypeError, ValueError):
        return float(default)
    if percent < 0 or percent > 100:
        return float(default)
    return float(Decimal(str(percent)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def get_receipt_checker_share_percent():
    reload_receipt_checker_env()
    return parse_receipt_checker_share_percent(
        os.getenv('RECEIPT_CHECKER_SHARE_PERCENT', str(DEFAULT_RECEIPT_CHECKER_SHARE_PERCENT))
    )


def calculate_checker_share_amount(amount, percent=None):
    if percent is None:
        percent = get_receipt_checker_share_percent()
    try:
        amount_decimal = Decimal(str(amount or 0))
        percent_decimal = Decimal(str(percent))
    except Exception:
        return 0.0
    share = amount_decimal * percent_decimal / Decimal('100')
    return float(share.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def calculate_checker_share_amount_toman(amount, percent=None):
    if percent is None:
        percent = get_receipt_checker_share_percent()
    try:
        amount_decimal = Decimal(str(amount or 0))
        percent_decimal = Decimal(str(percent))
    except Exception:
        return 0.0
    share = amount_decimal * percent_decimal / Decimal('100')
    return float(share.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def normalize_toman_amount(amount):
    try:
        return float(Decimal(str(amount or 0)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except Exception:
        return 0.0


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _parse_payment_datetime(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return None


def is_receipt_checker(user_id):
    checker_id = get_receipt_checker_user_id()
    return checker_id is not None and int(user_id) == checker_id


def should_route_to_receipt_checker(receipt_type):
    checker_id = get_receipt_checker_user_id()
    if checker_id is None:
        return False
    return receipt_type in get_receipt_checker_types()


def get_receipt_type_label(receipt_type):
    if receipt_type == RECEIPT_TYPE_SETTLEMENT:
        return 'Reseller Settlement'
    return 'Regular Customer'


def get_card_number_for_receipt_type(receipt_type):
    reload_receipt_checker_env()
    main_card = os.getenv('CARD_TO_CARD_NUMBER', '').strip()
    checker_card = os.getenv('CARD_TO_CARD_CHECKER_NUMBER', '').strip()
    if should_route_to_receipt_checker(receipt_type) and checker_card:
        return checker_card
    return main_card


def load_checker_settlements():
    with checker_settlement_lock:
        try:
            if os.path.exists(CHECKER_SETTLEMENTS_FILE):
                with open(CHECKER_SETTLEMENTS_FILE, 'r') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception:
            pass
        return []


def save_checker_settlements(settlements):
    with checker_settlement_lock:
        os.makedirs(os.path.dirname(CHECKER_SETTLEMENTS_FILE), exist_ok=True)
        with open(CHECKER_SETTLEMENTS_FILE, 'w') as f:
            json.dump(settlements, f, indent=4)


def add_checker_settlement(amount, admin_user_id, stats_snapshot, checker_id=None, open_account_amount=None):
    amount_value = normalize_toman_amount(amount)
    checker_id = checker_id if checker_id is not None else get_receipt_checker_user_id()
    checkpoint = {
        'id': str(uuid.uuid4()),
        'amount_toman': amount_value,
        'currency': 'Tomans',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'admin_user_id': admin_user_id,
        'checker_user_id': checker_id,
        'checker_share_percent_snapshot': stats_snapshot.get('share_percent', get_receipt_checker_share_percent()),
        'approved_total_snapshot_toman': normalize_toman_amount(stats_snapshot.get('approved_total', 0.0)),
        'owed_total_snapshot_toman': normalize_toman_amount(stats_snapshot.get('owed_total', 0.0)),
        'paid_before_toman': normalize_toman_amount(stats_snapshot.get('paid_total', 0.0)),
        'unpaid_before_toman': normalize_toman_amount(stats_snapshot.get('unpaid_total', 0.0)),
        'unpaid_after_toman': max(0.0, normalize_toman_amount(stats_snapshot.get('unpaid_total', 0.0)) - amount_value),
    }
    if open_account_amount is not None:
        checkpoint['open_account_amount_toman'] = normalize_toman_amount(open_account_amount)
    with checker_settlement_lock:
        settlements = load_checker_settlements()
        settlements.append(checkpoint)
        save_checker_settlements(settlements)
    return checkpoint


def get_checker_settlements(checker_id=None):
    settlements = load_checker_settlements()
    if checker_id is None:
        checker_id = get_receipt_checker_user_id()
    if checker_id is None:
        return settlements
    return [
        item for item in settlements
        if str(item.get('checker_user_id')) == str(checker_id)
    ]


def get_checker_paid_total(checker_id=None):
    total = 0.0
    for item in get_checker_settlements(checker_id):
        if item.get('amount_toman') is not None:
            total += _safe_float(item.get('amount_toman', 0.0))
    return normalize_toman_amount(total)


def get_checker_paid_total_since(cutoff_datetime, checker_id=None):
    total = 0.0
    for item in get_checker_settlements(checker_id):
        if item.get('amount_toman') is None:
            continue
        created_at = _parse_payment_datetime(item.get('created_at'))
        if created_at is None or created_at < cutoff_datetime:
            continue
        total += _safe_float(item.get('amount_toman', 0.0))
    return normalize_toman_amount(total)


def get_checker_paid_total_usd_legacy(checker_id=None):
    total = 0.0
    for item in get_checker_settlements(checker_id):
        if item.get('amount_toman') is None:
            total += _safe_float(item.get('amount', 0.0))
    return calculate_checker_share_amount(total, 100)


def _settlement_open_account_amount(item, share_percent):
    if item.get('open_account_amount_toman') is not None:
        return normalize_toman_amount(item.get('open_account_amount_toman'))
    if item.get('amount_toman') is None:
        return 0.0
    percent = item.get('checker_share_percent_snapshot')
    if percent is None:
        percent = share_percent
    return _open_account_from_balance(item.get('amount_toman'), percent)


def get_checker_paid_open_account_total(checker_id=None, share_percent=None):
    if share_percent is None:
        share_percent = get_receipt_checker_share_percent()
    total = 0.0
    for item in get_checker_settlements(checker_id):
        total += _settlement_open_account_amount(item, share_percent)
    return normalize_toman_amount(total)


def _receipt_type_from_record(payment_record):
    receipt_type = payment_record.get('receipt_type')
    if receipt_type:
        return receipt_type
    if payment_record.get('type') == 'settlement' or payment_record.get('plan_gb') == 'Settlement':
        return RECEIPT_TYPE_SETTLEMENT
    return RECEIPT_TYPE_REGULAR


def _open_account_from_balance(balance, share_percent):
    try:
        balance_decimal = Decimal(str(balance or 0))
        percent_decimal = Decimal(str(share_percent))
    except Exception:
        return 0.0
    if percent_decimal <= 0:
        return 0.0
    amount = balance_decimal * Decimal('100') / percent_decimal
    return float(amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def build_receipt_checker_stats(payments, checker_id=None):
    if checker_id is None:
        checker_id = get_receipt_checker_user_id()
    checker_types = get_receipt_checker_types()
    share_percent = get_receipt_checker_share_percent()
    paid_open_account_total = get_checker_paid_open_account_total(checker_id, share_percent)
    stats = {
        'checker_id': checker_id,
        'checker_types': checker_types,
        'share_percent': share_percent,
        'types': {
            RECEIPT_TYPE_REGULAR: {
                'pending': 0,
                'approved': 0,
                'rejected': 0,
                'approved_total': 0.0,
                'checker_owed_total': 0.0,
            },
            RECEIPT_TYPE_SETTLEMENT: {
                'pending': 0,
                'approved': 0,
                'rejected': 0,
                'approved_total': 0.0,
                'checker_owed_total': 0.0,
            },
        },
        'approved_total': 0.0,
        'approved_total_usd': 0.0,
        'converted_approved_total': 0.0,
        'converted_currency': None,
        'converted_currency_mixed': False,
        'owed_total': 0.0,
        'owed_total_usd': 0.0,
        'paid_total': get_checker_paid_total(checker_id),
        'paid_last_30_days': get_checker_paid_total_since(datetime.now() - timedelta(days=30), checker_id),
        'paid_total_usd': get_checker_paid_total_usd_legacy(checker_id),
        'paid_open_account_total': paid_open_account_total,
        'unpaid_total': 0.0,
        'open_account_total': 0.0,
        'unpaid_total_usd': 0.0,
        'legacy_estimated_count': 0,
        'latest_review': None,
    }
    latest_review = None

    for payment_id, record in (payments or {}).items():
        if not record.get('routed_to_checker'):
            continue
        if checker_id is not None:
            try:
                routed_checker_id = int(record.get('receipt_checker_user_id'))
            except (TypeError, ValueError):
                routed_checker_id = None
            if str(routed_checker_id) != str(checker_id):
                continue

        receipt_type = _receipt_type_from_record(record)
        if receipt_type not in stats['types']:
            continue

        item = stats['types'][receipt_type]
        status = record.get('status')
        if status == 'pending_approval':
            item['pending'] += 1
        elif status == 'completed':
            approved_amount_usd = _safe_float(record.get('price', 0.0))
            approved_amount_toman = record.get('checker_accounting_amount_toman')
            if approved_amount_toman is None:
                approved_amount_toman = record.get('converted_amount')
            item['approved'] += 1
            if approved_amount_toman is not None:
                approved_amount_toman = normalize_toman_amount(approved_amount_toman)
                item['approved_total'] += approved_amount_toman
                stats['approved_total'] += approved_amount_toman

                if record.get('checker_share_amount_toman') is not None:
                    owed_amount_toman = normalize_toman_amount(record.get('checker_share_amount_toman', 0.0))
                else:
                    owed_amount_toman = calculate_checker_share_amount_toman(approved_amount_toman, share_percent)
                    stats['legacy_estimated_count'] += 1
                item['checker_owed_total'] += owed_amount_toman
                stats['owed_total'] += owed_amount_toman
            else:
                stats['approved_total_usd'] += approved_amount_usd
                if record.get('checker_share_amount') is not None:
                    owed_amount_usd = _safe_float(record.get('checker_share_amount', 0.0))
                else:
                    owed_amount_usd = calculate_checker_share_amount(approved_amount_usd, share_percent)
                stats['owed_total_usd'] += owed_amount_usd
                stats['legacy_estimated_count'] += 1

            converted_amount = record.get('converted_amount')
            if converted_amount is not None:
                stats['converted_approved_total'] += normalize_toman_amount(converted_amount)
                currency = record.get('converted_currency') or 'Tomans'
                if stats['converted_currency'] is None:
                    stats['converted_currency'] = currency
                elif stats['converted_currency'] != currency:
                    stats['converted_currency_mixed'] = True
        elif status == 'rejected':
            item['rejected'] += 1

        reviewed_at = _parse_payment_datetime(record.get('reviewed_at'))
        if reviewed_at and (latest_review is None or reviewed_at > latest_review[0]):
            latest_review = (reviewed_at, payment_id, record)

    for item in stats['types'].values():
        item['approved_total'] = normalize_toman_amount(item['approved_total'])
        item['checker_owed_total'] = normalize_toman_amount(item['checker_owed_total'])

    stats['approved_total'] = normalize_toman_amount(stats['approved_total'])
    stats['approved_total_usd'] = calculate_checker_share_amount(stats['approved_total_usd'], 100)
    stats['converted_approved_total'] = normalize_toman_amount(stats['converted_approved_total'])
    stats['owed_total'] = normalize_toman_amount(stats['owed_total'])
    stats['owed_total_usd'] = calculate_checker_share_amount(stats['owed_total_usd'], 100)
    stats['unpaid_total'] = max(0.0, normalize_toman_amount(stats['owed_total'] - stats['paid_total']))
    stats['paid_open_account_total'] = normalize_toman_amount(stats['paid_open_account_total'])
    stats['open_account_total'] = max(
        0.0,
        normalize_toman_amount(stats['approved_total'] - stats['paid_open_account_total'])
    )
    stats['unpaid_total_usd'] = max(0.0, calculate_checker_share_amount(stats['owed_total_usd'] - stats['paid_total_usd'], 100))

    if latest_review:
        reviewed_at, payment_id, record = latest_review
        stats['latest_review'] = {
            'reviewed_at': reviewed_at.strftime('%Y-%m-%d %H:%M:%S'),
            'payment_id': payment_id,
            'receipt_type': _receipt_type_from_record(record),
            'reviewed_action': record.get('reviewed_action', 'N/A'),
            'reviewed_by_user_id': record.get('reviewed_by_user_id', 'N/A'),
        }

    return stats


def can_review_receipt(user_id, payment_record, is_admin_user=False):
    if is_admin_user:
        return True

    checker_id = get_receipt_checker_user_id()
    if checker_id is None or int(user_id) != checker_id:
        return False

    receipt_type = payment_record.get('receipt_type')
    if not receipt_type:
        receipt_type = RECEIPT_TYPE_SETTLEMENT if payment_record.get('type') == 'settlement' or payment_record.get('plan_gb') == 'Settlement' else RECEIPT_TYPE_REGULAR

    try:
        routed_checker_id = int(payment_record.get('receipt_checker_user_id'))
    except (TypeError, ValueError):
        routed_checker_id = None

    return (
        bool(payment_record.get('routed_to_checker'))
        and routed_checker_id == checker_id
        and receipt_type in get_receipt_checker_types()
    )
