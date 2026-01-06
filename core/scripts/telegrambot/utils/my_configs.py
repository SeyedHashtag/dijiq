import qrcode
import io
import json
import os
import requests
import re
from dotenv import load_dotenv
from telebot import types
from utils.command import bot
from utils.adduser import APIClient
from utils.translations import BUTTON_TRANSLATIONS, get_message_text
from utils.language import get_user_language

@bot.message_handler(func=lambda message: any(
    message.text == translations["my_configs"] 
    for translations in BUTTON_TRANSLATIONS.values()
))
def my_configs(message):
    """Handle the My Configs button click"""
    user_id = message.from_user.id
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Create API client to fetch user data
    api_client = APIClient()
    
    # Get all users
    users = api_client.get_users()
    if users is None:
        bot.reply_to(message, "⚠️ Error connecting to API. Please try again later.")
        return
    
    # Look for usernames that match this user's Telegram ID pattern
    user_configs = []

    try:
        # The patterns are {telegram_id}t{timestamp} and sell{telegram_id}t{timestamp}
        pattern = f"^{user_id}t"
        sell_pattern = f"^sell{user_id}t"

        # Handle both list and dictionary responses from API
        if isinstance(users, dict):
            # If users is a dictionary, iterate through items
            for username, user_data in users.items():
                if username and (re.match(pattern, username) or re.match(sell_pattern, username)):
                    user_configs.append((username, user_data))

            # Check if we found any configs for this user
            if not user_configs:
                # Also check for test configs: test{telegram_id}t{timestamp}
                test_pattern = f"^test{user_id}t"

                for username, user_data in users.items():
                    if username and re.match(test_pattern, username):
                        user_configs.append((username, user_data))
        elif isinstance(users, list):
            # If users is a list, iterate through items
            for user in users:
                username = user.get('username')
                if username and (re.match(pattern, username) or re.match(sell_pattern, username)):
                    user_configs.append((username, user))

            # Check if we found any configs for this user
            if not user_configs:
                # Also check for test configs: test{telegram_id}t{timestamp}
                test_pattern = f"^test{user_id}t"

                for user in users:
                    username = user.get('username')
                    if username and re.match(test_pattern, username):
                        user_configs.append((username, user))

        if not user_configs:
            language = get_user_language(user_id)
            bot.reply_to(
                message,
                get_message_text(language, "no_active_configs")
            )
            return
    except Exception as e:
        bot.reply_to(message, f"⚠️ Error processing user data: {str(e)}")
        return
    
    # Process and display configs
    if len(user_configs) == 1:
        # Only one config found, display it directly
        display_config(message.chat.id, user_configs[0][0], user_configs[0][1], api_client)
    else:
        # Multiple configs found, create a selection menu
        markup = types.InlineKeyboardMarkup()
        
        for username, user_data in user_configs:
            # Get traffic limit in GB
            max_traffic_gb = user_data.get('max_download_bytes', 0) / (1024 ** 3)
            # Create button text with some info
            button_text = f"{username} - {max_traffic_gb:.2f} GB"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=f"show_config:{username}"))
        
        bot.reply_to(
            message,
            "📱 Select a configuration to view:",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('show_config:'))
