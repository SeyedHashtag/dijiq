from telebot import types
from utils.command import bot, is_admin, ADMIN_USER_IDS
from utils.common import create_main_markup
from utils.api_client import APIClient
import re
import json
import os
import time
from datetime import datetime, timedelta

BROADCAST_FAILED_USERS_PATH = "/etc/dijiq/core/scripts/telegrambot/broadcast_failed_users.json"
BROADCAST_LOGS_DIR = "/etc/dijiq/core/scripts/telegrambot/broadcast_logs"


def load_failed_broadcast_users():
    try:
        if not os.path.exists(BROADCAST_FAILED_USERS_PATH):
            return set()
        with open(BROADCAST_FAILED_USERS_PATH, 'r') as f:
            data = json.load(f)
        if not isinstance(data, list):
            return set()
        return {str(user_id) for user_id in data}
    except Exception as e:
        print(f"Failed to load broadcast failed users list: {str(e)}")
        return set()


def save_failed_broadcast_users(user_ids):
    try:
        os.makedirs(os.path.dirname(BROADCAST_FAILED_USERS_PATH), exist_ok=True)
        with open(BROADCAST_FAILED_USERS_PATH, 'w') as f:
            json.dump(sorted({str(user_id) for user_id in user_ids}), f)
    except Exception as e:
        print(f"Failed to save broadcast failed users list: {str(e)}")


def reset_failed_broadcast_users():
    try:
        if os.path.exists(BROADCAST_FAILED_USERS_PATH):
            os.remove(BROADCAST_FAILED_USERS_PATH)
    except Exception as e:
        print(f"Failed to reset broadcast failed users list: {str(e)}")


