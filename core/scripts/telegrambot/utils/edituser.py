# show and edit user file

import qrcode
import io
from telebot import types
from utils.command import bot, is_admin
from utils.common import create_main_markup
from utils.api_client import APIClient


@bot.callback_query_handler(func=lambda call: call.data == "cancel_show_user")
def handle_cancel_show_user(call):
    bot.edit_message_text("Operation canceled.", chat_id=call.message.chat.id, message_id=call.message.message_id)
    create_main_markup(call.message)

@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and message.text == '👤 Show User')
def show_user(message):
    markup = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_show_user")
    markup.add(cancel_button)
    
    msg = bot.reply_to(message, "Enter username:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_show_user)

def process_show_user(message):
    username = message.text.strip().lower()
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Use API client to get user details directly
    api_client = APIClient()
    
    # Just attempt to get the user directly
    user_details = api_client.get_user(username)

    if user_details is None:
        bot.reply_to(message, f"User '{username}' not found or API error.")
        return
    
    # Use the provided username directly
    actual_username = username
    
    try:
        upload_bytes = user_details.get('upload_bytes')
        download_bytes = user_details.get('download_bytes')
        status = user_details.get('status', 'Unknown')

        if upload_bytes is None or download_bytes is None:
            traffic_message = "**Traffic Data:**\nUser not active or no traffic data available."
        else:
            upload_gb = upload_bytes / (1024 ** 3)  # Convert bytes to GB
            download_gb = download_bytes / (1024 ** 3)  # Convert bytes to GB
            totalusage = upload_gb + download_gb
            
            traffic_message = (
                f"🔼 Upload: {upload_gb:.2f} GB\n"
                f"🔽 Download: {download_gb:.2f} GB\n"
                f"📊 Total Usage: {totalusage:.2f} GB\n"
                f"🌐 Status: {status}"
            )
    except Exception as e:
        bot.reply_to(message, f"Failed to process user data: {str(e)}")
        return

    formatted_details = (
        f"\n🆔 Name: {actual_username}\n"
        f"📊 Traffic Limit: {user_details['max_download_bytes'] / (1024 ** 3):.2f} GB\n"
        f"📅 Days: {user_details['expiration_days']}\n"
        f"⏳ Creation: {user_details['account_creation_date']}\n"
        f"💡 Blocked: {user_details['blocked']}\n\n"
        f"{traffic_message}"
    )
    
    # Get user URI from the API client
    user_uri_data = api_client.get_user_uri(actual_username)
    
    if not user_uri_data or 'normal_sub' not in user_uri_data:
        bot.reply_to(message, f"Error: Could not retrieve subscription URL for user '{actual_username}'. Check API configuration.")
        return
    
    sub_url = user_uri_data['normal_sub']
    ipv4_url = user_uri_data.get('ipv4', '')
    
    # Create QR code for subscription URL
    qr_code = qrcode.make(sub_url)
    bio = io.BytesIO()
    qr_code.save(bio, 'PNG')
    bio.seek(0)

    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton("Reset User", callback_data=f"reset_user:{actual_username}"))
    markup.add(types.InlineKeyboardButton("Edit Username", callback_data=f"edit_username:{actual_username}"),
               types.InlineKeyboardButton("Edit Traffic Limit", callback_data=f"edit_traffic:{actual_username}"))
    markup.add(types.InlineKeyboardButton("Edit Expiration Days", callback_data=f"edit_expiration:{actual_username}"),
               types.InlineKeyboardButton("Renew Password", callback_data=f"renew_password:{actual_username}"))
    markup.add(types.InlineKeyboardButton("Renew Creation Date", callback_data=f"renew_creation:{actual_username}"),
               types.InlineKeyboardButton("Block User", callback_data=f"block_user:{actual_username}"))

    caption = f"{formatted_details}\n\n"
    if ipv4_url:
        caption += f"IPv4 URL: `{ipv4_url}`\n\n"

    caption += f"Subscription URL:\n`{sub_url}`"
    
    bot.send_photo(
        message.chat.id,
        bio,
        caption=caption,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: any(call.data.startswith(p) for p in ['edit_username:', 'edit_traffic:', 'edit_expiration:', 'renew_password:', 'renew_creation:', 'block_user:', 'reset_user:']))
