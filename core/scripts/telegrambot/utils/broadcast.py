from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
from utils.adduser import APIClient
import re
import json
import os
from datetime import datetime, timedelta

def create_broadcast_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('👥 All Users', '✅ Active Users')
    markup.row('⛔️ Expired Users', '🧪 All Test Users')
    markup.row('✅🧪 Active Test Users', '⛔️🧪 Expired Test Users')
    markup.row('❌ Cancel')
    return markup

def get_user_ids(filter_type):
    # For test users, use the test_configs.json file
    test_config_path = "/etc/dijiq/core/scripts/telegrambot/test_configs.json"
    
    if filter_type in ['all_test', 'active_test', 'expired_test']:
        user_ids = set()
        try:
            if not os.path.exists(test_config_path):
                print(f"Test config file not found: {test_config_path}")
                return []
            with open(test_config_path, 'r') as f:
                test_users = json.load(f)
            now = datetime.now()
            for telegram_id, info in test_users.items():
                used_at_str = info.get('used_at')
                if not used_at_str:
                    continue
                try:
                    used_at = datetime.strptime(used_at_str, "%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    print(f"Invalid date for user {telegram_id}: {used_at_str}")
                    continue
                expired = (now - used_at) > timedelta(days=30)
                if filter_type == 'all_test':
                    user_ids.add(telegram_id)
                elif filter_type == 'active_test' and not expired:
                    user_ids.add(telegram_id)
                elif filter_type == 'expired_test' and expired:
                    user_ids.add(telegram_id)
            return list(user_ids)
        except Exception as e:
            print(f"Error reading test configs: {str(e)}")
            return []
    
    # For regular users (format: {telegram_id}t{timestamp})
    api_client = APIClient()
    
    # Get all users using API
    users = api_client.get_users()
    if users is None:
        return []
    
    try:
        user_ids = set()
        
        for username, details in users.items():
            if not username:
                continue
                
            if filter_type in ['all', 'active', 'expired']:
                match = re.match(r'^(\d+)t', username)
                if match:
                    telegram_id = match.group(1)
                    
                    if filter_type == 'all':
                        user_ids.add(telegram_id)
                    elif filter_type == 'active' and not details.get('blocked', False):
                        user_ids.add(telegram_id)
                    elif filter_type == 'expired' and details.get('blocked', True):
                        user_ids.add(telegram_id)
        
        return list(user_ids)
    except Exception as e:
        print(f"Error getting user IDs: {str(e)}")
        return []

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '📢 Broadcast Message')
def start_broadcast(message):
    msg = bot.reply_to(
        message,
        "Select the target users for your broadcast:",
        reply_markup=create_broadcast_markup()
    )
    bot.register_next_step_handler(msg, process_broadcast_target)

def process_broadcast_target(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Broadcast canceled.", reply_markup=create_main_markup(is_admin=True))
        return
        
    target_map = {
        '👥 All Users': 'all',
        '✅ Active Users': 'active',
        '⛔️ Expired Users': 'expired',
        '🧪 All Test Users': 'all_test',
        '✅🧪 Active Test Users': 'active_test',
        '⛔️🧪 Expired Test Users': 'expired_test'
    }
    
    if message.text not in target_map:
        bot.reply_to(
            message,
            "Invalid selection. Please use the provided buttons.",
            reply_markup=create_broadcast_markup()
        )
        return
        
    target = target_map[message.text]
    msg = bot.reply_to(
        message,
        "Enter the message you want to broadcast:",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("❌ Cancel"))
    )
    bot.register_next_step_handler(msg, send_broadcast, target)

def send_broadcast(message, target):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Broadcast canceled.", reply_markup=create_main_markup(is_admin=True))
        return
        
    broadcast_text = message.text.strip()
    if not broadcast_text:
        bot.reply_to(
            message,
            "Message cannot be empty. Please try again:",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("❌ Cancel"))
        )
        return
        
    user_ids = get_user_ids(target)
    
    if not user_ids:
        bot.reply_to(
            message,
            "No users found in the selected category.",
            reply_markup=create_main_markup(is_admin=True)
        )
        return
        
    success_count = 0
    fail_count = 0
    
    status_msg = bot.reply_to(message, f"Broadcasting message to {len(user_ids)} users...")
    
    for user_id in user_ids:
        try:
            bot.send_message(int(user_id), broadcast_text)
            success_count += 1
        except Exception as e:
            print(f"Failed to send broadcast to {user_id}: {str(e)}")
            fail_count += 1
            
        # Update status every 10 users
        if (success_count + fail_count) % 10 == 0:
            try:
                bot.edit_message_text(
                    f"Broadcasting: {success_count + fail_count}/{len(user_ids)} completed...",
                    chat_id=status_msg.chat.id,
                    message_id=status_msg.message_id
                )
            except:
                pass
    
    final_report = (
        "📢 Broadcast Completed\n\n"
        f"Target: {message.text}\n"
        f"Total Users: {len(user_ids)}\n"
        f"✅ Successful: {success_count}\n"
        f"❌ Failed: {fail_count}"
    )
    
    bot.reply_to(message, final_report, reply_markup=create_main_markup(is_admin=True))