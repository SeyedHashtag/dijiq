import json
import os
import threading
import random
import string
from datetime import datetime

REFERRALS_FILE = '/etc/dijiq/core/scripts/telegrambot/referrals.json'
referral_lock = threading.Lock()

# Configuration
REFERRAL_REWARD_PERCENTAGE = 10  # 10% reward

def load_referrals():
    with referral_lock:
        try:
            if os.path.exists(REFERRALS_FILE):
                with open(REFERRALS_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "referrals": {},  # user_id -> referrer_id
            "stats": {},      # user_id -> { "count": 0, "total_earnings": 0, "available_balance": 0 }
            "codes": {},      # code -> user_id
            "user_codes": {}  # user_id -> code
        }

def save_referrals(data):
    with referral_lock:
        os.makedirs(os.path.dirname(REFERRALS_FILE), exist_ok=True)
        with open(REFERRALS_FILE, 'w') as f:
            json.dump(data, f, indent=4)

def generate_unique_code():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(8))

def get_or_create_referral_code(user_id):
    data = load_referrals()
    user_id_str = str(user_id)
    
    if user_id_str in data["user_codes"]:
        return data["user_codes"][user_id_str]
    
    # Generate new unique code
    while True:
        code = generate_unique_code()
        if code not in data["codes"]:
            break
            
    data["codes"][code] = user_id_str
    data["user_codes"][user_id_str] = code
    data["stats"][user_id_str] = data["stats"].get(user_id_str, {
        "count": 0, 
        "total_earnings": 0, 
        "available_balance": 0
    })
    
    save_referrals(data)
    return code

def process_referral(new_user_id, code):
    data = load_referrals()
    new_user_id_str = str(new_user_id)
    
    # Check if user already referred
    if new_user_id_str in data["referrals"]:
        return False, "User already referred"
        
    # Check validity of code
    if code not in data["codes"]:
        return False, "Invalid referral code"
        
    referrer_id = data["codes"][code]
    
    # Prevent self-referral
    if referrer_id == new_user_id_str:
        return False, "Cannot refer yourself"
        
    data["referrals"][new_user_id_str] = referrer_id
    
    # Update stats for referrer
    if referrer_id not in data["stats"]:
        data["stats"][referrer_id] = {"count": 0, "total_earnings": 0, "available_balance": 0}
        
    data["stats"][referrer_id]["count"] += 1
    
    save_referrals(data)
    return True, referrer_id

def add_referral_reward(user_id, purchase_amount):
    """
    Add reward to the referrer of user_id based on purchase_amount.
    """
    data = load_referrals()
    user_id_str = str(user_id)
    
    if user_id_str not in data["referrals"]:
        return False # No referrer for this user
        
    referrer_id = data["referrals"][user_id_str]
    reward_amount = float(purchase_amount) * (REFERRAL_REWARD_PERCENTAGE / 100)
    
    if referrer_id not in data["stats"]:
        data["stats"][referrer_id] = {"count": 0, "total_earnings": 0, "available_balance": 0}
        
    data["stats"][referrer_id]["total_earnings"] += reward_amount
    data["stats"][referrer_id]["available_balance"] += reward_amount
    
    save_referrals(data)
    return True, referrer_id, reward_amount

def get_referral_stats(user_id):
    data = load_referrals()
    user_id_str = str(user_id)
    return data["stats"].get(user_id_str, {"count": 0, "total_earnings": 0, "available_balance": 0})

def get_referrer(user_id):
    data = load_referrals()
    return data["referrals"].get(str(user_id))
