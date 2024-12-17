from collections import defaultdict
import time
import json
import os

SPAM_PROTECTION_FILE = '/etc/hysteria/core/scripts/telegrambot/spam_protection.json'

class SpamProtection:
    def __init__(self):
        self.message_timestamps = defaultdict(list)
        self.payment_links = self.load_payment_links()
        
        # Settings
        self.max_messages = 10  # Maximum messages per time window
        self.time_window = 60   # Time window in seconds
        self.max_active_payments = 5  # Maximum active payment links per user
        
    def load_payment_links(self):
        """Load active payment links from file"""
        if os.path.exists(SPAM_PROTECTION_FILE):
            try:
                with open(SPAM_PROTECTION_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
        
    def save_payment_links(self):
        """Save active payment links to file"""
        try:
            os.makedirs(os.path.dirname(SPAM_PROTECTION_FILE), exist_ok=True)
            with open(SPAM_PROTECTION_FILE, 'w') as f:
                json.dump(self.payment_links, f)
        except Exception as e:
            print(f"Error saving payment links: {str(e)}")

    def can_send_message(self, user_id):
        """Check if user can send a message (anti-spam)"""
        current_time = time.time()
        user_id = str(user_id)
        
        # Remove old timestamps
        self.message_timestamps[user_id] = [
            ts for ts in self.message_timestamps[user_id]
            if current_time - ts < self.time_window
        ]
        
        # Check if user has exceeded message limit
        if len(self.message_timestamps[user_id]) >= self.max_messages:
            return False
            
        # Add new timestamp
        self.message_timestamps[user_id].append(current_time)
        return True

    def can_create_payment(self, user_id):
        """Check if user can create a new payment link"""
        user_id = str(user_id)
        current_time = time.time()
        
        # Initialize user's payment links if not exists
        if user_id not in self.payment_links:
            self.payment_links[user_id] = []
            
        # Remove expired payment links
        self.payment_links[user_id] = [
            link for link in self.payment_links[user_id]
            if current_time - link['timestamp'] < 3600  # 1 hour expiry
        ]
        
        # Save updated payment links
        self.save_payment_links()
        
        # Check if user has reached the limit
        return len(self.payment_links[user_id]) < self.max_active_payments

    def add_payment_link(self, user_id, payment_id):
        """Add a new payment link for the user"""
        user_id = str(user_id)
        if user_id not in self.payment_links:
            self.payment_links[user_id] = []
            
        self.payment_links[user_id].append({
            'payment_id': payment_id,
            'timestamp': time.time()
        })
        
        self.save_payment_links()

    def remove_payment_link(self, user_id, payment_id):
        """Remove a payment link after it's completed or expired"""
        user_id = str(user_id)
        if user_id in self.payment_links:
            self.payment_links[user_id] = [
                link for link in self.payment_links[user_id]
                if link['payment_id'] != payment_id
            ]
            self.save_payment_links()

# Create global instance
spam_protection = SpamProtection() 