def handle_edit_callback(call):
    action, username = call.data.split(':')
    api_client = APIClient()
    
    if action == 'edit_username':
        msg = bot.send_message(call.message.chat.id, f"Enter new username for {username}:")
        bot.register_next_step_handler(msg, process_edit_username, username)
    elif action == 'edit_traffic':
        msg = bot.send_message(call.message.chat.id, f"Enter new traffic limit (GB) for {username}:")
        bot.register_next_step_handler(msg, process_edit_traffic, username)
    elif action == 'edit_expiration':
        msg = bot.send_message(call.message.chat.id, f"Enter new expiration days for {username}:")
        bot.register_next_step_handler(msg, process_edit_expiration, username)
    elif action == 'renew_password':
        # Use API to renew password
        result = api_client.update_user(username, {"renew_password": True})
        if result is None:
            bot.send_message(call.message.chat.id, f"Failed to renew password for user '{username}'.")
        else:
            bot.send_message(call.message.chat.id, f"Password for user '{username}' renewed successfully.")
    elif action == 'renew_creation':
        # Use API to renew creation date
        result = api_client.update_user(username, {"renew_creation_date": True})
        if result is None:
            bot.send_message(call.message.chat.id, f"Failed to renew creation date for user '{username}'.")
        else:
            bot.send_message(call.message.chat.id, f"Creation date for user '{username}' renewed successfully.")
    elif action == 'block_user':
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("True", callback_data=f"confirm_block:{username}:true"),
                   types.InlineKeyboardButton("False", callback_data=f"confirm_block:{username}:false"))
        bot.send_message(call.message.chat.id, f"Set block status for {username}:", reply_markup=markup)
    elif action == 'reset_user':
        # Use API to reset user
        result = api_client.reset_user(username)
        if result is None:
            bot.send_message(call.message.chat.id, f"Failed to reset user '{username}'.")
        else:
            bot.send_message(call.message.chat.id, f"User '{username}' reset successfully.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_block:'))
def handle_block_confirmation(call):
    _, username, block_status = call.data.split(':')
    api_client = APIClient()
    
    # Use API to set block status
    is_blocked = block_status == 'true'
    result = api_client.update_user(username, {"blocked": is_blocked})

    if result is None:
        bot.send_message(call.message.chat.id, f"Failed to update block status for user '{username}'.")
    else:
        status = "blocked" if is_blocked else "unblocked"
        bot.send_message(call.message.chat.id, f"User '{username}' {status} successfully.")

def process_edit_username(message, username):
    new_username = message.text.strip()
    
    # Validate the new username is not empty
    if not new_username:
        bot.reply_to(message, "Username cannot be empty.")
        return
    
    api_client = APIClient()
    result = api_client.update_user(username, {"new_username": new_username})

    if result is None:
        bot.reply_to(message, f"Failed to update username for '{username}'.")
    else:
        bot.reply_to(message, f"Username updated from '{username}' to '{new_username}' successfully.")

def process_edit_traffic(message, username):
    try:
        new_traffic_limit = int(message.text.strip())
        api_client = APIClient()
        result = api_client.update_user(username, {"new_traffic_limit": new_traffic_limit})

        if result is None:
            bot.reply_to(message, f"Failed to update traffic limit for user '{username}'.")
        else:
            bot.reply_to(message, f"Traffic limit for user '{username}' updated to {new_traffic_limit} GB successfully.")
    except ValueError:
        bot.reply_to(message, "Invalid traffic limit. Please enter a number.")

def process_edit_expiration(message, username):
    try:
        new_expiration_days = int(message.text.strip())
        api_client = APIClient()
        result = api_client.update_user(username, {"new_expiration_days": new_expiration_days})

        if result is None:
            bot.reply_to(message, f"Failed to update expiration days for user '{username}'.")
        else:
            bot.reply_to(message, f"Expiration days for user '{username}' updated to {new_expiration_days} days successfully.")
    except ValueError:
        bot.reply_to(message, "Invalid expiration days. Please enter a number.")
