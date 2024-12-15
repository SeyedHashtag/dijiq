import json
import os
from telebot import types
from utils.command import bot, is_admin
from utils.client_manager import create_client_config

TEST_MODE_FILE = '/etc/hysteria/test_mode.json'

def load_test_mode():
    """Load test mode status"""
    if not os.path.exists(TEST_MODE_FILE):
        save_test_mode(False)
        return False
    try:
        with open(TEST_MODE_FILE, 'r') as f:
            data = json.load(f)
            return data.get('enabled', False)
    except json.JSONDecodeError:
        return False

def save_test_mode(enabled):
    """Save test mode status"""
    os.makedirs(os.path.dirname(TEST_MODE_FILE), exist_ok=True)
    with open(TEST_MODE_FILE, 'w') as f:
        json.dump({'enabled': enabled}, f)

def is_test_mode():
    """Check if test mode is enabled"""
    return load_test_mode()

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '🧪 Test Mode')
def toggle_test_mode(message):
    """Toggle test mode"""
    current_status = load_test_mode()
    new_status = not current_status
    save_test_mode(new_status)
    
    status_text = "enabled ✅" if new_status else "disabled ❌"
    bot.reply_to(message, f"Test mode {status_text}")

def handle_test_config(message, plan_id, plan):
    """Handle test configuration creation"""
    if not is_test_mode():
        return False
        
    # Create test config
    test_payment_info = {
        'id': 'test_payment',
        'status': 'test',
        'amount': 0,
        'currency': 'TEST',
        'timestamp': datetime.now().isoformat()
    }
    
    # Add 't' suffix to username
    def test_username_generator(user_id):
        now = datetime.now()
        date_str = now.strftime("%m%d%H%M")
        return f"{user_id}d{date_str}t"
    
    create_client_config(message, plan, test_payment_info, username_generator=test_username_generator)
    return True 