def generate_broadcast_log(target_label, total_users, success_users, failed_by_error, excluded_count, broadcast_text, admin_id):
    """
    Generate a formatted log file for the broadcast and return the file path.
    
    Args:
        target_label: The target category label
        total_users: Total number of users targeted
        success_users: List of user IDs that received the message successfully
        failed_by_error: Dict mapping error messages to lists of user IDs
        excluded_count: Number of users excluded from future broadcasts
        broadcast_text: The broadcast message content
        admin_id: The admin ID who initiated the broadcast
    
    Returns:
        Path to the generated log file
    """
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    timestamp_file = timestamp.strftime("%Y%m%d_%H%M%S")
    
    # Create logs directory if it doesn't exist
    os.makedirs(BROADCAST_LOGS_DIR, exist_ok=True)
    
    # Generate log filename
    log_filename = f"broadcast_{timestamp_file}_admin{admin_id}.txt"
    log_filepath = os.path.join(BROADCAST_LOGS_DIR, log_filename)
    
    # Calculate counts
    success_count = len(success_users)
    fail_count = sum(len(users) for users in failed_by_error.values())
    
    # Build log content
    lines = []
    lines.append("═" * 50)
    lines.append("         BROADCAST LOG REPORT")
    lines.append("═" * 50)
    lines.append(f"Timestamp: {timestamp_str}")
    lines.append(f"Target: {target_label}")
    lines.append(f"Total Users: {total_users}")
    lines.append("")
    lines.append("═" * 50)
    lines.append("           SUMMARY")
    lines.append("═" * 50)
    lines.append(f"✅ Successful: {success_count}")
    lines.append(f"❌ Failed: {fail_count}")
    lines.append(f"🚫 Excluded: {excluded_count}")
    lines.append("")
    
    # Detailed Results Section
    lines.append("═" * 50)
    lines.append("         DETAILED RESULTS")
    lines.append("═" * 50)
    lines.append("")
    
    # Successful users
    if success_users:
        lines.append(f"✅ SUCCESSFUL ({success_count} users):")
        # Format user IDs in rows of 10 for readability
        success_str = ", ".join(str(uid) for uid in success_users)
        lines.append(success_str)
        lines.append("")
    
    # Failed users grouped by error
    if failed_by_error:
        for error_msg, user_list in failed_by_error.items():
            count = len(user_list)
            lines.append(f"❌ FAILED - {error_msg} ({count} users):")
            user_str = ", ".join(str(uid) for uid in user_list)
            lines.append(user_str)
            lines.append("")
    
    # Broadcast message section
    lines.append("═" * 50)
    lines.append("         BROADCAST MESSAGE")
    lines.append("═" * 50)
    # Truncate message if too long for the log
    if len(broadcast_text) > 1000:
        lines.append(broadcast_text[:1000] + "... (truncated)")
    else:
        lines.append(broadcast_text)
    lines.append("")
    lines.append("═" * 50)
    lines.append("              END OF REPORT")
    lines.append("═" * 50)
    
    # Write to file
    with open(log_filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    
    return log_filepath


def create_broadcast_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('👥 All Paid Users', '✅ Active Paid Users')
    markup.row('⛔️ Expired Paid Users', '🧪 All Test Users')
    markup.row('✅🧪 Active Test Users', '⛔️🧪 Expired Test Users')
    markup.row('🔄 Reset Failed Exclusions', '❌ Cancel')
    return markup


def _extract_paid_telegram_id(username):
    """Extract paid-user Telegram ID from new and legacy username formats."""
    if not username:
        return None

    match = re.match(r'^s(\d+)[a-z]*$', username, flags=re.IGNORECASE)
    if match:
        return match.group(1)

    match = re.match(r'^(\d+)t', username)
    if match:
        return match.group(1)

    match = re.match(r'^sell(\d+)t', username)
    if match:
        return match.group(1)

    return None


def get_user_ids(filter_type):
    def get_active_paid_user_ids():
        active_paid_ids = set()
        api_client = APIClient()
        users = api_client.get_users()
        if users is None:
            return active_paid_ids

        def collect_active_paid(username, details):
            telegram_id = _extract_paid_telegram_id(username)
            if telegram_id is None:
                return
            blocked = details.get('blocked', False) if isinstance(details, dict) else False
            if not blocked:
                active_paid_ids.add(telegram_id)

        if isinstance(users, dict):
            for username, details in users.items():
                collect_active_paid(username, details)
        elif isinstance(users, list):
            for item in users:
                if not isinstance(item, dict):
                    continue
                collect_active_paid(item.get('username'), item)

        return active_paid_ids

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

            # Exclude users who already have an active paid account.
            active_paid_ids = get_active_paid_user_ids()
            if active_paid_ids:
                user_ids -= active_paid_ids

            failed_user_ids = load_failed_broadcast_users()
            if failed_user_ids:
                user_ids -= failed_user_ids
            return list(user_ids)
        except Exception as e:
            print(f"Error reading test configs: {str(e)}")
            return []
    
    # For regular paid users (new and legacy formats).
    api_client = APIClient()
    
    # Get all users using API
    users = api_client.get_users()
    if users is None:
        return []
    
    try:
        user_ids = set()

        def process_user_record(username, details):
            if not username or filter_type not in ['all', 'active', 'expired']:
                return

            telegram_id = _extract_paid_telegram_id(username)
            if telegram_id is None:
                return

            blocked = details.get('blocked', False) if isinstance(details, dict) else False

            if filter_type == 'all':
                user_ids.add(telegram_id)
            elif filter_type == 'active' and not blocked:
                user_ids.add(telegram_id)
            elif filter_type == 'expired' and blocked:
                user_ids.add(telegram_id)

        # API may return either a dict keyed by username or a list of user objects.
        if isinstance(users, dict):
            for username, details in users.items():
                process_user_record(username, details)
        elif isinstance(users, list):
            for item in users:
                if not isinstance(item, dict):
                    continue
                process_user_record(item.get('username'), item)
        
        failed_user_ids = load_failed_broadcast_users()
        if failed_user_ids:
            user_ids -= failed_user_ids
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

    if message.text == "🔄 Reset Failed Exclusions":
        reset_failed_broadcast_users()
        bot.reply_to(
            message,
            "Failed-user exclusion list has been reset. All users will be eligible for the next broadcasts.",
            reply_markup=create_main_markup(is_admin=True)
        )
        return
        
    target_map = {
        '👥 All Paid Users': 'all',
        '✅ Active Paid Users': 'active',
        '⛔️ Expired Paid Users': 'expired',
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
    target_label = message.text
    msg = bot.reply_to(
        message,
        "Enter the message you want to broadcast:",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("❌ Cancel"))
    )
    bot.register_next_step_handler(msg, send_broadcast, target, target_label)

def send_broadcast(message, target, target_label):
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
    
    admin_id = message.from_user.id
        
    # Track users by result
    success_users = []  # List of user IDs that received the message
    failed_by_error = {}  # Dict: error_message -> list of user IDs
    failed_user_ids = load_failed_broadcast_users()
    newly_failed_user_ids = set()
    
    status_msg = bot.reply_to(message, f"Broadcasting message to {len(user_ids)} users...")
    
    for user_id in user_ids:
        try:
            bot.send_message(int(user_id), broadcast_text)
            success_users.append(str(user_id))
            time.sleep(0.05)  # Rate limit: ~20 messages/second to avoid Telegram throttling
        except Exception as e:
            error_msg = str(e)
            # Simplify common error messages for grouping
            if "blocked" in error_msg.lower():
                error_key = "Bot was blocked by the user"
            elif "deactivated" in error_msg.lower():
                error_key = "User is deactivated"
            elif "chat not found" in error_msg.lower():
                error_key = "Chat not found"
            elif "user is bot" in error_msg.lower():
                error_key = "User is a bot"
            elif "forbidden" in error_msg.lower():
                error_key = "Forbidden - User unavailable"
            elif "bad request" in error_msg.lower():
                error_key = "Bad Request"
            else:
                error_key = error_msg[:50]  # Truncate long error messages
            
            # Add user ID to the appropriate error group
            if error_key not in failed_by_error:
                failed_by_error[error_key] = []
            failed_by_error[error_key].append(str(user_id))
            newly_failed_user_ids.add(str(user_id))
            print(f"Failed to send broadcast to {user_id}: {error_msg}")
            
        # Update status every 10 users
        processed = len(success_users) + sum(len(u) for u in failed_by_error.values())
        if processed % 10 == 0:
            try:
                bot.edit_message_text(
                    f"Broadcasting: {processed}/{len(user_ids)} completed...",
                    chat_id=status_msg.chat.id,
                    message_id=status_msg.message_id
                )
            except:
                pass
    
    # Update failed users list
    if newly_failed_user_ids:
        failed_user_ids.update(newly_failed_user_ids)
        save_failed_broadcast_users(failed_user_ids)
    
    # Calculate counts
    success_count = len(success_users)
    fail_count = sum(len(users) for users in failed_by_error.values())
    
    # Generate and send log file
    log_filepath = generate_broadcast_log(
        target_label=target_label,
        total_users=len(user_ids),
        success_users=success_users,
        failed_by_error=failed_by_error,
        excluded_count=len(failed_user_ids),
        broadcast_text=broadcast_text,
        admin_id=admin_id
    )
    
    # Build summary for admin message
    error_summary = ""
    if failed_by_error:
        error_summary = "\n\n📋 Error Breakdown:"
        for error_msg, users in failed_by_error.items():
            error_summary += f"\n  • {error_msg}: {len(users)}"

    final_report = (
        "📢 Broadcast Completed\n\n"
        f"Target: {target_label}\n"
        f"Total Users: {len(user_ids)}\n"
        f"✅ Successful: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"🚫 Excluded For Next Broadcasts: {len(failed_user_ids)}"
        f"{error_summary}\n\n"
        f"📄 Detailed log file sent below."
    )
    
    bot.reply_to(message, final_report, reply_markup=create_main_markup(is_admin=True))
    
    # Send the log file to the admin
    try:
        with open(log_filepath, 'rb') as log_file:
            bot.send_document(
                message.chat.id,
                log_file,
                caption=f"📊 Broadcast Log - {target_label}"
            )
    except Exception as e:
        print(f"Failed to send broadcast log file: {str(e)}")
        bot.reply_to(message, f"⚠️ Could not send log file: {str(e)}")
