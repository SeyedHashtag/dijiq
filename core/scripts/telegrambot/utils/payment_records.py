import json
import os
from datetime import datetime

PAYMENTS_FILE = '/etc/hysteria/core/scripts/telegrambot/payments.json'

def load_payments():
    try:
        if os.path.exists(PAYMENTS_FILE):
            with open(PAYMENTS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_payments(payments):
    os.makedirs(os.path.dirname(PAYMENTS_FILE), exist_ok=True)
    with open(PAYMENTS_FILE, 'w') as f:
        json.dump(payments, f, indent=4)

def add_payment_record(payment_id, data):
    payments = load_payments()
    payments[payment_id] = data
    save_payments(payments)

def update_payment_status(payment_id, status):
    payments = load_payments()
    if payment_id in payments:
        payments[payment_id]['status'] = status
        payments[payment_id]['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_payments(payments) 
