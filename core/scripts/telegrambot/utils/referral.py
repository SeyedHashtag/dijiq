import json
import os
import threading
import random
import string
import uuid
from datetime import datetime

REFERRALS_FILE = '/etc/dijiq/core/scripts/telegrambot/referrals.json'
referral_lock = threading.RLock()

# Configuration
REFERRAL_REWARD_PERCENTAGE = 20  # 20% reward
REFERRAL_MIN_PAYOUT_BALANCE = 2.0

def _default_referrals_data():
    return {
        "referrals": {},  # user_id -> referrer_id
        "stats": {},      # user_id -> { "count": 0, "total_earnings": 0, "available_balance": 0 }
        "codes": {},      # code -> user_id
        "user_codes": {},  # user_id -> code
        "wallets": {},    # user_id -> wallet_address
        "referral_details": {},  # invited user_id -> invite metadata
        "payouts": []     # paid referral payout audit records
    }

def _ensure_referrals_shape(data):
    defaults = _default_referrals_data()
    for key, value in defaults.items():
        data.setdefault(key, value.copy() if isinstance(value, dict) else list(value))
    if not isinstance(data.get("payouts"), list):
        data["payouts"] = []
    return data

def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)

def load_referrals():
    with referral_lock:
        try:
            if os.path.exists(REFERRALS_FILE):
                with open(REFERRALS_FILE, 'r') as f:
                    data = json.load(f)
                    return _ensure_referrals_shape(data)
        except Exception:
            pass
        return _default_referrals_data()

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

def process_referral(new_user_id, code, telegram_username=None, first_name=None, last_name=None):
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
    data.setdefault("referral_details", {})[new_user_id_str] = {
        "telegram_user_id": new_user_id,
        "telegram_username": telegram_username,
        "first_name": first_name,
        "last_name": last_name,
        "referral_code": code,
        "referrer_id": referrer_id,
        "invited_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
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

def set_wallet_address(user_id, address):
    data = load_referrals()
    user_id_str = str(user_id)
    
    if "wallets" not in data:
        data["wallets"] = {}
        
    data["wallets"][user_id_str] = address
    save_referrals(data)
    return True

def get_wallet_address(user_id):
    data = load_referrals()
    user_id_str = str(user_id)
    return data.get("wallets", {}).get(user_id_str)

def get_eligible_referral_users(min_balance=REFERRAL_MIN_PAYOUT_BALANCE):
    data = load_referrals()
    wallets = data.get("wallets", {})
    eligible_users = []

    for user_id, stats in data.get("stats", {}).items():
        if not isinstance(stats, dict):
            continue
        available_balance = _safe_float(stats.get("available_balance", 0))
        if available_balance < float(min_balance):
            continue
        wallet = wallets.get(str(user_id))
        eligible_users.append({
            "user_id": str(user_id),
            "available_balance": available_balance,
            "total_earnings": _safe_float(stats.get("total_earnings", 0)),
            "invited_count": _safe_int(stats.get("count", 0)),
            "wallet": wallet,
            "has_wallet": bool(wallet),
        })

    eligible_users.sort(key=lambda item: (-item["available_balance"], str(item["user_id"])))
    return eligible_users

def mark_referral_payout_paid(user_id, admin_user_id):
    with referral_lock:
        data = load_referrals()
        user_id_str = str(user_id)
        stats = data.get("stats", {}).get(user_id_str)

        if not isinstance(stats, dict):
            return False, "No stats found"

        available_balance = _safe_float(stats.get("available_balance", 0))
        if available_balance < REFERRAL_MIN_PAYOUT_BALANCE:
            return False, "Insufficient balance (Minimum $2.00)"

        wallet = data.get("wallets", {}).get(user_id_str)
        if not wallet:
            return False, "Wallet address not set"

        payout = {
            "id": str(uuid.uuid4()),
            "user_id": user_id_str,
            "admin_user_id": str(admin_user_id),
            "amount": available_balance,
            "wallet": wallet,
            "paid_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "available_balance_before": available_balance,
            "available_balance_after": 0,
            "total_earnings_snapshot": _safe_float(stats.get("total_earnings", 0)),
            "invited_count_snapshot": _safe_int(stats.get("count", 0)),
        }

        stats["available_balance"] = 0
        data.setdefault("payouts", []).append(payout)
        save_referrals(data)
        return True, payout

def _get_invitee_payments(invitee_user_id):
    try:
        from utils.payment_records import load_payments
        payments = load_payments()
    except Exception:
        payments = {}

    invitee_payments = []
    for payment_id, payment_data in payments.items():
        if str(payment_data.get("user_id")) != str(invitee_user_id):
            continue

        invitee_payments.append({
            "payment_id": payment_id,
            "status": payment_data.get("status"),
            "price": payment_data.get("price"),
            "plan_gb": payment_data.get("plan_gb"),
            "days": payment_data.get("days"),
            "created_at": payment_data.get("created_at"),
            "updated_at": payment_data.get("updated_at")
        })

    return invitee_payments

def build_withdrawal_audit_payload(user_id, telegram_username, withdrawal_data):
    data = load_referrals()
    user_id_str = str(user_id)
    referral_details = data.get("referral_details", {})

    invitees = []
    for invitee_id, referrer_id in data.get("referrals", {}).items():
        if str(referrer_id) != user_id_str:
            continue

        details = referral_details.get(str(invitee_id), {})
        metadata_complete = bool(details.get("invited_at"))
        invitees.append({
            "telegram_user_id": int(invitee_id) if str(invitee_id).isdigit() else invitee_id,
            "telegram_username": details.get("telegram_username"),
            "first_name": details.get("first_name"),
            "last_name": details.get("last_name"),
            "referral_code": details.get("referral_code"),
            "invited_at": details.get("invited_at"),
            "metadata_complete": metadata_complete,
            "payments": _get_invitee_payments(invitee_id)
        })

    invitees.sort(key=lambda item: (item.get("invited_at") is None, item.get("invited_at") or "", str(item.get("telegram_user_id"))))

    return {
        "request": {
            "requested_at": withdrawal_data.get("requested_at"),
            "requester_user_id": user_id,
            "requester_username": telegram_username,
            "amount": withdrawal_data.get("amount"),
            "wallet": withdrawal_data.get("wallet"),
            "available_balance_after": withdrawal_data.get("available_balance_after"),
            "total_earnings": withdrawal_data.get("total_earnings"),
            "invited_count": withdrawal_data.get("invited_count")
        },
        "invitees": invitees
    }

def process_withdrawal_request(user_id):
    data = load_referrals()
    user_id_str = str(user_id)
    
    stats = data["stats"].get(user_id_str)
    if not stats:
        return False, "No stats found"
        
    if stats["available_balance"] < 2.0:
        return False, "Insufficient balance (Minimum $2.00)"
        
    wallet = data.get("wallets", {}).get(user_id_str)
    if not wallet:
        return False, "Wallet address not set"
        
    amount = stats["available_balance"]
    requested_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    stats["available_balance"] = 0
    
    save_referrals(data)
    return True, {
        "amount": amount,
        "wallet": wallet,
        "requested_at": requested_at,
        "available_balance_after": stats["available_balance"],
        "total_earnings": stats.get("total_earnings", 0),
        "invited_count": stats.get("count", 0)
    }
