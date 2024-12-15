import json
import os
from datetime import datetime, timedelta

PAYMENT_TRACKING_FILE = '/etc/hysteria/payment_tracking.json'

def load_payment_tracking():
    """Load payment tracking data from JSON file"""
    if not os.path.exists(PAYMENT_TRACKING_FILE):
        return {}
    try:
        with open(PAYMENT_TRACKING_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_payment_tracking(tracking_data):
    """Save payment tracking data to JSON file"""
    os.makedirs(os.path.dirname(PAYMENT_TRACKING_FILE), exist_ok=True)
    with open(PAYMENT_TRACKING_FILE, 'w') as f:
        json.dump(tracking_data, f, indent=4)

def clean_expired_tracking():
    """Remove expired payment tracking entries"""
    tracking_data = load_payment_tracking()
    now = datetime.now()
    
    # Filter out expired entries
    cleaned_data = {
        user_id: {
            plan_id: data
            for plan_id, data in plans.items()
            if datetime.fromisoformat(data['expires_at']) > now
        }
        for user_id, plans in tracking_data.items()
    }
    
    # Remove empty user entries
    cleaned_data = {
        user_id: plans
        for user_id, plans in cleaned_data.items()
        if plans
    }
    
    save_payment_tracking(cleaned_data)
    return cleaned_data

def can_request_payment(user_id, plan_id):
    """Check if user can request payment for a plan"""
    tracking_data = clean_expired_tracking()
    user_id = str(user_id)
    
    if user_id in tracking_data and plan_id in tracking_data[user_id]:
        expires_at = datetime.fromisoformat(tracking_data[user_id][plan_id]['expires_at'])
        if expires_at > datetime.now():
            return False, tracking_data[user_id][plan_id]
    return True, None

def track_payment_request(user_id, plan_id, payment_id):
    """Track new payment request"""
    tracking_data = clean_expired_tracking()
    user_id = str(user_id)
    
    if user_id not in tracking_data:
        tracking_data[user_id] = {}
    
    # Set expiration to 30 minutes from now
    expires_at = (datetime.now() + timedelta(minutes=30)).isoformat()
    
    tracking_data[user_id][plan_id] = {
        'payment_id': payment_id,
        'requested_at': datetime.now().isoformat(),
        'expires_at': expires_at
    }
    
    save_payment_tracking(tracking_data) 
