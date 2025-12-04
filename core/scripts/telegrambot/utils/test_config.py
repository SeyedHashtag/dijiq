import json
import os
import datetime
from telebot import types
from utils.command import bot
from utils.common import create_main_markup
from utils.adduser import APIClient
from utils.translations import BUTTON_TRANSLATIONS, get_message_text
from utils.language import get_user_language
import qrcode
import io

TEST_CONFIGS_FILE = '/etc/dijiq/core/scripts/telegrambot/test_configs.json'

def load_test_configs():
    try:
        if os.path.exists(TEST_CONFIGS_FILE):
            with open(TEST_CONFIGS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_test_configs(configs):
    os.makedirs(os.path.dirname(TEST_CONFIGS_FILE), exist_ok=True)
    with open(TEST_CONFIGS_FILE, 'w') as f:
        json.dump(configs, f, indent=4)

def has_used_test_config(user_id):
    configs = load_test_configs()
    return str(user_id) in configs

def mark_test_config_used(user_id, username=None):
    configs = load_test_configs()
    entry = {
        'used_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    if username:
        entry['username'] = username
    configs[str(user_id)] = entry
    save_test_configs(configs)

def format_datetime_string():
    """Generate a datetime string for the username"""
    now = datetime.datetime.now()
    return now.strftime("%Y%m%d%H%M%S")

def create_username_from_user_id(user_id):
    """Create a username for test config using the required format: test{telegram numeric id}t{exact date and time}"""
    time_str = format_datetime_string()
    return f"test{user_id}t{time_str}"

@bot.message_handler(func=lambda message: any(
    message.text == translations["test_config"] 
    for translations in BUTTON_TRANSLATIONS.values()
))
def test_config(message):
    user_id = message.from_user.id
      # Check if user has already used a test config
    if has_used_test_config(user_id):
        language = get_user_language(user_id)
        bot.reply_to(
            message,
            get_message_text(language, "test_config_used"),
            reply_markup=create_main_markup(is_admin=False, user_id=user_id)
        )
        return
    
    # Ask for confirmation
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Yes, create my test config", callback_data="confirm_test_config"),
        types.InlineKeyboardButton("❌ No, cancel", callback_data="cancel_test_config")
    )
    
    bot.reply_to(
        message,
        "🎁 You're about to create a free test configuration (1GB for 30 days). Would you like to continue?",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_test_config")
def handle_cancel_test_config(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "❌ Test config creation cancelled.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )

@bot.callback_query_handler(func=lambda call: call.data == "confirm_test_config")
def handle_confirm_test_config(call):
    user_id = call.from_user.id
    # Double check if user has already used a test config
    if has_used_test_config(user_id):
        bot.answer_callback_query(call.id)
        language = get_user_language(user_id)
        bot.edit_message_text(
            get_message_text(language, "test_config_used"),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        return

    # Create a username for the test config
    username = create_username_from_user_id(user_id)

    # Constants for test config
    TEST_TRAFFIC_GB = 1  # 1 GB
    TEST_DAYS = 30       # 30 days

    # Display processing message
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "⏳ Creating your test configuration...",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )

    api_client = APIClient()
    result = api_client.add_user(username, TEST_TRAFFIC_GB, TEST_DAYS, unlimited=True)

    if result:
        # Mark the test config as used (save username as well)
        mark_test_config_used(user_id, username=username)

        # Get user URI from API
        user_uri_data = api_client.get_user_uri(username)
        if user_uri_data and 'normal_sub' in user_uri_data:
            sub_url = user_uri_data['normal_sub']
            # Create QR code for subscription URL
            qr = qrcode.make(sub_url)
            bio = io.BytesIO()
            qr.save(bio, 'PNG')
            bio.seek(0)

            # Format success message
            success_message = (
                f"✅ Your test configuration has been created successfully!\n\n"
                f"📊 Test Plan Details:\n"
                f"- 🔹 Data: {TEST_TRAFFIC_GB} GB\n"
                f"- 🔹 Duration: {TEST_DAYS} days\n"
                f"- 🔹 Unlimited Devices: Yes\n"
                f"- 🔹 Username: `{username}`\n\n"
                f"Subscription URL: `{sub_url}`\n\n"
                f"Scan the QR code to configure your VPN client."
            )
            # Send the QR code with config details
            bot.send_photo(
                call.message.chat.id,
                photo=bio,
                caption=success_message,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                call.message.chat.id,
                f"✅ Your test configuration has been created, but the subscription URL could not be generated. Please contact support.",
                parse_mode="Markdown"
            )
    else:
        bot.send_message(
            call.message.chat.id,
            "❌ Failed to create test configuration. Please try again later or contact support.",
            parse_mode="Markdown"
        )