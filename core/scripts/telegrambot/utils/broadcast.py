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


def generate_broadcast_log(target_label, total_users, success_users, failed_by_error, excluded_by_reason, broadcast_text, admin_id):
    """
    Generate a formatted log file for the broadcast and return the file path.
    
    Args:
        target_label: The target category label
        total_users: Total number of users in the raw pool (before exclusions)
        success_users: List of user IDs that received the message successfully
        failed_by_error: Dict mapping error messages to lists of user IDs
        excluded_by_reason: Dict mapping exclusion reason -> list of user IDs
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
    excluded_count = sum(len(users) for users in excluded_by_reason.values())
    sent_count = success_count + fail_count
    
    # Build log content
    lines = []
    lines.append("═" * 50)
    lines.append("         BROADCAST LOG REPORT")
    lines.append("═" * 50)
    lines.append(f"Timestamp: {timestamp_str}")
    lines.append(f"Target: {target_label}")
    lines.append(f"Pool Size (before exclusions): {total_users}")
    lines.append(f"Actually Sent To: {sent_count}")
    lines.append("")
    lines.append("═" * 50)
    lines.append("           SUMMARY")
    lines.append("═" * 50)
    lines.append(f"✅ Successful: {success_count}")
    lines.append(f"❌ Failed: {fail_count}")
    lines.append(f"🚫 Excluded (skipped): {excluded_count}")
    lines.append("")
    
    # Detailed Results Section
    lines.append("═" * 50)
    lines.append("         DETAILED RESULTS")
    lines.append("═" * 50)
    lines.append("")
    
    # Successful users
    if success_users:
        lines.append(f"✅ SUCCESSFUL ({success_count} users):")
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
    
    # Excluded users grouped by reason
    if excluded_by_reason:
        for reason, user_list in excluded_by_reason.items():
            count = len(user_list)
            lines.append(f"🚫 EXCLUDED - {reason} ({count} users):")
            user_str = ", ".join(str(uid) for uid in sorted(user_list))
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
    markup.row('🎯 Specific User IDs')
    markup.row('🔄 Reset Failed Exclusions', '❌ Cancel')
    return markup


def parse_specific_user_ids(raw_user_ids):
    tokens = re.split(r'[\s,]+', raw_user_ids.strip())
    user_ids = []
    invalid_tokens = []
    seen = set()

    for token in tokens:
        if not token:
            continue
        if not token.isdigit():
            invalid_tokens.append(token)
            continue
        if token in seen:
            continue
        seen.add(token)
        user_ids.append(token)

    return user_ids, invalid_tokens


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
        excluded_by_reason = {}
        try:
            if not os.path.exists(test_config_path):
                print(f"Test config file not found: {test_config_path}")
                return [], {}
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

            total_pool = set(user_ids)  # snapshot before exclusions

            # Exclude users who already have an active paid account.
            active_paid_ids = get_active_paid_user_ids()
            paid_overlap = user_ids & active_paid_ids
            if paid_overlap:
                user_ids -= paid_overlap
                excluded_by_reason["Has active paid account"] = list(paid_overlap)

            failed_user_ids = load_failed_broadcast_users()
            failed_overlap = user_ids & failed_user_ids
            if failed_overlap:
                user_ids -= failed_overlap
                excluded_by_reason["Previously failed (blocked/deactivated)"] = list(failed_overlap)

            return list(user_ids), excluded_by_reason
        except Exception as e:
            print(f"Error reading test configs: {str(e)}")
            return [], {}
    
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
        excluded_by_reason = {}
        failed_overlap = user_ids & failed_user_ids
        if failed_overlap:
            user_ids -= failed_overlap
            excluded_by_reason["Previously failed (blocked/deactivated)"] = list(failed_overlap)
        return list(user_ids), excluded_by_reason
    except Exception as e:
        print(f"Error getting user IDs: {str(e)}")
        return [], {}

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

    if message.text == "🎯 Specific User IDs":
        msg = bot.reply_to(
            message,
            "Enter one or more Telegram numeric user IDs, separated by commas, spaces, or new lines:",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("❌ Cancel"))
        )
        bot.register_next_step_handler(msg, process_specific_user_ids)
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

def process_specific_user_ids(message):
    if message.text == "❌ Cancel":
        bot.reply_to(message, "Broadcast canceled.", reply_markup=create_main_markup(is_admin=True))
        return

    user_ids, invalid_tokens = parse_specific_user_ids(message.text or "")

    if invalid_tokens or not user_ids:
        invalid_preview = ""
        if invalid_tokens:
            invalid_preview = "\n\nInvalid entries: " + ", ".join(invalid_tokens[:10])
            if len(invalid_tokens) > 10:
                invalid_preview += f", ... ({len(invalid_tokens) - 10} more)"

        msg = bot.reply_to(
            message,
            "Please enter only numeric Telegram user IDs separated by commas, spaces, or new lines."
            f"{invalid_preview}",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("❌ Cancel"))
        )
        bot.register_next_step_handler(msg, process_specific_user_ids)
        return

    msg = bot.reply_to(
        message,
        f"Enter the message you want to send to {len(user_ids)} specific user(s):",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("❌ Cancel"))
    )
    bot.register_next_step_handler(msg, send_broadcast, None, "🎯 Specific User IDs", user_ids)


def send_broadcast(message, target, target_label, explicit_user_ids=None):
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

    if explicit_user_ids is None:
        user_ids, excluded_by_reason = get_user_ids(target)
    else:
        user_ids = list(explicit_user_ids)
        excluded_by_reason = {}

    total_pool = len(user_ids) + sum(len(v) for v in excluded_by_reason.values())
    
    if not user_ids and not excluded_by_reason:
        bot.reply_to(
            message,
            "No users found in the selected category.",
            reply_markup=create_main_markup(is_admin=True)
        )
        return
    
    if not user_ids:
        # All users were excluded — generate a log so admin can see who was excluded
        admin_id = message.from_user.id
        log_filepath = generate_broadcast_log(
            target_label=target_label,
            total_users=total_pool,
            success_users=[],
            failed_by_error={},
            excluded_by_reason=excluded_by_reason,
            broadcast_text=broadcast_text,
            admin_id=admin_id
        )
        bot.reply_to(
            message,
            f"⚠️ All {total_pool} users in this category are currently excluded (blocked/deactivated or have active paid accounts). No messages sent.\n\n📄 Exclusion log sent below.",
            reply_markup=create_main_markup(is_admin=True)
        )
        try:
            with open(log_filepath, 'rb') as log_file:
                bot.send_document(message.chat.id, log_file, caption=f"📊 Exclusion Log - {target_label}")
        except Exception as e:
            print(f"Failed to send exclusion log file: {str(e)}")
        return

    admin_id = message.from_user.id
        
    # Track users by result
    success_users = []  # List of user IDs that received the message
    failed_by_error = {}  # Dict: error_message -> list of user IDs
    newly_failed_user_ids = set()
    
    status_msg = bot.reply_to(message, f"Broadcasting message to {len(user_ids)} users (pool: {total_pool} total, {total_pool - len(user_ids)} pre-excluded)...")
    
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
        existing_failed = load_failed_broadcast_users()
        existing_failed.update(newly_failed_user_ids)
        save_failed_broadcast_users(existing_failed)
    
    # Calculate counts
    success_count = len(success_users)
    fail_count = sum(len(users) for users in failed_by_error.values())
    
    # Generate and send log file
    log_filepath = generate_broadcast_log(
        target_label=target_label,
        total_users=total_pool,
        success_users=success_users,
        failed_by_error=failed_by_error,
        excluded_by_reason=excluded_by_reason,
        broadcast_text=broadcast_text,
        admin_id=admin_id
    )
    
    # Build summary for admin message
    excluded_total = sum(len(v) for v in excluded_by_reason.values())
    error_summary = ""
    if failed_by_error:
        error_summary = "\n\n📋 Error Breakdown:"
        for error_msg, users in failed_by_error.items():
            error_summary += f"\n  • {error_msg}: {len(users)}"
    
    excluded_summary = ""
    if excluded_by_reason:
        excluded_summary = "\n\n🚫 Exclusion Breakdown:"
        for reason, users in excluded_by_reason.items():
            excluded_summary += f"\n  • {reason}: {len(users)}"

    final_report = (
        "📢 Broadcast Completed\n\n"
        f"Target: {target_label}\n"
        f"Pool Size: {total_pool}\n"
        f"✅ Successful: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"🚫 Pre-excluded (skipped): {excluded_total}"
        f"{error_summary}"
        f"{excluded_summary}\n\n"
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