def handle_show_config(call):
    """Handle the selection of a specific config"""
    try:
        bot.answer_callback_query(call.id)
        username = call.data.split(':')[1]
        
        # Create API client
        api_client = APIClient()
        
        # Get specific user data
        user_data = api_client.get_user(username)
        
        if user_data:
            # Show the config
            display_config(call.message.chat.id, username, user_data, api_client, is_callback=True, message_id=call.message.message_id)
        else:
            bot.edit_message_text(
                f"⚠️ Error: User '{username}' not found or API error.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
    except Exception as e:
        print(f"Error in handle_show_config: {str(e)}")
        bot.edit_message_text(
            f"⚠️ Error processing your request: {str(e)}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )

def display_config(chat_id, username, user_data, api_client, is_callback=False, message_id=None):
    """Display user configuration details and QR code"""
    
    # Check if the user is blocked/expired
    is_blocked = user_data.get('blocked', False)
    
    try:
        # Extract user statistics with default values to prevent NoneType errors
        upload_bytes = user_data.get('upload_bytes', 0) or 0  # Convert None to 0
        download_bytes = user_data.get('download_bytes', 0) or 0  # Convert None to 0
        status = user_data.get('status', 'Unknown')
        max_download_bytes = user_data.get('max_download_bytes', 0) or 0  # Convert None to 0
        expiration_days = user_data.get('expiration_days', 0)
        account_creation_date = user_data.get('account_creation_date', 'Unknown')

        # Calculate traffic with safety checks
        upload_gb = upload_bytes / (1024 ** 3)  # Convert bytes to GB
        download_gb = download_bytes / (1024 ** 3)  # Convert bytes to GB
        total_usage_gb = upload_gb + download_gb
        max_traffic_gb = max_download_bytes / (1024 ** 3)
        
        # Format user details
        if upload_bytes == 0 and download_bytes == 0:
            traffic_message = "**Traffic Data:**\nNo traffic data available."
        else:
            traffic_message = (
                f"🔼 Upload: {upload_gb:.2f} GB\n"
                f"🔽 Download: {download_gb:.2f} GB\n"
                f"📊 Total Usage: {total_usage_gb:.2f} GB"
            )
            if max_traffic_gb > 0:
                traffic_message += f" / {max_traffic_gb:.2f} GB"
            traffic_message += f"\n🌐 Status: {status}"

        traffic_limit_display = f"{max_traffic_gb:.2f} GB" if max_traffic_gb > 0 else "Unlimited"
        
        formatted_details = (
            f"\n🆔 Username: {username}\n"
            f"📊 Traffic Limit: {traffic_limit_display}\n"
            f"📅 Days Remaining: {expiration_days}\n"
            f"⏳ Creation Date: {account_creation_date}\n"
            f"💡 Status: {'❌ Blocked/Expired' if is_blocked else '✅ Active'}\n\n"
            f"{traffic_message}"
        )
        
        if is_blocked:
            # User is blocked/expired
            message = (
                f"❌ **Your configuration has expired!**\n{formatted_details}\n\n"
                "Please use the '💰 Purchase Plan' button to buy a new subscription."
            )
            
            if is_callback:
                bot.edit_message_text(message, chat_id=chat_id, message_id=message_id, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, message, parse_mode="Markdown")
            return
        
        # User is active, get subscription URL using the new API endpoint
        user_uri_data = api_client.get_user_uri(username)
        if not user_uri_data or 'normal_sub' not in user_uri_data:
            if is_callback:
                bot.edit_message_text(
                    f"⚠️ Error: Could not generate subscription URL for '{username}'. Please contact support.",
                    chat_id=chat_id,
                    message_id=message_id
                )
            else:
                bot.send_message(
                    chat_id,
                    f"⚠️ Error: Could not generate subscription URL for '{username}'. Please contact support."
                )
            return
        sub_url = user_uri_data['normal_sub']
        
        # Create QR code for subscription URL
        qr_code = qrcode.make(sub_url)
        bio = io.BytesIO()
        qr_code.save(bio, 'PNG')
        bio.seek(0)
        
        # Prepare caption with formatted details and subscription URL
        caption = f"{formatted_details}\n\nSubscription URL: `{sub_url}`"
        
        # Send QR code with details
        if is_callback:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
            bot.send_photo(
                chat_id,
                photo=bio,
                caption=caption,
                parse_mode="Markdown"
            )
        else:
            bot.send_photo(
                chat_id,
                photo=bio,
                caption=caption,
                parse_mode="Markdown"
            )
    except Exception as e:
        error_message = f"⚠️ Error displaying configuration: {str(e)}"
        print(f"Error in display_config: {str(e)}")
        if is_callback:
            bot.edit_message_text(error_message, chat_id=chat_id, message_id=message_id)
        else:
            bot.send_message(chat_id, error_message)
