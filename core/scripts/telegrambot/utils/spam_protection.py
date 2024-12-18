from collections import defaultdict
import time
import json
import os

class SpamProtection:
    def __init__(self):
        self.message_timestamps = defaultdict(list)
        self.payment_links = defaultdict(list)
        
        # Settings
        self.max_messages = 20  # Maximum messages per minute
        self.time_window = 60   # Time window in seconds
        self.max_active_payments = 5  # Maximum active payment links
        self.payment_expiry = 3600  # Payment link expiry in seconds (1 hour)
    
    def can_send_message(self, user_id):
        """Check if user can send a message"""
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
        current_time = time.time()
        user_id = str(user_id)
        
        # Remove expired payment links
        self.payment_links[user_id] = [
            link for link in self.payment_links[user_id]
            if current_time - link['timestamp'] < self.payment_expiry
        ]
        
        # Check if user has reached the limit
        return len(self.payment_links[user_id]) < self.max_active_payments
    
    def add_payment_link(self, user_id, payment_id):
        """Add a new payment link"""
        user_id = str(user_id)
        self.payment_links[user_id].append({
            'payment_id': payment_id,
            'timestamp': time.time()
        })
    
    def remove_payment_link(self, user_id, payment_id):
        """Remove a payment link"""
        user_id = str(user_id)
        self.payment_links[user_id] = [
            link for link in self.payment_links[user_id]
            if link['payment_id'] != payment_id
        ]

# Create global instance
spam_protection = SpamProtection() 
