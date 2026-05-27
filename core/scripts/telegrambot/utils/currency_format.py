from decimal import Decimal, ROUND_HALF_UP


def _to_decimal(value):
    return Decimal(str(value))


def format_usd_amount(value):
    return f"{_to_decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def format_toman_amount(value):
    return f"{_to_decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP):,}"
