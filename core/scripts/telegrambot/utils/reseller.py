import json
import os
import threading
from datetime import datetime

RESELLERS_FILE = '/etc/dijiq/core/scripts/telegrambot/resellers.json'
reseller_lock = threading.RLock()

def load_resellers():
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

def save_resellers(resellers):
    with reseller_lock:
        os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
        with open(RESELLERS_FILE, 'w') as f:
            json.dump(resellers, f, indent=4)

def get_reseller_data(user_id):
    resellers = load_resellers()
    return resellers.get(str(user_id))

def get_all_resellers():
    return load_resellers()

def update_reseller_status(user_id, status):
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                resellers = {}
        except Exception:
            resellers = {}
            
        if user_id not in resellers:
            resellers[user_id] = {
                'status': status,
                'debt': 0.0,
                'configs': [],
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            resellers[user_id]['status'] = status
            
        # Ensure debt key exists
        if 'debt' not in resellers[user_id]:
             resellers[user_id]['debt'] = 0.0
        
        os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
        with open(RESELLERS_FILE, 'w') as f:
            json.dump(resellers, f, indent=4)
        return True

def add_reseller_debt(user_id, amount, config_data):
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                return False
        except Exception:
            return False
            
        if user_id in resellers:
            resellers[user_id]['debt'] = resellers[user_id].get('debt', 0.0) + float(amount)
            if 'configs' not in resellers[user_id]:
                resellers[user_id]['configs'] = []
            
            config_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            resellers[user_id]['configs'].append(config_data)
            
            os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
            with open(RESELLERS_FILE, 'w') as f:
                json.dump(resellers, f, indent=4)
            return True
        return False

def clear_reseller_debt(user_id):
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                return False
        except Exception:
            return False
            
        if user_id in resellers:
            resellers[user_id]['debt'] = 0.0
            os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
            with open(RESELLERS_FILE, 'w') as f:
                json.dump(resellers, f, indent=4)
            return True
        return False

def set_reseller_debt(user_id, amount):
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                return False
        except Exception:
            return False
            
        if user_id in resellers:
            resellers[user_id]['debt'] = float(amount)
            os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
            with open(RESELLERS_FILE, 'w') as f:
                json.dump(resellers, f, indent=4)
            return True
        return False

def apply_reseller_payment(user_id, amount):
    user_id = str(user_id)
    with reseller_lock:
        try:
            if os.path.exists(RESELLERS_FILE):
                with open(RESELLERS_FILE, 'r') as f:
                    resellers = json.load(f)
            else:
                return False, None
        except Exception:
            return False, None

        if user_id not in resellers:
            return False, None

        try:
            paid_amount = float(amount)
        except (TypeError, ValueError):
            return False, None

        current_debt = float(resellers[user_id].get('debt', 0.0))
        new_debt = max(0.0, current_debt - paid_amount)
        resellers[user_id]['debt'] = new_debt

        os.makedirs(os.path.dirname(RESELLERS_FILE), exist_ok=True)
        with open(RESELLERS_FILE, 'w') as f:
            json.dump(resellers, f, indent=4)
        return True, new_debt
