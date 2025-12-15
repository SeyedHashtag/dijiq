import json
import os
import threading
from datetime import datetime

PAYMENTS_FILE = '/etc/dijiq/core/scripts/telegrambot/payments.json'
payment_lock = threading.Lock()

def load_payments():
    with payment_lock:
        try:
            if os.path.exists(PAYMENTS_FILE):
                with open(PAYMENTS_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

def save_payments(payments):
    with payment_lock:
        os.makedirs(os.path.dirname(PAYMENTS_FILE), exist_ok=True)
        with open(PAYMENTS_FILE, 'w') as f:
            json.dump(payments, f, indent=4)

def add_payment_record(payment_id, data):
    # Load and save handle locking, but we need to ensure atomicity of read-modify-write
    with payment_lock:
        try:
            if os.path.exists(PAYMENTS_FILE):
                with open(PAYMENTS_FILE, 'r') as f:
                    payments = json.load(f)
            else:
                payments = {}
        except Exception:
            payments = {}
            
        data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data['updates'] = []  # Add history tracking
        payments[payment_id] = data
        
        os.makedirs(os.path.dirname(PAYMENTS_FILE), exist_ok=True)
        with open(PAYMENTS_FILE, 'w') as f:
            json.dump(payments, f, indent=4)

def update_payment_status(payment_id, status):
    with payment_lock:
        try:
            if os.path.exists(PAYMENTS_FILE):
                with open(PAYMENTS_FILE, 'r') as f:
                    payments = json.load(f)
            else:
                return False
        except Exception:
            return False

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
            
            with open(PAYMENTS_FILE, 'w') as f:
                json.dump(payments, f, indent=4)
            return True
        return False

def get_payment_record(payment_id):
    payments = load_payments()
    return payments.get(payment_id)

def get_user_payments(user_id):
    payments = load_payments()
    user_payments = {}
    for payment_id, payment_data in payments.items():
        if payment_data.get('user_id') == user_id:
            user_payments[payment_id] = payment_data
    return user_payments
