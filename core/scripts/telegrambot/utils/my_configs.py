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

@bot.message_handler(func=lambda message: message.text == '📱 My Configs')
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
        # The pattern is {telegram_id}t{timestamp}
        pattern = f"^{user_id}t"
        
        for username, user_data in users.items():
            if username and re.match(pattern, username):
                user_configs.append((username, user_data))
        
        # Check if we found any configs for this user
        if not user_configs:
            # Also check for test configs: test{telegram_id}t{timestamp}
            test_pattern = f"^test{user_id}t"
            
            for username, user_data in users.items():
                if username and re.match(test_pattern, username):
                    user_configs.append((username, user_data))
            
            if not user_configs:
                bot.reply_to(
                    message, 
                    "❌ You don't have any active configurations.\n\n"
                    "Please use the '🎁 Test Config' button to get a free test config "
                    "or the '💰 Purchase Plan' button to buy a subscription."
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
    bot.answer_callback_query(call.id)
    username = call.data.split(':')[1]
    
    # Create API client
    api_client = APIClient()
    
    # Get specific user details
    user_data = api_client.get_user(username)
    
    if "error" in user_data:
        bot.edit_message_text(
            f"⚠️ Error: {user_data['error']}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        return
    
    # Show the config
    display_config(call.message.chat.id, username, user_data, api_client, is_callback=True, message_id=call.message.message_id)

def display_config(chat_id, username, user_data, api_client, is_callback=False, message_id=None):
    """Display user configuration details and QR code"""
    
    # Check if the user is blocked/expired
    is_blocked = user_data.get('blocked', False)
    
    try:
        # Extract user statistics
        upload_bytes = user_data.get('upload_bytes', 0)
        download_bytes = user_data.get('download_bytes', 0)
        status = user_data.get('status', 'Unknown')
        max_download_bytes = user_data.get('max_download_bytes', 0)
        expiration_days = user_data.get('expiration_days', 0)
        account_creation_date = user_data.get('account_creation_date', 'Unknown')

        # Calculate traffic percentages
        upload_gb = upload_bytes / (1024 ** 3)  # Convert bytes to GB
        download_gb = download_bytes / (1024 ** 3)  # Convert bytes to GB
        total_usage_gb = upload_gb + download_gb
        max_traffic_gb = max_download_bytes / (1024 ** 3)
        
        # Format user details
        if upload_bytes is None or download_bytes is None:
            traffic_message = "**Traffic Data:**\nNo traffic data available."
        else:
            traffic_message = (
                f"🔼 Upload: {upload_gb:.2f} GB\n"
                f"🔽 Download: {download_gb:.2f} GB\n"
                f"📊 Total Usage: {total_usage_gb:.2f} GB / {max_traffic_gb:.2f} GB\n"
                f"🌐 Status: {status}"
            )
        
        formatted_details = (
            f"\n🆔 Username: {username}\n"
            f"📊 Traffic Limit: {max_traffic_gb:.2f} GB\n"
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
        
        # User is active, get subscription URL
        sub_url = api_client.get_subscription_url(username)
        
        if not sub_url:
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
        if is_callback:
            bot.edit_message_text(error_message, chat_id=chat_id, message_id=message_id)
        else:
            bot.send_message(chat_id, error_message)