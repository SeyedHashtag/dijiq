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
    data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data['updates'] = []  # Add history tracking
    payments[payment_id] = data
    save_payments(payments)

def update_payment_status(payment_id, status):
    payments = load_payments()
    if payment_id in payments:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Add update to history
        update = {
            'status': status,
            'timestamp': current_time,
            'previous_status': payments[payment_id].get('status', 'unknown')
        }
        
        payments[payment_id]['status'] = status
        payments[payment_id]['updated_at'] = current_time
        payments[payment_id]['updates'].append(update)
        
        save_payments(payments) 
