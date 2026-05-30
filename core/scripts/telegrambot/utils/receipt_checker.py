import os
from dotenv import load_dotenv


TELEGRAM_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))

RECEIPT_TYPE_REGULAR = 'regular'
RECEIPT_TYPE_SETTLEMENT = 'settlement'
VALID_RECEIPT_TYPES = {RECEIPT_TYPE_REGULAR, RECEIPT_TYPE_SETTLEMENT}


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
